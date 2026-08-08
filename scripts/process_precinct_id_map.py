import json
import sys


if __name__ == "__main__":
    precincts = json.load(sys.stdin)
    output_map = {}
    for precinct in precincts["features"]:
        name = precinct["properties"]["name"].replace("3Macomb", "Macomb")
        precinct_id = precinct["properties"]["id"]
        output_map[name] = precinct_id
        if "Township of" in name:
            admin_name, precinct_num = name.split(", ")
            clean_admin_name = admin_name.replace("Charter ", "").replace(
                "Township of ", ""
            )
            clean_name = f"{clean_admin_name} Township, {precinct_num}"
            output_map[clean_name] = precinct_id
        elif "City of the Village of" in name:
            output_map[name.replace("City of the Village of ", "")] = precinct_id
        elif "City of" in name:
            output_map[name.replace("City of ", "")] = precinct_id
        if "Orchard Lake" in name:
            precinct_num = name.split(", ")[1]
            output_map[f"Orchard Lake, {precinct_num}"] = precinct_id
        if "Pontiac" in name:
            precinct_num = [p for p in name.split(", ") if "Precinct" in p][0]
            output_map[f"Pontiac, {precinct_num}"] = precinct_id
        if "Rochester Hills, District" in name:
            precinct_num = name.split(", ")[-1]
            output_map[f"Rochester Hills, {precinct_num}"] = precinct_id
        if "Inkster" in name:
            city, ward, precinct_num = name.split(", ")
            ward_num = ward.split(" ")[-1]
            output_map[f"City of Inkster, District {ward_num} {precinct_num}"] = (
                precinct_id
            )
        if "Brownstown" in name:
            precinct_num = name.split(", ")[-1]
            output_map[f"Charter Township of Brownstown, {precinct_num}"] = precinct_id
        if "Huron Township" in name:
            precinct_num = name.split(", ")[-1]
            output_map[f"Charter Township of Huron, {precinct_num}"] = precinct_id
        if "Northville Township" in name:
            precinct_num = name.split(", ")[-1]
            output_map[f"Charter Township of Northville, {precinct_num}"] = precinct_id
        if "Sumpter Township" in name:
            precinct_num = name.split(", ")[-1]
            output_map[f"Township of Sumpter, {precinct_num}"] = precinct_id
        if "Village of Grosse Pointe Shores":
            precinct_num = name.split(" ")[-1]
            output_map[f"The {name.replace('A Michigan', 'a Michigan')}"] = precinct_id
            output_map[f"Grosse Pointe Shores {precinct_num}"] = precinct_id

    json.dump(output_map, sys.stdout)
