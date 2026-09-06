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

# TODO:
data/results/cass:
	poetry run python processor/process_clarity.py https://results.enr.clarityelections.com//MI/Cass/127065/377945/reports/detailxml.zip $@

data/results/eaton:
	poetry run python processor/process_clarity.py https://results.enr.clarityelections.com//MI/Eaton/126881/378357/reports/detailxml.zip $@

data/results/emmet:
	poetry run python processor/process_clarity.py https://results.enr.clarityelections.com//MI/Emmet/126948/378360/reports/detailxml.zip $@

data/results/grand-traverse:
	poetry run python processor/process_clarity.py https://results.enr.clarityelections.com//MI/Grand_Traverse/127066/378477/reports/detailxml.zip $@

data/results/ottawa:
	poetry run python processor/process_clarity.py https://www.miottawavotes.gov//MI/Ottawa/126772/377930/reports/detailxml.zip $@

data/results/roscommon:
	poetry run python processor/process_clarity.py https://results.enr.clarityelections.com//MI/Roscommon/126770/378560/reports/detailxml.zip $@

data/results/bay: input/results/bay/primary.pdf
	poetry run python processor/process_bay_pdf.py $< $@

data/results/wayne: input/results/wayne/primary.pdf
	poetry run python processor/process_dominion_pdf.py $< $@

data/results/alger: input/results/alger/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/allegan: input/results/allegan/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

# TODO:
data/results/alpena: input/results/alpena/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/baraga: input/results/baraga/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/barry: input/results/barry/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/chippewa: input/results/chippewa/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/houghton: input/results/houghton/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/iron: input/results/iron/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/jackson: input/results/jackson/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/lenawee: input/results/lenawee/primary.pdf
	poetry run python processor/process_dominion_flat_pdf.py $< $@

data/results/marquette: input/results/marquette/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/mecosta: input/results/mecosta/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/oceana: input/results/oceana/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/ogemaw: input/results/ogemaw/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/oscoda: input/results/oscoda/primary.pdf
	poetry run python processor/process_dominion_alt_2_pdf.py $< $@

data/results/wexford: input/results/wexford/primary.pdf
	poetry run python processor/process_dominion_alt_pdf.py $< $@

data/results/berrien:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/berrien-county-mi/2026Augustelection $@

data/results/branch:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/branch-county-mi/August2026Primary $@

data/results/clare:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/clare-county-mi/2026AugustElection $@

data/results/delta:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/delta-county-mi/August2026Election $@

data/results/gratiot:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/gratiot-county-mi/GratiotCountyPrimary2026 $@

data/results/iosco:
	poetry run python processor/process_enhanced_voting.py 	https://app.enhancedvoting.com/results/public/api/elections/iosco-county-mi/AugustPrimary2026 $@

data/results/kent:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/kent-county-mi/08042026 $@

data/results/leelanau:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/leelanau-county-mi/20260804_LeelanauAugust2026Primary $@

data/results/midland:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/midland-county-mi/AugustPrimary2026 $@

data/results/monroe:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/monroe-county-mi/August2026Election $@

data/results/saginaw:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/saginaw-county-mi/SaginawCountyAugust2026Primary $@

data/results/shiawassee:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/shiawassee-county-mi/AUGUST42026 $@

data/results/st-joseph:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/st.-joseph-county-mi/2026PrimaryElection $@

data/results/ingham:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/ingham-county-mi/AugustElection08042026 $@

data/results/isabella:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/isabella-county-mi/August2026Primary $@

data/results/kalamazoo:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/kalamazoo-county-mi/August-2026-Primary-Election $@

data/results/lake:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/lake-county-mi/Aug-2026-Primary $@

data/results/newaygo:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/newaygo-county-mi/August2026PrimaryElection $@

data/results/osceola:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/osceola-county-mi/August2026 $@

data/results/st-clair:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/st.-clair-county-mi/2026AugustPrimary $@

data/results/van-buren:
	poetry run python processor/process_enhanced_voting.py https://app.enhancedvoting.com/results/public/api/elections/van-buren-county-mi/Primary2026 $@

data/results/clinton: input/results/clinton/primary.pdf
	poetry run python processor/process_canvass_pdf.py $< $@

data/results/hillsdale: input/results/hillsdale/primary.pdf
	poetry run python processor/process_hillsdale_pdf.py $< $@

data/results/montcalm: input/results/montcalm/primary.pdf
	poetry run python processor/process_canvass_pdf.py $< $@

input/precinct-id-map.json: input/precincts.geojson
	cat $< | poetry run python processor/process_precinct_id_map.py > $@

# TODO: Match on counties too, not just ID names, need to include CountyFIPS
# TODO: Benzie AVCBs
input/precincts.geojson:
	wget -O - 'https://hub.arcgis.com/api/v3/datasets/b7df95c78668407280a7dead8e26aad0_0/downloads/data?format=geojson&spatialRefId=4326&where=1=1' | \
	npm run mapshaper -- -i - \
	-dissolve where='CountyFIPS === "009"' calc='CountyFIPS = "009", PrecinctLongName= "Antrim County", PrecinctCode = "009"' \
	-dissolve where='CountyFIPS === "011"' calc='CountyFIPS = "011", PrecinctLongName= "Arenac County", PrecinctCode = "011"' \
	-dissolve where='CountyFIPS === "031"' calc='CountyFIPS = "031", PrecinctLongName= "Cheboygan County", PrecinctCode = "031"' \
	-dissolve where='CountyFIPS === "043"' calc='CountyFIPS = "043", PrecinctLongName= "Dickinson County", PrecinctCode = "043"' \
	-dissolve where='CountyFIPS === "051"' calc='CountyFIPS = "051", PrecinctLongName= "Gladwin County", PrecinctCode = "051"' \
	-dissolve where='CountyFIPS === "097"' calc='CountyFIPS = "097", PrecinctLongName= "Mackinac County", PrecinctCode = "097"' \
	-dissolve where='CountyFIPS === "109"' calc='CountyFIPS = "109", PrecinctLongName= "Menominee County", PrecinctCode = "109"' \
	-dissolve where='CountyFIPS === "119"' calc='CountyFIPS = "119", PrecinctLongName= "Montmorency County", PrecinctCode = "119"' \
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
