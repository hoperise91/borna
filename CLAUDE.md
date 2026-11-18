# Bornă: conventions

Romania's open road database: an NVDB-style portal built from public data. The plan lives in `docs/ROADMAP.md`. Work one roadmap step at a time and commit after each one.

## Non-negotiables
- **Public data only.** Use only sources listed in ROADMAP §2 (or similar public/open ones). No scraping behind logins and no data obtained by formal request until Phase 5.
- **Source, date and licence on every value.** Every row in `road`, `road_segment`, `attribute_event` and `point_object` references `borna.source`. Attribute events and point objects also carry `source_date` and `licence`. Never merge values from two sources into one unlabelled value.
- **CRS:** store geometry in **EPSG:4326**. Compute every length, distance and chainage in **EPSG:3844 (Stereo 70)**. Use constants from `pipeline/borna/config.py` and don't hard-code SRIDs.
- **Linear referencing is the primary key.** Format positions as `DN1 km 27+400`; store them as numeric km (`27.400`, 3 decimals).
- **Bilingual.** All user-facing text is Romanian by default (`/`), with English at `/en/`. Use proper diacritics (ș ț with comma below, not cedilla ş ţ).

## Licensing
- Code is MIT. OSM/Overture-derived layers are ODbL (share-alike), so keep them in separate files from other-licence layers.
- HG 540 register: official act, public under Legea 8/1996 art. 9. Always cite the act and its amendments.
- CESTRIN layers: attribution plus a take-down-on-request policy.

## Layout
- `pipeline/borna/`: Python 3.12 package. One module per Makefile target (`download`, `importer`, `register`, `lrs`, `tiles`).
- `pipeline/sql/`: schema and SQL. `00_schema.sql` runs on first DB start. Schemas: `raw` (untouched imports) and `borna` (the reference network).
- `pipeline/osm2pgsql/roads.lua`: flex style → `raw.osm_roads`, `raw.osm_road_points` (milestones, junctions, level crossings, tolls, borders), `raw.osm_road_routes` (route relations with ordered `way_ids`).
- Downloads write `data/raw/<source>/manifest.json`; `make import` loads them and upserts `borna.source`. Overture lands in `raw.overture_segment` / `raw.overture_connector` (nested fields as jsonb). Its bbox covers neighbouring countries too: clip with GISCO boundaries (Phase 1 step 6).
- `make register` parses the HG 540/2000 annexes (`data/raw/hg540/anexe.html`, newest consolidation from legislatie.just.ro) into `borna.register_entry` (one row per published table row, lists `national`, `county_dn`, `dj`, `dc`, `dp`) and derives `borna.road` (one row per ref; national roads have `county` NULL; county codes are ISO 3166-2:RO). It checks parsed sums against the totals printed in the act and writes `data/out/hg540/{register,totals_check,amendments,problems}.csv`. Known typos in the act go in `REF_CORRECTIONS` with a reason; never silently change official values.
- `gisco` → `raw.gisco_nuts` (NUTS 2024, `county` on level 3) and `raw.gisco_lau` (3,181 UATs; `siruta`, `county`). `ins_trn139a` → `raw.ins_trn139a` (INS road length by category × surface × area × year; `county` set on county rows). County names → ISO codes via `borna.romania.county_code`.
- `aadt_end` → `raw.end_major_roads`: open AADT (CC BY 4.0, data.gov.ro) from the Environmental Noise Directive reporting, only roads above 3M vehicles/year (299 sections, 72 roads); `aadt` = annualTrafficFlow / 365. The full CESTRIN 2022 census layer is access-restricted: Phase 5 request.
- EuroRegionalMap (Open Maps for Europe WFS, token in `.env` as `ERM_TOKEN`): checked 2026-11-18, **Romania is not in the open release** (only neighbouring MD/HU/RS roads), so it can't serve as a DN/DJ cross-check. TENtec (webgate.ec.europa.eu) was down on 2026-11-18; retry before Phase 3.
- Never work around access controls on a source (403s, token-gated or referer-restricted services). Public-data-only means data that is openly served; anything else waits for a formal request (Phase 5).
- `make lrs` (Phase 2) builds the linear reference network: `borna.osm_way_ref` (normalised OSM road numbers, from ref tags and route relations), `borna.osm_way_county`, one centreline per HG 540 road (ramps dropped, gaps ≤300 m bridged, longest path), km calibrated from county-border km (per-county DN tables), junctions with the roads named at the route's ends, and milestones; output `borna.road_segment` (km_quality calibrated/interpolated/estimated) and `borna.lrs_road`. `borna.locate(ref, km, county)` returns the point. Reports in `data/out/lrs/` (gaps, OSM refs not in the register, checkpoints). Orientation: county-border/junction/milestone controls, else the places named at the route's ends (OSM place nodes), else the roads named there; county roads split into pieces keep the piece nearest those places. `borna.measure(ref, point, county)` is the reverse lookup. `make lrs ARGS=--holdout` keeps every 5th milestone out of calibration and reports the error at them (2026-11-18: median 12 m, 89% within 50 m on DN roads). Private QA points go in `tests/local_checkpoints.csv` (git-ignored; e.g. km-stones read from Google Street View, which must never be published or used as a data source). Checkpoints must stay within 50 m; never move a checkpoint to make it pass unless the point itself was wrong, and say why in its note.
- `make attributes` (after `make lrs`) places OSM surface/lanes/maxspeed/width/bridge/tunnel (values as tagged, per way) and open AADT on road km ranges in `borna.attribute_event`, with source, date and licence; same-value ranges merged. OSM `lanes` is per way, so each carriageway of a dual road reports its own lanes.
- `make qa` (after lrs + attributes) writes `data/out/qa/`: county lengths (HG 540 vs INS vs OSM), county surface shares (INS vs OSM tags; INS modernised + light pavement = paved), exact attribute coverage, gaps by county, OSM refs not in the register, and a README.md summary meant for sharing.
- Schema changes: edit `pipeline/sql/00_schema.sql`, then `make db-reset` (and re-run `make import register`) or apply the matching ALTER by hand.
- `data/`: git-ignored (`raw/` downloads, `interim/`, `out/` exports). Never commit data.
- `web/`: Astro site (Phase 3).
- `tests/lrs_checkpoints.csv`: the km-lookup quality gate (road, km, lat, lon, note). Target ±50 m. Note where each km value comes from (local knowledge, HG 540, milestone photo); approximate ones say so.

## Commands
`make test` · `make help` · `make check-tools` · `make setup` · `make db-up` · `make psql` · `make download|import|register|lrs|tiles|web-dev`
