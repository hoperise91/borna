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
- Schema changes: edit `pipeline/sql/00_schema.sql`, then `make db-reset` (and re-run `make import register`) or apply the matching ALTER by hand.
- `data/`: git-ignored (`raw/` downloads, `interim/`, `out/` exports). Never commit data.
- `web/`: Astro site (Phase 3).
- `tests/lrs_checkpoints.csv`: the km-lookup quality gate (road, km, lat, lon, note). Target ±50 m.

## Commands
`make test` · `make help` · `make check-tools` · `make setup` · `make db-up` · `make psql` · `make download|import|register|lrs|tiles|web-dev`
