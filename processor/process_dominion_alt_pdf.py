import csv
import os
import re
import sys
import json

import pandas as pd
from collections import defaultdict
import pdfplumber
from typing import Any, DefaultDict, Dict, List, Optional, Tuple, TypedDict, Union

import pdfplumber
from pdfplumber.page import Page

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# pdfplumber itself types chars/words as Dict[str, Any] (see pdfplumber._typing.T_obj)
# and bounding boxes as a 4-tuple of numbers -- mirror those here rather than
# reaching into pdfplumber's private module.
Char = Dict[str, Any]
BBox = Tuple[float, float, float, float]

# page.crop() returns a CroppedPage, which exposes the same .chars/.find_tables()
# API as Page but isn't the same class -- accept either.
PageLike = Union[Page, "pdfplumber.page.CroppedPage"]


def slugify(text):
    return re.sub(
        r"\s", "-", re.sub(r"\s+", " ", re.sub(r"[^a-z\d]", " ", text.lower())).strip()
    ).replace("-for-", "-")


def _is_rotated_char(c: Char) -> bool:
    matrix = c.get("matrix")
    if matrix:
        return abs(matrix[0]) < 1e-6 and abs(matrix[3]) < 1e-6 and (
            abs(matrix[1]) > 1e-6 or abs(matrix[2]) > 1e-6
        )
    if "upright" in c:
        return not c["upright"]
    return False


def header_text_for_cell(
    page_or_crop: PageLike,
    cell_bbox: BBox,
    space_gap: float = 1.5,
) -> str:
    """
    Reconstruct the text of one rotated header cell.

    cell_bbox: (x0, top, x1, bottom) as returned by pdfplumber's
               table.rows[...].cells
    space_gap: min vertical gap (pts) between consecutive chars in a
               rotated line to be treated as a word-space.
    """
    x0, top, x1, bottom = cell_bbox
    chars: List[Char] = [
        c
        for c in page_or_crop.chars
        if _is_rotated_char(c)
        and x0 - 0.5 <= c["x0"] < x1 + 0.5
        and top - 0.5 <= c["top"] < bottom + 0.5
    ]
    if not chars:
        return ""

    # Each distinct x0 = one wrapped line of the rotated header.
    by_x: DefaultDict[float, List[Char]] = defaultdict(list)
    for c in chars:
        by_x[round(c["x0"], 1)].append(c)

    lines: List[str] = []
    for x in sorted(by_x):  # ascending x0 = left-to-right wrap order
        line_chars = sorted(by_x[x], key=lambda c: -c["top"])  # rotated reading order
        text = ""
        prev: Optional[Char] = None
        for c in line_chars:
            if prev is not None and (prev["top"] - c["bottom"]) > space_gap:
                text += " "
            text += c["text"]
            prev = c
        lines.append(text)

    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def detect_header_font(first_page) -> str:
    words = first_page.extract_words(extra_attrs=["size", "fontname"])
    top_words = [w for w in words if w["top"] < 100]
    if not top_words:
        return ""
    return max(top_words, key=lambda w: w["size"])["fontname"]


def extract_race_header(page, header_font, top_cutoff=100, title_size_cutoff=16):
    words = page.extract_words(extra_attrs=["size", "fontname"])
    bold_words = [
        w
        for w in words
        if w["fontname"] == header_font
        and w["top"] < top_cutoff
        and w["size"] < title_size_cutoff
    ]
    if not bold_words:
        return None
    race_header_str = " ".join(
        w["text"] for w in sorted(bold_words, key=lambda w: (w["top"], w["x0"]))
    )
    return re.sub(r"\s+", " ", re.sub(r"\(.*\)", "", race_header_str)).strip()


def extract_rotated_headers(page: Page, table, gap: float = 25.0) -> list[tuple[float, float, str]]:
    chars = [
        c for c in page.chars
        if _is_rotated_char(c)
        and table.bbox[1] - 1 <= c["top"] <= table.bbox[3]
    ]
    if not chars:
        return []

    xs = sorted({round(c["x0"], 1) for c in chars})
    clusters: list[list[float]] = []
    current: list[float] = []
    for x in xs:
        if current and x - current[-1] > gap:
            clusters.append(current)
            current = []
        current.append(x)
    if current:
        clusters.append(current)

    headers = []
    for cluster in clusters:
        cluster_set = set(cluster)
        cluster_chars = [c for c in chars if round(c["x0"], 1) in cluster_set]
        by_x: DefaultDict[float, List[Char]] = defaultdict(list)
        for c in cluster_chars:
            by_x[round(c["x0"], 1)].append(c)

        lines = []
        for x in sorted(by_x):
            line_chars = sorted(by_x[x], key=lambda c: -c["top"])
            text = ""
            prev = None
            for c in line_chars:
                if prev is not None and (prev["top"] - c["bottom"]) > 1.5:
                    text += " "
                text += c["text"]
                prev = c
            lines.append(text)

        text = re.sub(r"\s+", " ", " ".join(lines)).strip()
        if text:
            headers.append((min(cluster), max(cluster), text))
    return headers


