import csv
import os
import re
import sys
import json
from collections import defaultdict

import pandas as pd
import pdfplumber

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGET_KEYWORDS = ("congress", "governor")


def clean_header(header):
    return re.sub(
        r"\s+",
        " ",
        header.replace("NP -", "").replace("DEM -", "").replace("REP -", ""),
    ).strip()


def slugify(text):
    return re.sub(
        r"\s", "-", re.sub(r"\s+", " ", re.sub(r"[^a-z\d]", " ", text.lower())).strip()
    )


def get_race_file_key(race_key):
    if "governor" in race_key:
        return "mi-governor-dem" if "dem" in race_key else "mi-governor-rep"
    if "senat" in race_key:
        return "united-states-senator-dem"
    return (
        race_key.replace("democratic", "dem")
        .replace("republican", "rep")
        .replace("-party", "")
    )


def is_target_race(race_title):
    title = race_title.lower()
    if any(keyword in title for keyword in TARGET_KEYWORDS):
        return True
    if "senator" in title and "united states" in title and "democratic" in title:
        return True
    return False


def get_rotated_headers(page):
    words = page.extract_words(keep_blank_chars=True)
    vertical_words = [w for w in words if not w["upright"]]
    if not vertical_words:
        return [], 0, [], 0
    header_bottom = max(w["bottom"] for w in vertical_words)
    sorted_words = sorted(vertical_words, key=lambda w: w["x0"])
    columns = [[sorted_words[0]]]
    for w in sorted_words[1:]:
        if w["x0"] - columns[-1][-1]["x1"] < 5:
            columns[-1].append(w)
        else:
            columns.append([w])
    # Header text in this PDF is written bottom-to-top, so the extracted
    # string comes out reversed relative to normal reading order.
    headers = [
        " ".join(w["text"].strip() for w in sorted(col, key=lambda w: w["top"]))[::-1]
        for col in columns
    ]
    col_centers = [
        (min(w["x0"] for w in g) + max(w["x1"] for w in g)) / 2 for g in columns
    ]
    # Split point: just left of the first rotated header strip
    data_split = min(w["x0"] for w in sorted_words) - 7
    return headers, header_bottom, col_centers, data_split


def assign_to_col(x, col_centers):
    return min(range(len(col_centers)), key=lambda i: abs(col_centers[i] - x))


def extract_race_title(page):
    """The race title sits on the line right after 'Run Date ...  Page N'."""
    text = page.extract_text()
    if not text:
        return None
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    run_date_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("Run Date")), None
    )
    if run_date_idx is None or run_date_idx + 1 >= len(lines):
        return None
    return lines[run_date_idx + 1]


def extract_page_table(page, label_cols=("Precinct",)):
    col_headers, header_bottom, col_centers, data_split = get_rotated_headers(page)
    if not col_headers:
        return None

    all_words = page.extract_words(keep_blank_chars=True)
    data_words = sorted(
        [
            w
            for w in all_words
            if w["upright"]
            and w["top"] > header_bottom
            and w["bottom"] < page.height - 5
        ],
        key=lambda w: w["top"],
    )

    # Group words into rows. Normal row gap is larger than the gap between a
    # precinct row and its wrapped continuation line below it.
    ROW_GAP = 9
    rows = []
    for w in data_words:
        if not rows or w["top"] - rows[-1][0]["top"] > ROW_GAP:
            rows.append([w])
        else:
            rows[-1].append(w)

    # Handle multi-line precincts
    merged_rows = []
    for row in rows:
        label_words = [w for w in row if (w["x0"] + w["x1"]) / 2 < data_split]
        data_word_list = [w for w in row if (w["x0"] + w["x1"]) / 2 >= data_split]
        is_precinct_continuation = label_words and not data_word_list
        if is_precinct_continuation and merged_rows:
            merged_rows[-1]["precinct"] += " " + " ".join(
                w["text"].strip() for w in label_words
            )
        else:
            merged_rows.append(
                {
                    "precinct": " ".join(w["text"].strip() for w in label_words),
                    "data": data_word_list,
                }
            )

    all_headers = list(label_cols) + col_headers
    records = []
    for row in merged_rows:
        row_data = [""] * len(col_headers)
        for w in row["data"]:
            col_idx = assign_to_col((w["x0"] + w["x1"]) / 2, col_centers)
            row_data[col_idx] = (row_data[col_idx] + " " + w["text"].strip()).strip()
        records.append([row["precinct"]] + row_data)

    return pd.DataFrame(
        records, columns=[clean_header(header) for header in all_headers]
    )


