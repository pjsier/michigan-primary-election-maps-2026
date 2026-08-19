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
        if not c.get("upright", True)
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


def extract_race_header(page, top_cutoff=100, title_size_cutoff=16):
    """Return the race-header text if this page starts a new race, else None.

    Every page repeats the document title ("Statement of Votes Cast") in bold
    18pt Georgia near the top of the page. Actual race headers ("Governor
    (DEM) (Vote for 1)", etc.) use the same bold Georgia font but at 14pt.
    Without the size filter, the title on page 1 gets mistaken for a race
    header, which stomps on the "Registration" bucket and misfiles the
    registration table under "Statement of Votes Cast".
    """
    words = page.extract_words(extra_attrs=["size", "fontname"])
    bold_words = [
        w
        for w in words
        if "Bold" in w["fontname"]
        and "Georgia" in w["fontname"]
        and w["top"] < top_cutoff
        and w["size"] < title_size_cutoff
    ]
    if not bold_words:
        return None
    race_header_str = " ".join(
        w["text"] for w in sorted(bold_words, key=lambda w: (w["top"], w["x0"]))
    )
    return re.sub(r"\s+", " ", re.sub(r"\(.*\)", "", race_header_str)).strip()


def extract_vertical_headers(page: Page, table) -> list[str]:
    cropped = page.crop(table.bbox)
    header_row = cropped.find_tables()[0].rows[0]
    return [
        header_text_for_cell(cropped, cell) if cell else "" for cell in header_row.cells
    ]


def extract_table_info(page: Page, table) -> dict:
    # Skipping first because it's always Precinct/Vote Type
    headers = [h for h in extract_vertical_headers(page, table) if h]
    table_columns = ["Vote Type"]
    if "Times Cast" in headers:
        table_columns.extend(headers)
    else:
        for header in headers:
            table_columns.append(header)
            if "Total" not in header:
                table_columns.append(f"{header} Percent")

    precinct_map = defaultdict(list)
    precinct = ""
    table_rows = table.extract()
    # Registration at top is a bit different
    if "Voters Cast" in table_rows[0]:
        table_columns = ["Vote Type"] + [
            re.sub(r"\s+", " ", c).strip() for c in table_rows[0][1:]
        ]

    # Classify rows by labels, content
    done_with_precincts = False
    for row in table_rows[1:]:
        if done_with_precincts:
            continue

        label = re.sub(r"\s+", " ", row[0] or "").strip()
        if not label or "Cumulative" in label:
            continue

        has_values = any(v and v.strip() for v in row[1:])

        if "County" in label or "top District" in label:
            if has_values:
                done_with_precincts = True
            continue

        if not has_values:
            # Format B label row -- remember the precinct, no data here.
            precinct = label
            continue

        if precinct:
            vote_type, row_precinct = label, precinct
        else:
            vote_type, row_precinct = "Total", label

        row_values = [vote_type] + [
            (r.replace("%", "").replace(",", "") if r else r) for r in row[1:]
        ]
        precinct_map[row_precinct].append(dict(zip(table_columns, row_values)))

    return precinct_map


def process_results_input(input_file: str) -> dict:
    current_race = "Registration"
    race_mappings = {current_race: defaultdict(dict)}
    with pdfplumber.open(input_file) as pdf:
        # Flush cache at the end because these get large
        for i in range(len(pdf.pages)):
            page = pdf.pages[i]
            if race_header := extract_race_header(page):
                current_race = race_header
                race_mappings[current_race] = defaultdict(dict)
            for table in page.find_tables():
                for precinct, precinct_rows in extract_table_info(page, table).items():
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

            precinct_data["registered"] = int(
                precinct_data.pop("Registered Voters", "")
            )
            precinct_data["ballots"] = int(precinct_data.pop("Times Cast", "0"))
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
            precinct_data_keys = list(precinct_data.keys())
            for precinct_data_key in precinct_data_keys:
                if " Percent" in precinct_data_key:
                    precinct_data.pop(precinct_data_key, None)
                elif "(" in precinct_data_key:
                    clean_key = re.sub(r"\s\(.*\)", "", precinct_data_key)
                    precinct_data[clean_key] = precinct_data.pop(precinct_data_key)

            output_results.append(
                {
                    "id": id_map[county_slug].get(
                        precinct_key[0], slugify(precinct_key[0])
                    ),
                    "name": precinct_key[0],
                    "board": "",
                    **precinct_data,
                }
            )
        if len(output_results) == 0:
            continue
        output_file_key = slugify(race_key)
        if output_file_key == "registration":
            output_file_key = "turnout"
        with open(f"{output_dir}/{output_file_key}.csv", "w") as f:
            writer = csv.DictWriter(f, output_results[0].keys())
            writer.writeheader()
            writer.writerows(output_results)
