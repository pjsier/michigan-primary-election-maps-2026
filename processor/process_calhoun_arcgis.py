from pathlib import Path
from collections import defaultdict
import json
import csv
import requests

BASE_DIR = Path(__file__).parent.parent
BASE_URL = "https://services7.arcgis.com/3kp3Io7Dw56fpgk8/ArcGIS/rest/services/ElectionResults_join_f3043708a71343f49d0e1e6fa5d9dded/FeatureServer/2"

CONTESTS = [
    "02- United States Senator (DEM): 1 Position",
    "01- Governor (REP): 1 Position",
    "01- Governor (DEM): 1 Position",
]

contest_map = defaultdict(dict)


def get_contest_key(contest):
    if "senat" in contest.lower():
        return "united-states-senator-dem"
    if "dem" in contest.lower():
        return "mi-governor-dem"
    return "mi-governor-rep"


def clean_precinct(precinct):
    return precinct.replace("  ", ", ").replace(" Charter", "")


def query_endpoint(url):
    records = []
    offset = 0
    page_size = 2000

    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "f": "json",
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        features = data.get("features", [])
        records.extend(feature["attributes"] for feature in features)

        print(f"Got {len(features)} records (total: {len(records)})")

        if not data.get("exceededTransferLimit") or not features:
            break

        offset += len(features)

    print(f"Finished: {len(records)} records")
    return records


def process_endpoint_results(results):
    contest_precinct_map = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for result in results:
        if result["contest"] not in CONTESTS:
            continue
        choice_name = result["candidate"]
        contest_precinct_map[result["contest"]]["Total"][
            clean_precinct(result["jurisdictionname"])
        ][choice_name] = result["numvotes"]
    return contest_precinct_map


if __name__ == "__main__":
    output_dir = BASE_DIR / "data" / "results" / "calhoun"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = process_endpoint_results(query_endpoint(f"{BASE_URL}/query"))

    with Path.open(BASE_DIR / "input" / "precinct-id-map.json", "r") as f:
        id_map = json.load(f)["calhoun"]

    for contest, vote_types in results.items():
        # contest_rows = []
        for vote_type, precincts in vote_types.items():
            precinct_rows = []
            for precinct_name, precinct_data in precincts.items():
                precinct_rows.append(
                    {
                        "name": precinct_name,
                        "id": id_map[precinct_name],
                        **precinct_data,
                    }
                )
            vote_type_slug = ""
            if vote_type != "Total":
                vote_type_slug = f"-{vote_type.lower().replace(' ', '-')}"
            with Path.open(
                output_dir / f"{get_contest_key(contest)}{vote_type_slug}.csv", "w"
            ) as f:
                writer = csv.DictWriter(f, fieldnames=list(precinct_rows[0].keys()))
                writer.writeheader()
                writer.writerows(precinct_rows)
