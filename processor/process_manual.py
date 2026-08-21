from pathlib import Path
import csv
import json

BASE_DIR = Path(__file__).parent.parent


MANUAL_COUNTIES = [
    "arenac",
    "charlevoix",
    "cheboygan",
    "crawford",
    "gogebic",
    "huron",
    "lapeer",
    "luce",
    "mackinac",
    "mason",
    "missaukee",
    "montmorency",
    "sanilac",
    "schoolcraft",
]

CONTESTS = [
    "mi-governor-dem",
    "mi-governor-rep",
    "representative-in-congress-1st-district-dem",
    "representative-in-congress-1st-district-dem",
    "united-states-senator-dem",
]

if __name__ == "__main__":
    with Path.open(BASE_DIR / "input" / "precinct-id-map.json", "r") as f:
        id_map = json.load(f)

    for county in MANUAL_COUNTIES:
        print(county)
        for contest in CONTESTS:
            input_file_path = BASE_DIR / "input" / "results" / county / f"{contest}.csv"
            if not input_file_path.exists():
                continue
            with Path.open(input_file_path, "r") as f:
                rows = [row for row in csv.DictReader(f)]
            output_fields = ["id"] + list(rows[0].keys())
            output_dir = (BASE_DIR / "data" / "results" / county).mkdir(
                parents=True, exist_ok=True
            )
            with Path.open(
                BASE_DIR / "data" / "results" / county / f"{contest}.csv", "w"
            ) as f:
                writer = csv.DictWriter(f, fieldnames=output_fields)
                writer.writeheader()
                for row in rows:
                    if row["name"] not in id_map[county]:
                        print(f"Precinct not found: {row['name']}")
                        continue
                    writer.writerow({"id": id_map[county][row["name"]], **row})
