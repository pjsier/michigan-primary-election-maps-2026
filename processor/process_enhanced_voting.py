import requests
import json
from pathlib import Path
import sys
import re
import csv
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def clean_precinct_name(name: str) -> str:
    """Handling some weird typos"""
    return name.replace("Athur ", "Arthur ")


def slugify(text):
    return (
        re.sub(
            r"\s",
            "-",
            re.sub(r"\s+", " ", re.sub(r"[^a-z\d]", " ", text.lower())).strip(),
        )
        .replace("-for-", "-")
        .replace("-state-senate", "")
    )


def process_ballot_item(base_url, item_id, candidate_map, id_map):
    res = requests.get(f"{base_url}/data/ballot-item/{item_id}")
    data = res.json()

    vote_type_groups = {"Total": []}
    for group_name in (
        data["ballotItemWithBreakdown"]["breakdownResults"][0]["ballotOptions"][0][
            "groupResults"
        ]
        or []
    ):
        vote_type_groups[group_name["groupName"][0]["text"]] = []
    vote_types = list(vote_type_groups.keys())

    for item in data["ballotItemWithBreakdown"]["breakdownResults"]:
        precinct_name = clean_precinct_name(item["precinct"]["name"][0]["text"])

        for vote_type in vote_types:
            # Hack to override weird multi-county item in Kent, Isabella
            if any(c in precinct_name for c in ("(Ionia County)", "(Clare County)", "(Out of County)")):
                continue
            result_obj = {
                "id": id_map[precinct_name],
                "name": precinct_name,
            }
            for ballot_option in item["ballotOptions"]:
                if vote_type == "Total":
                    result_obj[ballot_option["name"][0]["text"]] = ballot_option[
                        "voteCount"
                    ]
                else:
                    for group_result in ballot_option["groupResults"]:
                        if group_result["groupName"][0]["text"] == vote_type:
                            result_obj[ballot_option["name"][0]["text"]] = group_result[
                                "voteCount"
                            ]
            vote_type_groups[vote_type].append(result_obj)

    return vote_type_groups


def main():
    base_url = sys.argv[1]
    output_dir = Path(sys.argv[2])
    county_slug = output_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(os.path.join(BASE_DIR, "input", "precinct-id-map.json"), "r") as f:
        id_map = json.load(f)[county_slug]

    res = requests.get(f"{base_url}/data")
    data = res.json()

    turnout = []
    for precinct in data["voterTurnout"]:
        # Weird hack for county exception
        if any(
            c in precinct["precinctName"] for c in ("(Ionia County)", "(Clare County)", "(Out of County)")
        ):
            continue
        if precinct["voterRegistration"] == 0:
            turnout_val = 0.0
        else:
            turnout_val = round(
                (precinct["ballotsCast"] / precinct["voterRegistration"]) * 100, 2
            )
        precinct_name = clean_precinct_name(precinct["precinctName"])
        turnout.append(
            {
                "id": id_map[precinct_name],
                "name": precinct_name,
                "ballots": precinct["ballotsCast"],
                "registered": precinct["voterRegistration"],
                "turnout": turnout_val,
            }
        )
    if len(turnout) > 0:
        with Path.open(output_dir / "turnout.csv", "w") as f:
            writer = csv.DictWriter(f, fieldnames=list(turnout[0].keys()))
            writer.writeheader()
            writer.writerows(turnout)

    for ballot_item in data["ballotItems"]:
        item_name = ballot_item["name"][0]["text"]
        if not any(w in item_name for w in ("Governor", "States Senator", "Congress")):
            continue
        print(item_name)
        candidate_map = {}
        for ballot_option in ballot_item["summaryResults"]["ballotOptions"]:
            candidate_map[ballot_option["id"]] = ballot_option["name"][0]["text"]

        vote_type_results = process_ballot_item(
            base_url, ballot_item["id"], candidate_map, id_map
        )
        for vote_type, item_results in vote_type_results.items():
            vote_type_slug = ""
            if vote_type != "Total":
                vote_type_slug = f"-{slugify(vote_type)}"
            with Path.open(
                output_dir / f"{slugify(item_name)}{vote_type_slug}.csv", "w"
            ) as f:
                writer = csv.DictWriter(f, fieldnames=list(item_results[0].keys()))
                writer.writeheader()
                writer.writerows(item_results)


if __name__ == "__main__":
    main()