if __name__ == "__main__":
    input_file = sys.argv[1]
    output_dir = sys.argv[2]
    county_slug = output_dir.split("/")[-1]

    os.makedirs(output_dir, exist_ok=True)

    id_map = {}
    id_map_path = os.path.join(BASE_DIR, "input", "precinct-id-map.json")
    if os.path.exists(id_map_path):
        with open(id_map_path, "r") as f:
            id_map = json.load(f)
    precinct_ids = id_map.get(county_slug, {})

    # Group races into batches to handle splitting across multiple pages
    label_cols = {"Precinct"}
    batch_frames: dict[str, dict[frozenset, pd.DataFrame]] = defaultdict(dict)

    with pdfplumber.open(input_file) as pdf:
        for idx, page in enumerate(pdf.pages):
            title = extract_race_title(page)
            if title is None or not is_target_race(title):
                continue

            df = extract_page_table(page)
            if df is None:
                print(idx, "no table found")
                continue

            race_key = slugify(title)
            batches = batch_frames[race_key]
            batch_key = frozenset(df.columns) - label_cols
            if batch_key in batches:
                batches[batch_key] = pd.concat(
                    [batches[batch_key], df], axis=0, ignore_index=True
                )
            else:
                batches[batch_key] = df

    df_map: dict[str, pd.DataFrame] = {}
    for race_key, batches in batch_frames.items():
        batch_dfs = list(batches.values())
        merged = batch_dfs[0]
        for other in batch_dfs[1:]:
            diff_cols = [c for c in other.columns if c not in merged.columns]
            df_to_merge = other[["Precinct"] + diff_cols]
            merged = pd.merge(merged, df_to_merge, on=["Precinct"], how="left")
        df_map[race_key] = merged

    for race_key, df_val in df_map.items():
        df_val = df_val.loc[:, ~df_val.columns.duplicated()]
        for col in df_val.columns:
            if col in ["Precinct", "Turnout Percentage"]:
                continue
            df_val[col] = (
                pd.to_numeric(
                    df_val[col].astype(str).str.replace(",", "", regex=False),
                    errors="coerce",
                )
                .fillna(0)
                .astype(int)
            )
        df_val = df_val.rename(
            columns={
                "Precinct": "name",
                "Cast Votes": "total",
                "Election Day Voting Ballots Cast": "election_day_ballots",
                "Absentee Voting Ballots Cast": "absentee_ballots",
                "Early Voting Ballots Cast": "early_ballots",
                "Total Ballots Cast": "ballots",
                "Registered Voters": "registered",
                "Turnout Percentage": "turnout",
                "Write-ins": "Write-in",
            }
        )

        non_candidate_cols = [
            "total",
            "election_day_ballots",
            "absentee_ballots",
            "early_ballots",
            "ballots",
            "registered",
            "turnout",
        ]
        candidate_cols = [
            c for c in df_val.columns if c not in ["name"] + non_candidate_cols
        ]

        is_precinct = df_val["name"].str.contains("Precinct", na=False)
        precinct_df = df_val.loc[is_precinct, ["name"] + candidate_cols].copy()
        precinct_df["id"] = precinct_df["name"].map(precinct_ids)
        if precinct_ids and precinct_df["id"].isna().any():
            # TODO: Print specific missing items
            print(f"Warning: missing precinct id mapping for some rows in {race_key}")
        precinct_df = precinct_df[["name", "id"] + candidate_cols]

        precinct_df.to_csv(
            f"{output_dir}/{get_race_file_key(race_key)}.csv", index=False
        )
        print(f"Wrote {race_key}.csv ({len(precinct_df)} precincts)")
