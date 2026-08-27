import csv
import os
import re
import sys
import json

import pandas as pd
from collections import defaultdict
import pdfplumber
from typing import Any, DefaultDict, Dict, List, Optional, Tuple, TypedDict, Union

from pdfplumber.page import Page

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

Char = Dict[str, Any]
BBox = Tuple[float, float, float, float]
PageLike = Union[Page, "pdfplumber.page.CroppedPage"]


def slugify(text):
    return re.sub(
        r"\s", "-", re.sub(r"\s+", " ", re.sub(r"[^a-z\d]", " ", text.lower())).strip()
    ).replace("-for-", "-")


def _is_rotated_char(c: Char) -> bool:
    matrix = c.get("matrix")
    if matrix:
        return (
            abs(matrix[0]) < 1e-6
            and abs(matrix[3]) < 1e-6
            and (abs(matrix[1]) > 1e-6 or abs(matrix[2]) > 1e-6)
        )
    if "upright" in c:
        return not c["upright"]
    return False


def _clean_value(value):
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    if not value:
        return None
    return value.replace("%", "").replace(",", "")


def extract_cell_text(
    page: PageLike, bbox: Optional[BBox], x_gap: float = 1.0, y_gap: float = 3.0
) -> str:
    if not bbox:
        return ""
    x0, top, x1, bottom = bbox
    chars: List[Char] = [
        c
        for c in page.chars
        if not _is_rotated_char(c)
        and x0 - 0.5 <= c["x0"] < x1 + 0.5
        and top - 0.5 <= c["top"] < bottom + 0.5
    ]
    if not chars:
        return ""

    chars.sort(key=lambda c: (round(c["top"], 1), c["x0"]))
    lines: List[List[Char]] = []
    current: List[Char] = []
    current_top: Optional[float] = None
    for c in chars:
        if current_top is None or abs(c["top"] - current_top) <= y_gap:
            current.append(c)
            current_top = c["top"] if current_top is None else current_top
        else:
            lines.append(current)
            current = [c]
            current_top = c["top"]
    if current:
        lines.append(current)

    line_texts = []
    for line in lines:
        line = sorted(line, key=lambda c: c["x0"])
        text = ""
        prev: Optional[Char] = None
        for c in line:
            if prev is not None and (c["x0"] - prev["x1"]) > x_gap:
                text += " "
            text += c["text"]
            prev = c
        line_texts.append(text)

    return re.sub(r"\s+", " ", " ".join(line_texts)).strip()


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


def extract_rotated_headers(
    page: Page, table, gap: float = 25.0
) -> list[tuple[float, float, str]]:
    chars = [
        c
        for c in page.chars
        if _is_rotated_char(c) and table.bbox[1] - 1 <= c["top"] <= table.bbox[3]
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
    for i, cell in enumerate(row_cells):
        if cell and cell[0] - 0.5 <= x <= cell[2] + 0.5:
            return i
    return None


def _build_header_map(page: Page, table) -> Dict[int, str]:
    rotated_headers = [
        (x0, x1, header)
        for x0, x1, header in extract_rotated_headers(page, table)
        if table.bbox[0] - 1 <= (x0 + x1) / 2 <= table.bbox[2] + 1
    ]
    if not rotated_headers:
        return {}

    # Find a data row (any row after the header row that has real cells) to
    # use for mapping header x-position -> column index.
    sample_row = None
    for row in table.rows[1:]:
        if row.cells and any(row.cells):
            sample_row = row
            break
    if sample_row is None:
        sample_row = table.rows[-1]

    header_map: Dict[int, str] = {}
    for x0, x1, header in rotated_headers:
        idx = _cell_index_for_x(sample_row.cells, (x0 + x1) / 2)
        if idx is not None:
            header_map[idx] = header
    return header_map


def extract_table_info(page: Page, table, state: dict) -> dict:
    header_map = _build_header_map(page, table)
    raw_rows = table.extract()
    precinct_map: DefaultDict[str, dict] = defaultdict(dict)
    precinct = state.get("precinct", "")

    for i, row in enumerate(raw_rows):
        if i == 0:
            continue  # header row

        cell0_bbox = table.rows[i].cells[0] if i < len(table.rows) else None
        label = extract_cell_text(page, cell0_bbox)
        if not label:
            label = _clean_value(row[0]) or ""
        if not label:
            continue
        if label == "Precinct":
            continue

        has_values = any(v and str(v).strip() for v in row[1:])

        if "Cumulative" in label:
            if not has_values:
                precinct = label
            continue

        if "County" in label:
            continue

        if not has_values:
            precinct = label
            continue

        vote_type = label
        if vote_type != "Total":
            continue
        if "Cumulative" in precinct:
            continue

        entry = precinct_map[precinct]
        for idx, header in header_map.items():
            if idx < len(row):
                val = _clean_value(row[idx])
                if val is not None:
                    entry[header] = val
        entry["Vote Type"] = "Total"

    state["precinct"] = precinct
    return precinct_map


def process_results_input(input_file: str) -> dict:
    current_race = "Registration"
    race_mappings = {current_race: defaultdict(dict)}
    race_state = {current_race: {"precinct": ""}}
    with pdfplumber.open(input_file) as pdf:
        header_font = detect_header_font(pdf.pages[0])
        for i in range(len(pdf.pages)):
            page = pdf.pages[i]
            if race_header := extract_race_header(page, header_font):
                current_race = race_header
                race_mappings.setdefault(current_race, defaultdict(dict))
                race_state.setdefault(current_race, {"precinct": ""})
            state = race_state[current_race]
            for table in page.find_tables():
                for precinct, precinct_row in extract_table_info(
                    page, table, state
                ).items():
                    vote_type = precinct_row.pop("Vote Type", "Total")
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
            if precinct_key[1] != "Total":
                continue

            reg = registration_lookup.get(precinct_key[0], {})

            registered_raw = precinct_data.pop("Registered Voters", None)
            if not registered_raw:
                registered_raw = reg.get("Registered Voters", "")
            precinct_data["registered"] = int(registered_raw) if registered_raw else 0

            times_cast_raw = precinct_data.pop("Times Cast", None)
            if not times_cast_raw:
                times_cast_raw = reg.get("Voters Cast", "0")
            precinct_data["ballots"] = int(times_cast_raw) if times_cast_raw else 0

            precinct_data["over_votes"] = "0"
            precinct_data["under_votes"] = "0"
            precinct_data["total"] = precinct_data.pop("Total Votes", "")
            precinct_data["turnout"] = (
                round((precinct_data["ballots"] / precinct_data["registered"]) * 100, 2)
                if precinct_data["registered"]
                else 0
            )
            if "Unresolved Write-In" in precinct_data:
                precinct_data["Write-in"] = precinct_data.pop(
                    "Unresolved Write-In", "0"
                )
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
        output_file_key = (
            slugify(race_key).replace("dem-dem", "dem").replace("rep-rep", "rep")
        )
        if output_file_key == "registration":
            output_file_key = "turnout"
        with open(f"{output_dir}/{output_file_key}.csv", "w") as f:
            writer = csv.DictWriter(f, output_results[0].keys())
            writer.writeheader()
            writer.writerows(output_results)
