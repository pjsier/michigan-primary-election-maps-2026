from pathlib import Path
from collections import defaultdict
import json
import csv
import requests

BASE_DIR = Path(__file__).parent.parent
BASE_URL = "https://gis.muskegoncountygis.com/arcgis/rest/services/Elections/Election_Results_2026_08/FeatureServer"

CONTESTS = [ "United States Senator - Democratic Primary", "Representative in Congress 2nd District - Democratic Primary", "Governor - Republican Primary", "Governor - Democratic Primary"]

contest_map = defaultdict(dict)

def get_contest_key(contest):
    if "senat" in contest.lower():
        return "united-states-senator-dem"
    if "district" in contest.lower():
        return "representative-in-congress-2nd-district-dem"
    if "dem" in contest.lower():
        return "mi-governor-dem"
    return "mi-governor-rep"

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
        if result["GIS_Contest_Title"] not in CONTESTS:
            continue
        choice_name = result["Choice_Name"]
        if choice_name == "Justin Blackburn":
            choice_name = "Write-in"
        contest_precinct_map[result["GIS_Contest_Title"]]["Total"][result["Precinct_Parent"]][choice_name]= result["Total_Votes"]
        contest_precinct_map[result["GIS_Contest_Title"]]["Election day"][result["Precinct_Parent"]][choice_name] = result["ElectionDayVoting_Votes"]
        contest_precinct_map[result["GIS_Contest_Title"]]["All early votes"][result["Precinct_Parent"]][choice_name] = result["EarlyVoting_Local_Votes"] + result["Absentee_Voting_Votes"]
    return contest_precinct_map

if __name__ == "__main__":
    output_dir = BASE_DIR / "data" / "results" / "muskegon"
    output_dir.mkdir(parents=True, exist_ok=True)
    federal_results = process_endpoint_results(query_endpoint(f"{BASE_URL}/5/query"))
    state_results = process_endpoint_results(query_endpoint(f"{BASE_URL}/7/query"))

    with Path.open(BASE_DIR / "input" / "precinct-id-map.json", "r") as f:
        id_map = json.load(f)["muskegon"]

    for contest, vote_types in {**federal_results, **state_results}.items():
        # contest_rows = []
        for vote_type, precincts in vote_types.items():
            precinct_rows = []
            for precinct_name, precinct_data in precincts.items():
                precinct_rows.append({"name": precinct_name, "id": id_map[precinct_name], **precinct_data})
            vote_type_slug = ""
            if vote_type != "Total":
                vote_type_slug = f'-{vote_type.lower().replace(" ", "-")}'
            with Path.open(output_dir / f"{get_contest_key(contest)}{vote_type_slug}.csv", "w") as f:
                writer = csv.DictWriter(f, fieldnames=list(precinct_rows[0].keys()))
                writer.writeheader()
                writer.writerows(precinct_rows)
