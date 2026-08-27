import json
import re
import sys
from collections import defaultdict

MI_COUNTY_FIPS = {
    "001": "alcona",
    "003": "alger",
    "005": "allegan",
    "007": "alpena",
    "009": "antrim",
    "011": "arenac",
    "013": "baraga",
    "015": "barry",
    "017": "bay",
    "019": "benzie",
    "021": "berrien",
    "023": "branch",
    "025": "calhoun",
    "027": "cass",
    "029": "charlevoix",
    "031": "cheboygan",
    "033": "chippewa",
    "035": "clare",
    "037": "clinton",
    "039": "crawford",
    "041": "delta",
    "043": "dickinson",
    "045": "eaton",
    "047": "emmet",
    "049": "genesee",
    "051": "gladwin",
    "053": "gogebic",
    "055": "grand-traverse",
    "057": "gratiot",
    "059": "hillsdale",
    "061": "houghton",
    "063": "huron",
    "065": "ingham",
    "067": "ionia",
    "069": "iosco",
    "071": "iron",
    "073": "isabella",
    "075": "jackson",
    "077": "kalamazoo",
    "079": "kalkaska",
    "081": "kent",
    "083": "keweenaw",
    "085": "lake",
    "087": "lapeer",
    "089": "leelanau",
    "091": "lenawee",
    "093": "livingston",
    "095": "luce",
    "097": "mackinac",
    "099": "macomb",
    "101": "manistee",
    "103": "marquette",
    "105": "mason",
    "107": "mecosta",
    "109": "menominee",
    "111": "midland",
    "113": "missaukee",
    "115": "monroe",
    "117": "montcalm",
    "119": "montmorency",
    "121": "muskegon",
    "123": "newaygo",
    "125": "oakland",
    "127": "oceana",
    "129": "ogemaw",
    "131": "ontonagon",
    "133": "osceola",
    "135": "oscoda",
    "137": "otsego",
    "139": "ottawa",
    "141": "presque-isle",
    "143": "roscommon",
    "145": "saginaw",
    "147": "st-clair",
    "149": "st-joseph",
    "151": "sanilac",
    "153": "schoolcraft",
    "155": "shiawassee",
    "157": "tuscola",
    "159": "van-buren",
    "161": "washtenaw",
    "163": "wayne",
    "165": "wexford",
}
if __name__ == "__main__":
    precincts = json.load(sys.stdin)
    output_map = defaultdict(dict)

    for precinct in precincts["features"]:
        name = precinct["properties"]["name"].replace("3Macomb", "Macomb")
        precinct_id = precinct["properties"]["id"]
        county_slug = re.sub(
            r"[^a-z]",
            "-",
            MI_COUNTY_FIPS[precinct["properties"]["countyfips"]]
            .lower()
            .replace(".", ""),
        )
        output_map[county_slug][name] = precinct_id
        if "Township of" in name:
            admin_name, precinct_num = name.split(", ")
            clean_admin_name = admin_name.replace("Charter ", "").replace(
                "Township of ", ""
            )
            clean_name = f"{clean_admin_name} Township, {precinct_num}"
            output_map[county_slug][clean_name] = precinct_id
        elif "City of the Village of" in name:
            output_map[county_slug][name.replace("City of the Village of ", "")] = (
                precinct_id
            )
        elif "City of" in name:
            output_map[county_slug][name.replace("City of ", "")] = precinct_id
            # HACK
            if "Fenton" in name:
                output_map["oakland"][name.replace("City of ", "")] = precinct_id
        if "Orchard Lake" in name:
            precinct_num = name.split(", ")[1]
            output_map[county_slug][f"Orchard Lake, {precinct_num}"] = precinct_id
        if "Pontiac" in name:
            precinct_num = [p for p in name.split(", ") if "Precinct" in p][0]
            output_map[county_slug][f"Pontiac, {precinct_num}"] = precinct_id
        if "Rochester Hills, District" in name:
            precinct_num = name.split(", ")[-1]
            output_map[county_slug][f"Rochester Hills, {precinct_num}"] = precinct_id
        if "Inkster" in name:
            city, ward, precinct_num = name.split(", ")
            ward_num = ward.split(" ")[-1]
            output_map[county_slug][
                f"City of Inkster, District {ward_num} {precinct_num}"
            ] = precinct_id
        if "Brownstown" in name:
            precinct_num = name.split(", ")[-1]
            output_map[county_slug][
                f"Charter Township of Brownstown, {precinct_num}"
            ] = precinct_id
        if "Huron Township" in name:
            precinct_num = name.split(", ")[-1]
            output_map[county_slug][f"Charter Township of Huron, {precinct_num}"] = (
                precinct_id
            )
        if "Northville Township" in name:
            precinct_num = name.split(", ")[-1]
            output_map[county_slug][
                f"Charter Township of Northville, {precinct_num}"
            ] = precinct_id
        if "Sumpter Township" in name:
            precinct_num = name.split(", ")[-1]
            output_map[county_slug][f"Township of Sumpter, {precinct_num}"] = (
                precinct_id
            )
        if "Village of Grosse Pointe Shores" in name:
            precinct_num = name.split(" ")[-1]
            output_map[county_slug][
                f"The {name.replace('A Michigan', 'a Michigan')}"
            ] = precinct_id
            output_map[county_slug][f"Grosse Pointe Shores {precinct_num}"] = (
                precinct_id
            )
        if (("City of Muskegon" in name) or ("City of Flint" in name)) and (
            "Ward" in name
        ):
            split_precinct = name.split(", ")
            updated_precinct = ", ".join([split_precinct[0], split_precinct[2]])
            output_map[county_slug][updated_precinct] = precinct_id
        if "Fruitport" in name:
            precinct_num = name.split(" ")[-1]
            output_map[county_slug][
                f"Fruitport Charter Township, Precinct {precinct_num}"
            ] = precinct_id
        if "City of Marquette" in name:
            precinct_num = name.split(" ")[-1]
            output_map[county_slug][
                f"City of Marquette, Ward 1, Precinct {precinct_num}"
            ] = precinct_id
        if "Chocolay" in name:
            output_map[county_slug][name.replace("Chocolay", "Chocolay Charter")] = (
                precinct_id
            )
        if "Marquette Township" in name:
            output_map[county_slug][
                name.replace("Marquette Township", "Marquette Charter Township")
            ] = precinct_id
        if "Blackman Township" in name:
            output_map[county_slug][name.replace("Blackman", "Blackman Charter")] = (
                precinct_id
            )
        if "Columbia Township" in name:
            output_map[county_slug][name.replace("Columbia", "Columbia Charter")] = (
                precinct_id
            )
        if "Sandstone Township" in name:
            output_map[county_slug][name.replace("Sandstone", "Sandstone Charter")] = (
                precinct_id
            )
        if "Caledonia Township" in name:
            precinct_num = name.split(" ")[-1]
            output_map[county_slug][
                f"Caledonia Charter Township, Precinct {precinct_num}"
            ] = precinct_id
        if "Cedar Springs" in name:
            output_map[county_slug]["Cedar Springs City, Precinct 1"] = precinct_id
        if "City of East Grand Rapids" in name:
            second_component = ", ".join(name.split(", ")[1:])
            output_map[county_slug][f"East Grand Rapids City, {second_component}"] = (
                precinct_id
            )
        if "City of Grand Rapids" in name:
            second_component = ", ".join(name.split(", ")[1:])
            output_map[county_slug][f"Grand Rapids City, {second_component}"] = (
                precinct_id
            )
        if "Manchester Township" in name:
            output_map[county_slug][
                name.replace("Manchester Township", "City of Manchester")
            ] = precinct_id
        if name.startswith("City of "):
            components = name.split(", ")
            precinct_name = ", ".join(
                [f"{components[0].replace('City of ', '')} City"] + components[1:]
            )
            output_map[county_slug][precinct_name] = precinct_id
        if "Pavilion Township" in name:
            precinct_num = name.split(" ")[-1]
            output_map[county_slug][
                f"Charter Township of Pavilion, Precinct {precinct_num}"
            ] = precinct_id
        if "Maple Forest Township" in name:
            output_map[county_slug][name.replace("501", "1")] = precinct_id
        if (county_slug == "barry") and ("City of Hastings" in name):
            precinct_num = name.split(" ")[-1]
            output_map[county_slug][
                f"City of Hastings, Ward {precinct_num}, Precinct {precinct_num}"
            ] = precinct_id
        if (county_slug == "barry") and any(
            w in name for w in ["Hastings Township", "Rutland"]
        ):
            output_map[county_slug][name.replace(" Township", " Charter Township")] = (
                precinct_id
            )
        if county_slug == "delta":
            output_map[county_slug][name.replace("Bay De ", "Bay de ")] = precinct_id
        if county_slug == "houghton":
            if "City of Hancock" in name:
                precinct_num = name.split(" ")[-1]
                output_map[county_slug][
                    f"City of Hancock, Ward {precinct_num}, Precinct {precinct_num}"
                ] = precinct_id
            if any(w in name for w in ["Chassell", "Calumet"]):
                output_map[county_slug][
                    name.replace(" Township", " Charter Township")
                ] = precinct_id
        if county_slug == "mecosta":
            if ("Big Rapids" in name) or ("Green" in name):
                output_map[county_slug][
                    name.replace(" Township", " Charter Township")
                ] = precinct_id
        if county_slug == "isabella":
            if "Pleasant" in name:
                output_map[county_slug][name.replace("Mount ", "Mt. ")] = precinct_id
            if "Union Township" in name:
                output_map[county_slug][
                    name.replace(" Township", " Charter Township")
                ] = precinct_id
        if (county_slug == "gogebic") and ("Ironwood Township" in name):
            output_map[county_slug][
                name.replace("Ironwood Township", "Ironwood Charter Township")
            ] = precinct_id
        if (county_slug == "mason") and "Ludington" in name:
            clean_name = ", ".join(name.split(", ")[:-1]).replace("Ward", "Precinct")
            output_map["mason"][clean_name] = precinct_id
        if (county_slug == "ogemaw") and ("City" in name):
            output_map[county_slug][
                name.replace(", Precinct 1", ", Ward 1, Precinct 1")
            ] = precinct_id
        if county_slug == "allegan":
            if "Gunplain" in name:
                output_map[county_slug][name.replace("Gunplain", "Gun Plain")] = (
                    precinct_id
                )
        if county_slug in ["ingham", "kalamazoo"]:
            if "Township" in name:
                output_map[county_slug][
                    name.replace("Township", "Charter Township")
                ] = precinct_id
        if county_slug == "berrien":
            if "Benton Harbor, Ward" in name:
                ward_num = name.split(",")[1].split(" ")[-1]
                output_map[county_slug][
                    name.replace("Precinct 1", f"Precinct {ward_num}")
                ] = precinct_id
        if county_slug == "branch":
            if "City of Coldwater" in name:
                ward_num = name.split(",")[1].split(" ")[-1]
                output_map[county_slug][f"City of Coldwater, Precinct {ward_num}"] = (
                    precinct_id
                )
        if county_slug == "chippewa":
            output_map[county_slug][
                name.replace("Detour", "DeTour").replace(
                    "Drummond Township", "Drummond Island Township"
                )
            ] = precinct_id
        if county_slug == "clinton":
            output_map[county_slug][
                name.replace("De Witt", "DeWitt")
                .replace("Bath Town", "Bath Charter Town")
                .replace("DeWitt Town", "DeWitt Charter Town")
                .replace("Watertown Town", "Watertown Charter Town")
            ] = precinct_id
        if county_slug == "emmet" and ("City of Petoskey" in name):
            name_start = ", ".join(name.split(", ")[:2])
            output_map[county_slug][f"{name_start}, Precinct 1"] = precinct_id
        if county_slug == "iosco":
            output_map[county_slug][name.replace("Au Sable", "AuSable")] = precinct_id
        if county_slug == "monroe" and ("Monroe" in name):
            output_map[county_slug][
                name.replace("Monroe Township", "Monroe Charter Township")
            ] = precinct_id
        if county_slug == "shiawassee" and ("Owosso" in name):
            output_map[county_slug][
                name.replace("Owosso Township", "Owosso Charter Township")
            ] = precinct_id
        if county_slug == "van-buren" and ("South Haven Township" in name):
            output_map[county_slug][
                name.replace("Haven Township", "Haven Charter Township")
            ] = precinct_id
        if county_slug == "calhoun" and ("City of Battle Creek" in name):
            precinct = name.split(", ")[-1]
            output_map[county_slug][f"City of Battle Creek, {precinct}"] = precinct_id
        if county_slug == "lenawee":
            output_map[county_slug][name.replace("Tecumseh, Ward 1, ", "Tecumseh, ").replace("Raisin ", "Raisin Charter ")] = precinct_id

    output_map["van-buren"]["City of South Haven, Ward 3, Precinct 2"] = output_map[
        "allegan"
    ]["City of South Haven, Ward 3, Precinct 2"]

    json.dump(output_map, sys.stdout, indent=2)
