import os
import re
import sys
import json
from collections import defaultdict

import pandas as pd
import pdfplumber

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEADER_LINES = {"TOTAL Election Absentee Early", "Day Counting Voting", "Board"}

CANDIDATE_LINE_RE = re.compile(
    r"^(.+?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)$"
)
RACE_TITLE_RE = re.compile(r"^(DEM|REP) ")
VOTE_FOR_RE = re.compile(r"^Vote For \d+$")


def slugify(text):
    return re.sub(
        r"\s", "-", re.sub(r"\s+", " ", re.sub(r"[^a-z\d]", " ", text.lower())).strip()
    )


def get_race_file_key(race_key):
    if "governor" in race_key:
        return "mi-governor-dem" if "dem" in race_key else "mi-governor-rep"
    if "senat" in race_key:
        return "united-states-senator-dem"
    return race_key


def is_target_race(race_title):
    title = race_title.lower()
    if "governor" in title or "congress" in title:
        return True
    if title.startswith("dem") and "united states senator" in title:
        return True
    return False


def clean_precinct_name(name):
    return name.replace("Twp.", "Township").replace("Pct ", "Precinct ").replace("Mt. ", "Mount ")


def extract_precinct_bodies(pdf):
    precinct_bodies = {}
    order = []
    current_name = None

    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        lines = text.split("\n")

        header_idx = next(
            (i for i, line in enumerate(lines) if "Primary Election" in line), None
        )
        if header_idx is None or header_idx + 2 >= len(lines):
            continue

        precinct_name = clean_precinct_name(lines[header_idx + 2])
        body = lines[header_idx + 3 :]
        body = [line for line in body if not line.startswith("Precinct Summary")]

        if precinct_name != current_name:
            current_name = precinct_name
            order.append(current_name)
            precinct_bodies[current_name] = []
        precinct_bodies[current_name].extend(body)

    return order, precinct_bodies


def parse_precinct_body(body):
    races = {}
    current_title = None
    current_candidates = None
    in_statistics = False

    def flush():
        if current_title is not None:
            races[current_title] = current_candidates

    for line in body:
        line = line.strip()
        if not line:
            continue

        if RACE_TITLE_RE.match(line):
            flush()
            current_title = line
            current_candidates = []
            in_statistics = False
            continue

        if line.startswith("Statistics "):
            flush()
            current_title = None
            current_candidates = None
            in_statistics = True
            continue

        if in_statistics:
            continue

        if VOTE_FOR_RE.match(line) or line in HEADER_LINES:
            continue

        match = CANDIDATE_LINE_RE.match(line)
        if match and current_title is not None:
            name = match.group(1).strip()
            total_votes = match.group(2)
            current_candidates.append((name, total_votes))

    flush()
    return races


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

    with pdfplumber.open(input_file) as pdf:
        precinct_order, precinct_bodies = extract_precinct_bodies(pdf)

    race_data = defaultdict(dict)
    race_candidate_order = defaultdict(list)

    for precinct_name in precinct_order:
        races = parse_precinct_body(precinct_bodies[precinct_name])
        for title, candidates in races.items():
            if not is_target_race(title):
                continue
            race_key = slugify(title)
            row = {}
            for name, total in candidates:
                col_name = "Write-in" if name == "Write-In Totals" else name
                row[col_name] = total
                if col_name not in race_candidate_order[race_key]:
                    race_candidate_order[race_key].append(col_name)
            race_data[race_key][precinct_name] = row

    for race_key, precinct_rows in race_data.items():
        candidate_cols = race_candidate_order[race_key]

        records = []
        for precinct_name in precinct_order:
            if precinct_name not in precinct_rows:
                continue
            row = precinct_rows[precinct_name]
            record = {"name": precinct_name}
            for col in candidate_cols:
                record[col] = row.get(col, 0)
            records.append(record)

        df = pd.DataFrame(records, columns=["name"] + candidate_cols)
        for col in candidate_cols:
            df[col] = (
                pd.to_numeric(
                    df[col].astype(str).str.replace(",", "", regex=False),
                    errors="coerce",
                )
                .fillna(0)
                .astype(int)
            )

        df["id"] = df["name"].map(precinct_ids)
        if precinct_ids and df["id"].isna().any():
            # TODO: Print specific missing items
            print(f"Warning: missing precinct id mapping for some rows in {race_key}")
        df = df[["name", "id"] + candidate_cols]

        df.to_csv(f"{output_dir}/{get_race_file_key(race_key)}.csv", index=False)
        print(f"Wrote {race_key}.csv ({len(df)} precincts)")