def _cell_index_for_x(row_cells, x: float) -> Optional[int]:
    """Return the row cell containing x."""
    for i, cell in enumerate(row_cells):
        if cell and cell[0] - 0.5 <= x <= cell[2] + 0.5:
            return i
    return None


def _clean_value(value):
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    if not value:
        return None
    return value.replace("%", "").replace(",", "")


def extract_registration_table(table) -> dict:
    """Extract the registration/turnout table on page 1 of the new layout."""
    rows = table.extract()
    result = defaultdict(list)
    columns = ["Vote Type", "Registered Voters", "Voters Cast", "% Turnout"]

    for row in rows:
        label = re.sub(r"\s+", " ", row[0] or "").strip()
        if not label or label == "Precinct" or "Cumulative" in label or "County" in label:
            continue
        values = [_clean_value(v) for v in row[1:4]]
        if not any(v is not None for v in values):
            continue
        result[label].append(dict(zip(columns, ["Total", *values])))
    return result


def extract_combined_table_info(page: Page, table, state: dict) -> dict:
    """Extract a Dominion table where registration and candidate results share one table."""
    rows = table.extract()
    rotated_headers = extract_rotated_headers(page, table)
    if not rotated_headers:
        return {}

    # Map each rotated header to the data cell whose x-range contains its center.
    header_map = {}
    sample_row = table.rows[4] if len(table.rows) > 4 else table.rows[-1]
    for x0, x1, header in rotated_headers:
        idx = _cell_index_for_x(sample_row.cells, (x0 + x1) / 2)
        if idx is not None:
            header_map[idx] = header

    registration_headers = {
        idx: header for idx, header in header_map.items()
        if header in {"Times Cast", "Registered Voters", "% Turnout", "Voters Cast"}
    }
    candidate_headers = {
        idx: header for idx, header in header_map.items()
        if header not in registration_headers.values()
    }

    precinct_map = defaultdict(dict)
    for row in rows[1:]:
        if not row:
            continue
        cleaned = [re.sub(r"\s+", " ", v or "").strip() if v is not None else None for v in row]
        labels = [i for i, v in enumerate(cleaned) if v and ("Precinct" in v)]
        if not labels:
            continue

        precinct = cleaned[labels[0]]
        if not precinct or precinct == "Precinct" or "Cumulative" in precinct:
            continue

        # Ignore county aggregate rows.
        if "County" in precinct:
            continue

        entry = precinct_map[precinct]
        for idx, header in registration_headers.items():
            if idx < len(cleaned) and cleaned[idx] is not None:
                entry[header] = _clean_value(cleaned[idx])
        for idx, header in candidate_headers.items():
            if idx < len(cleaned) and cleaned[idx] is not None:
                entry[header] = _clean_value(cleaned[idx])

        # The output pipeline expects one synthetic "Total" vote type per precinct.
        entry["Vote Type"] = "Total"

    return defaultdict(list, {p: [data] for p, data in precinct_map.items()})


def extract_vertical_headers(page: Page, table) -> list[str]:
    # Kept for compatibility with the older Dominion layout.
    cropped = page.crop(table.bbox)
    header_row = cropped.find_tables()[0].rows[0]
    return [
        header_text_for_cell(cropped, cell) if cell else "" for cell in header_row.cells
    ]


def extract_table_info(page: Page, table, state: dict) -> dict:
    rows = table.extract()
    joined_header = " ".join(str(v or "") for v in rows[:4])

    rotated_headers = extract_rotated_headers(page, table)

    # Page 1 is a plain registration table.
    if not rotated_headers and "Registered" in joined_header and "Voters Cast" in joined_header:
        return extract_registration_table(table)

    # New Dominion layout: registration and candidate columns are in one table.
    if "Times Cast" in joined_header or rotated_headers:
        return extract_combined_table_info(page, table, state)

    # Older layout: preserve the original extraction behavior.
    raw_headers = extract_vertical_headers(page, table)
    headers = [h for h in raw_headers if h]
    table_rows = rows

    has_header_row = True
    if "Voters Cast" in table_rows[0]:
        table_columns = ["Vote Type"] + [re.sub(r"\s+", " ", c or "").strip() for c in table_rows[0][1:]]
    elif headers:
        if "Times Cast" in headers:
            table_columns = ["Vote Type"] + raw_headers[1:]
        else:
            table_columns = ["Vote Type"]
            for header in headers:
                table_columns.append(header)
                if "Total" not in header:
                    table_columns.append(f"{header} Percent")
    else:
        has_header_row = False
        table_columns = state.get("table_columns") or ["Vote Type"]

    precinct_map = defaultdict(list)
    precinct = state.get("precinct", "")
    rows_to_process = table_rows[1:] if has_header_row else table_rows
    done_with_precincts = False
    for row in rows_to_process:
        if done_with_precincts:
            continue
        label = re.sub(r"\s+", " ", row[0] or "").strip()
        if not label or "Cumulative" in label:
            continue
        has_values = any(v and str(v).strip() for v in row[1:])
        if "County" in label or "top District" in label:
            if has_values:
                done_with_precincts = True
            continue
        if not has_values:
            precinct = label
            continue
        if precinct:
            vote_type, row_precinct = label, precinct
        else:
            vote_type, row_precinct = "Total", label
        row_values = [vote_type] + [_clean_value(r) for r in row[1:]]
        precinct_row = dict(zip(table_columns, row_values))
        precinct_row.pop("", None)
        precinct_map[row_precinct].append(precinct_row)

    state["precinct"] = precinct
    state["table_columns"] = table_columns
    return precinct_map

