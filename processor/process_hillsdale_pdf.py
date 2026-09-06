import csv
import os
import re
import sys
import json
from collections import defaultdict

import pdfplumber

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGET_CONTEST_KEYWORDS = (
    "representative-in-congress",
    "united-states-senator-dem",
    "governor",
)

HEADER_LINE = "Choice Party Early Voting AVCB Election Day Total"

PRECINCT_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<ballots>\d[\d,]*)\s+of\s+(?P<registered>[\d,]+)"
    r"\s+registered voters\s*=\s*(?P<turnout>[\d.]+)%$"
)

ROW_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<early>\d[\d,]*)\s+(?P<early_pct>[\d.]+)%\s+"
    r"(?P<avcb>\d[\d,]*)\s+(?P<avcb_pct>[\d.]+)%\s+"
    r"(?P<eday>\d[\d,]*)\s+(?P<eday_pct>[\d.]+)%\s+"
    r"(?P<total>\d[\d,]*)\s+(?P<total_pct>[\d.]+)%$"
)


def slugify(text):
    slug_text = re.sub(
        r"\s", "-", re.sub(r"\s+", " ", re.sub(r"[^a-z\d]", " ", text.lower())).strip()
    )
    slug_text = re.sub(r"-vote-for-not-more-than-\d+$", "", slug_text)
    slug_text = slug_text.replace("-democratic-party", "-dem").replace(
        "-republican-party", "-rep"
    )
    return slug_text


def clean_candidate_name(candidate_name):
    name = candidate_name.replace(",", "").strip()
    if name.endswith("(W)"):
        return "Write-in"
    return name


def to_int(text):
    return int(text.replace(",", ""))


def iter_page_races(page):
    text = page.extract_text()
    if not text:
        return
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    header_idxs = [i for i, line in enumerate(lines) if line == HEADER_LINE]
    for hi in header_idxs:
        j = hi - 1
        title_lines = []
        while (
            j >= 0
            and lines[j] != HEADER_LINE
            and not lines[j].startswith("Cast Votes:")
            and not PRECINCT_RE.match(lines[j])
        ):
            title_lines.append(lines[j])
            j -= 1
        title = " ".join(reversed(title_lines))

        rows = []
        k = hi + 1
        while k < len(lines) and not lines[k].startswith("Cast Votes:"):
            m = ROW_RE.match(lines[k])
            if m:
                rows.append(
                    (
                        clean_candidate_name(m.group("name")),
                        to_int(m.group("early")),
                        to_int(m.group("avcb")),
                        to_int(m.group("eday")),
                        to_int(m.group("total")),
                    )
                )
            k += 1

        yield title, rows


def parse_pdf(input_file):
    turnout_by_precinct = {}
    contests = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

    with pdfplumber.open(input_file) as pdf:
        current_precinct = None
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            for line in text.split("\n"):
                m = PRECINCT_RE.match(line.strip())
                if m:
                    current_precinct = m.group("name").strip()
                    turnout_by_precinct.setdefault(
                        current_precinct,
                        {
                            "name": current_precinct,
                            "ballots": m.group("ballots").replace(",", ""),
                            "registered": m.group("registered").replace(",", ""),
                            "turnout": m.group("turnout"),
                        },
                    )
                    break

            if current_precinct is None:
                print(idx, "no precinct header found yet, skipping page")
                continue

            for title, rows in iter_page_races(page):
                if not rows:
                    continue
                choice_map = contests[title][current_precinct]
                for candidate, early, avcb, eday, _total in rows:
                    vote_types = choice_map.setdefault(candidate, {})
                    # AVCB (absentee) votes are folded directly into Early
                    # Voting, so there are only two raw buckets downstream.
                    vote_types["Early Voting"] = (
                        vote_types.get("Early Voting", 0) + early + avcb
                    )
                    vote_types["Election Day"] = vote_types.get("Election Day", 0) + eday

    return turnout_by_precinct, contests


def process_contest(contest_choices, id_map):
    precinct_map = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for precinct_name, choices in contest_choices.items():
        for choice, vote_type_votes in choices.items():
            for vote_type_name, votes in vote_type_votes.items():
                precinct_map[precinct_name][vote_type_name][choice] += votes
                precinct_map[precinct_name]["Total"][choice] += votes

    precinct_vote_type_map = defaultdict(list)
    for precinct, vote_type_results in precinct_map.items():
        for vote_type, results in vote_type_results.items():
            total = sum(results.values())
            write_ins = 0
            results_keys = list(results.keys())
            for results_key in results_keys:
                if "rite-in" in results_key:
                    write_ins += results.pop(results_key)
            if id_map and precinct not in id_map:
                print(f"Warning: missing precinct id mapping for {precinct!r}")
            precinct_vote_type_map[vote_type].append(
                {
                    "id": id_map.get(precinct),
                    "name": precinct,
                    "total": total,
                    "over_votes": "",
                    "under_votes": "",
                    "Write-in": write_ins,
                    **results,
                }
            )
    return precinct_vote_type_map


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

    turnout_by_precinct, contests = parse_pdf(input_file)

    turnout_rows = []
    for precinct_name, row in turnout_by_precinct.items():
        if precinct_ids and precinct_name not in precinct_ids:
            print(f"Warning: missing precinct id mapping for {precinct_name!r}")
            continue
        turnout_rows.append({"id": precinct_ids.get(precinct_name), **row})
    if turnout_rows:
        with open(os.path.join(output_dir, "turnout.csv"), "w") as f:
            writer = csv.DictWriter(f, fieldnames=list(turnout_rows[0].keys()))
            writer.writeheader()
            writer.writerows(turnout_rows)

    for contest_title, contest_choices in contests.items():
        contest_slug = slugify(contest_title)
        if not any(w in contest_slug for w in TARGET_CONTEST_KEYWORDS):
            continue

        precinct_vote_type_map = process_contest(contest_choices, precinct_ids)

        for vote_type, rows in precinct_vote_type_map.items():
            if len(rows) == 0:
                continue
            vote_type_suffix = "" if vote_type == "Total" else f"-{slugify(vote_type)}"
            with open(
                os.path.join(output_dir, f"{contest_slug}{vote_type_suffix}.csv"),
                "w",
            ) as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            print(f"Wrote {contest_slug}{vote_type_suffix}.csv ({len(rows)} precincts)")
