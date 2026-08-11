from pathlib import Path
from collections import defaultdict
import json
import csv
import requests
import re

BASE_DIR = Path(__file__).parent.parent

SERVERS = {
    # "1": "turnout",
    "8": "mi-governor-dem",
    "9": "mi-governor-rep",
    "16": "united-states-senator-dem",
}

contest_map = defaultdict(dict)

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
    precinct_map = defaultdict(dict)
    for result in results:
        precinct = re.sub(r"\s+", " ", result["NAME"])
        precinct_map[precinct][result["Candidate1"]] = result["numvote1"]
        precinct_map[precinct][result["Candidate2"]] = result["numvote2"]
        if result.get("Candidate3"):
            precinct_map[precinct][result["Candidate3"]] = result["numvote3"]
    return precinct_map

if __name__ == "__main__":
    output_dir = BASE_DIR / "data" / "results" / "washtenaw"
    output_dir.mkdir(parents=True, exist_ok=True)

    with Path.open(BASE_DIR / "input" / "precinct-id-map.json", "r") as f:
        id_map = json.load(f)["washtenaw"]

    turnout_results = query_endpoint("https://services2.arcgis.com/xRI3cTw3hPVoEJP0/arcgis/rest/services/Aug2026Layers/FeatureServer/1/query")
    with Path.open(output_dir / "turnout.csv", "w") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "ballots", "registered", "turnout"])
        writer.writeheader()
        for turnout in turnout_results:
            precinct = re.sub(r"\s+", " ", turnout["NAME"])
            writer.writerow({
                "id": id_map[precinct],
                "name": precinct,
                "ballots": turnout["totballots"],
                "registered": turnout["regvoters"],
                "turnout": turnout["percvote"],
            })

    for server_id, contest in SERVERS.items():
        results = query_endpoint(f"https://services2.arcgis.com/xRI3cTw3hPVoEJP0/arcgis/rest/services/Aug2026Layers/FeatureServer/{server_id}/query")
        precincts = process_endpoint_results(results)
        precinct_rows = []
        for precinct_name, precinct_data in precincts.items():
            precinct_rows.append({"name": precinct_name, "id": id_map[precinct_name], **precinct_data})
        if len(precinct_rows) == 0:
            breakpoint()
        with Path.open(output_dir / f"{contest}.csv", "w") as f:
            writer = csv.DictWriter(f, fieldnames=list(precinct_rows[0].keys()))
            writer.writeheader()
            writer.writerows(precinct_rows)