def process_results_input(input_file: str) -> dict:
    current_race = "Registration"
    race_mappings = {current_race: defaultdict(dict)}
    race_state = {current_race: {"precinct": "", "table_columns": None}}
    with pdfplumber.open(input_file) as pdf:
        header_font = detect_header_font(pdf.pages[0])
        # Flush cache at the end because these get large
        for i in range(len(pdf.pages)):
            page = pdf.pages[i]
            if race_header := extract_race_header(page, header_font):
                current_race = race_header
                race_mappings.setdefault(current_race, defaultdict(dict))
                race_state.setdefault(
                    current_race, {"precinct": "", "table_columns": None}
                )
            state = race_state[current_race]
            for table in page.find_tables():
                for precinct, precinct_rows in extract_table_info(
                    page, table, state
                ).items():
                    for precinct_row in precinct_rows:
                        vote_type = precinct_row.pop("Vote Type")
                        race_mappings[current_race][precinct, vote_type].update(
                            precinct_row
                        )
            page.flush_cache()

    return race_mappings


if __name__ == "__main__":
    input_file = sys.argv[1]
    output_dir = sys.argv[2]
    county_slug = output_dir.split("/")[-1]
    os.makedirs(output_dir, exist_ok=True)

    id_map_path = os.path.join(BASE_DIR, "input", "precinct-id-map.json")
    if os.path.exists(id_map_path):
        with open(id_map_path, "r") as f:
            id_map = json.load(f)
    else:
        print(f"WARNING: {id_map_path} not found; falling back to slugified IDs")
        id_map = {}

    processed_results = process_results_input(input_file)
    registration_lookup = {
        precinct: data
        for (precinct, vote_type), data in processed_results.get(
            "Registration", {}
        ).items()
        if vote_type == "Total"
    }

    for race_key, race_results in processed_results.items():
        if not any(w in race_key.lower() for w in ("governor", "senator", "congress")):
            continue
        output_results = []
        for precinct_key, precinct_data in race_results.items():
            # TODO: Currently filtering out Detroit, later on we can join to state dataset
            # if "Detroit" not in precinct_key[0]:
            #     continue
            # TODO: Can split out in future
            if precinct_key[1] != "Total":
                continue

            reg = registration_lookup.get(precinct_key[0], {})

            registered_raw = precinct_data.pop("Registered Voters", None)
            if not registered_raw:
                registered_raw = reg.get("Registered Voters", "")
            precinct_data["registered"] = int(registered_raw)

            times_cast_raw = precinct_data.pop("Times Cast", None)
            if not times_cast_raw:
                times_cast_raw = reg.get("Voters Cast", "0")
            precinct_data["ballots"] = int(times_cast_raw)

            precinct_data["over_votes"] = "0"
            precinct_data["under_votes"] = "0"
            precinct_data["total"] = precinct_data.pop("Total Votes", "")
            precinct_data["turnout"] = round(
                (precinct_data["ballots"] / precinct_data["registered"]) * 100, 2
            )
            if "Voters Cast" in precinct_data:
                precinct_data["ballots"] = int(precinct_data.pop("Voters Cast", "0"))
            if "% Turnout" in precinct_data:
                precinct_data["turnout"] = precinct_data.pop("% Turnout", "")
            elif reg.get("% Turnout"):
                precinct_data["turnout"] = reg.get("% Turnout")
            if "Unresolved Write-In" in precinct_data:
                precinct_data["Write-in"] = precinct_data.pop("Unresolved Write-In", "0")
            precinct_data_keys = list(precinct_data.keys())
            for precinct_data_key in precinct_data_keys:
                if " Percent" in precinct_data_key:
                    precinct_data.pop(precinct_data_key, None)
                elif "(" in precinct_data_key:
                    clean_key = re.sub(r"\s\(.*\)", "", precinct_data_key)
                    precinct_data[clean_key] = precinct_data.pop(precinct_data_key)

            output_results.append(
                {
                    "id": id_map.get(county_slug, {}).get(
                        precinct_key[0], slugify(precinct_key[0])
                    ),
                    "name": precinct_key[0],
                    "board": "",
                    **precinct_data,
                }
            )
        if len(output_results) == 0:
            continue
        output_file_key = slugify(race_key).replace("dem-dem", "dem").replace("rep-rep", "rep")
        if output_file_key == "registration":
            output_file_key = "turnout"
        with open(f"{output_dir}/{output_file_key}.csv", "w") as f:
            writer = csv.DictWriter(f, output_results[0].keys())
            writer.writeheader()
            writer.writerows(output_results)