# TODO: Use more full basemap from Maptiler?

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

input/precinct-id-map.json: input/precincts.geojson
	cat $< | poetry run python scripts/process_precinct_id_map.py > $@

# TODO: Consolidating counties that don't publish precinct-level
# TODO: make ID int?
input/precincts.geojson:
	wget -O - 'https://hub.arcgis.com/api/v3/datasets/b7df95c78668407280a7dead8e26aad0_0/downloads/data?format=geojson&spatialRefId=4326&where=1=1' | \
	npm run mapshaper -- -i - \
	-dissolve where='CountyFIPS === "153"' calc='CountyFIPS = "153", PrecinctLongName= "Schoolcraft County", PrecinctCode = "153"' \
	-rename-fields id=PrecinctCode,name=PrecinctLongName \
	-filter-fields id,name \
	-o $@

input/counties.geojson: input/districts.geojson
	wget -O - 'https://hub.arcgis.com/api/download/v1/items/dcbf3b3eb47941cf9fb764b5f5308b15/geojson?redirect=true&layers=0&spatialRefId=4326' | \
	npm run mapshaper -- -i - \
	-clip $< \
	-o $@

input/districts.geojson:
	wget -O $@ 'https://hub.arcgis.com/api/download/v1/items/54edc5b8c1c54de39421e858998a6b31/geojson?redirect=true&layers=23&spatialRefId=4326'
