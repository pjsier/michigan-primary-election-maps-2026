# TODO: Use more full basemap from Maptiler?
CLARITY_COUNTIES = 

data/tiles/%.pmtiles: data/tiles/%.mbtiles
	pmtiles convert $< $@

data/tiles/%.mbtiles: data/results/%.geojson
	tippecanoe \
	--simplification=10 \
	--simplify-only-low-zooms \
	--minimum-zoom=5 \
	--maximum-zoom=12 \
	--no-tile-stats \
	--detect-shared-borders \
	--grid-low-zooms \
	--coalesce-smallest-as-needed \
	--use-attribute-for-id=id \
	--force \
	-L precincts:$< -o $@

data/results/oakland:
	poetry run python processor/process_clarity.py https://results.enr.clarityelections.com//MI/OaklandMI/127075/377933/reports/detailxml.zip $@

data/results/macomb:
	poetry run python processor/process_clarity.py https://results.enr.clarityelections.com//MI/Macomb/126774/377944/reports/detailxml.zip $@

data/results/genesee:
	poetry run python processor/process_clarity.py https://results.enr.clarityelections.com//MI/Genesee/126773/377963/reports/detailxml.zip $@

data/results/ottawa:
	poetry run python processor/process_clarity.py https://www.miottawavotes.gov//MI/Ottawa/126772/377930/reports/detailxml.zip $@

data/results/wayne: input/results/wayne/primary.pdf
	poetry run python processor/process_dominion_pdf.py $< $@

data/results/marquette: input/results/marquette/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/jackson: input/results/jackson/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/kent:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/kent-county-mi/08042026 $@

data/results/saginaw:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/saginaw-county-mi/SaginawCountyAugust2026Primary $@

input/precinct-id-map.json: input/precincts.geojson
	cat $< | poetry run python processor/process_precinct_id_map.py > $@

# TODO: Match on counties too, not just ID names, need to include CountyFIPS
# TODO: Benzie AVCBs
input/precincts.geojson:
	wget -O - 'https://hub.arcgis.com/api/v3/datasets/b7df95c78668407280a7dead8e26aad0_0/downloads/data?format=geojson&spatialRefId=4326&where=1=1' | \
	npm run mapshaper -- -i - \
	-dissolve where='CountyFIPS === "003"' calc='CountyFIPS = "003", PrecinctLongName= "Alger County", PrecinctCode = "003"' \
	-dissolve where='CountyFIPS === "007"' calc='CountyFIPS = "007", PrecinctLongName= "Alpena County", PrecinctCode = "007"' \
	-dissolve where='CountyFIPS === "009"' calc='CountyFIPS = "009", PrecinctLongName= "Antrim County", PrecinctCode = "009"' \
	-dissolve where='CountyFIPS === "011"' calc='CountyFIPS = "011", PrecinctLongName= "Arenac County", PrecinctCode = "011"' \
	-dissolve where='CountyFIPS === "031"' calc='CountyFIPS = "031", PrecinctLongName= "Cheboygan County", PrecinctCode = "031"' \
	-dissolve where='CountyFIPS === "043"' calc='CountyFIPS = "043", PrecinctLongName= "Dickinson County", PrecinctCode = "043"' \
	-dissolve where='CountyFIPS === "051"' calc='CountyFIPS = "051", PrecinctLongName= "Gladwin County", PrecinctCode = "051"' \
	-dissolve where='CountyFIPS === "097"' calc='CountyFIPS = "097", PrecinctLongName= "Mackinac County", PrecinctCode = "097"' \
	-dissolve where='CountyFIPS === "109"' calc='CountyFIPS = "109", PrecinctLongName= "Menominee County", PrecinctCode = "109"' \
	-dissolve where='CountyFIPS === "119"' calc='CountyFIPS = "119", PrecinctLongName= "Montmorency County", PrecinctCode = "119"' \
	-dissolve where='CountyFIPS === "135"' calc='CountyFIPS = "135", PrecinctLongName= "Oscoda County", PrecinctCode = "135"' \
	-dissolve where='CountyFIPS === "137"' calc='CountyFIPS = "137", PrecinctLongName= "Otsego County", PrecinctCode = "137"' \
	-dissolve where='CountyFIPS === "141"' calc='CountyFIPS = "141", PrecinctLongName= "Presque Isle County", PrecinctCode = "141"' \
	-dissolve where='CountyFIPS === "153"' calc='CountyFIPS = "153", PrecinctLongName= "Schoolcraft County", PrecinctCode = "153"' \
	-rename-fields id=PrecinctCode,name=PrecinctLongName,countyfips=CountyFIPS \
	-each 'id = +id' \
	-filter-fields id,name,countyfips \
	-o $@

input/counties.geojson: input/districts.geojson
	wget -O - 'https://hub.arcgis.com/api/download/v1/items/dcbf3b3eb47941cf9fb764b5f5308b15/geojson?redirect=true&layers=0&spatialRefId=4326' | \
	npm run mapshaper -- -i - \
	-clip $< \
	-o $@

input/districts.geojson:
	wget -O $@ 'https://hub.arcgis.com/api/download/v1/items/54edc5b8c1c54de39421e858998a6b31/geojson?redirect=true&layers=23&spatialRefId=4326'
