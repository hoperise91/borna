# Bornă — Romania's open road database
### Roadmap from idea to live portal (RO / EN)

> **Name:** **Bornă**, from *bornă kilometrică*, the kilometre post. Short, works in both languages, and it points at the core feature: finding any road position as "DN1 km 27+400".
> **Tagline:** *Baza de date deschisă a drumurilor din România* / *Romania's open road database*
> **Domain:** `borna.ro` is taken. Candidates to check on rotld.ro / your registrar, in order of preference:
> `bornakm.ro` · `borna-km.ro` · `bornarutiera.ro` · `harta-borna.ro` · `borna.eu` · `borna.app` · `borna.info`
> (`bornakm.ro` reads naturally as "bornă km" and is short to say aloud.)

**Status:** personal hobby project. Hosted on free tiers. Built **only from public Romanian and EU data first**. Formal data requests come last, only for gaps the public data can't fill.

---

## Progress (updated 2026-11-19)

**Phases 1–3 done: live at https://bornakm.ro since 2026-11-19.** Next session: the data-list redesign (Next steps 3), then NVDB-style batch 1 (§ "Next steps" below).

| Phase / step | Status | Notes |
|---|---|---|
| 1.1 Scaffold | ✅ | repo, PostGIS in Docker, Makefile, CLAUDE.md |
| 1.2 OSM + Overture | ✅ | Geofabrik extract, Overture transportation (bbox) |
| 1.3 HG 540/2000 register | ✅ | 9,012 rows from the consolidated annexes (08.09.2026); 132/143 official totals match, the rest are errors in the act itself |
| 1.4 TENtec / EuroRegionalMap | ⏸ | TENtec server down (retry); **Romania is not in the open EuroRegionalMap** |
| 1.5 Traffic (AADT) | ◐ | open AADT for the busiest roads (Directive 2002/49/CE data, data.gov.ro); full CESTRIN census is access-restricted → Phase 5 |
| 1.6 GISCO + INS | ✅ | NUTS/LAU boundaries, INS TRN139A road statistics 1990–2025 |
| 2 Linear referencing | ✅ | every register road matched to OSM, km calibrated (county borders, junctions, milestones); held-out milestones: median 12 m, 88% within 50 m |
| 2 Attributes | ✅ | surface, lanes, speed, width, bridges, tunnels, AADT on km ranges with source/date/licence |
| 2 QA | ✅ | `make qa`: register vs INS vs OSM per county, surfaces, gap report |
| 3 Portal | ✅ live | https://bornakm.ro (Cloudflare Pages, auto-deploy from GitHub `hoperise91/borna` main); data on R2 at https://data.bornakm.ro |

**What the portal does now:** map with click/hover on roads, county → road browsing, search incl. `DN1 km 27+400`, road panel and road page (strip diagram, every value with its source), layer modes (category, surface, speed, traffic, width, administrator), background maps (light, dark, detailed, MapTiler terrain + satellite, none), road-type toggles, road-number labels, dashed sections under construction, data and about pages.

**Findings worth knowing:**
- HG 540's motorway list is outdated: A0, A7, A10, DX12 … are taken from OSM and labelled "not in HG 540/2000".
- Open motorway km cross-checked against 130km.ro (2026-11-19): A0, A1, A2, A3, A7, DX12 match. 130km.ro is used only as a check (private site, no reuse terms).
- HG 540 and INS disagree by up to 30% per county (communal roads especially); the portal should show both, labelled.
- OSM barely has road width (~200 tagged stretches): the width layer is mostly an estimate from lanes, labelled as such.

### Next steps
1. ~~Go live~~ ✅ 2026-11-19. Setup: domain bornakm.ro (registrar Nettissimo, DNS on Cloudflare); Pages project `borna` (`borna-6h1.pages.dev`; root `web`, `npm run build`, output `dist`, env `PUBLIC_DATA_URL`, `PUBLIC_MAPTILER_KEY`, `NODE_VERSION=24`); R2 bucket `borna-data` (EEUR) on `data.bornakm.ro`, CORS in `deploy/r2-cors.json` (paste into the dashboard when it changes); data upload `make deploy-data` (R2 keys in `.env`); MapTiler key allows bornakm.ro, www, borna-6h1.pages.dev; Cloudflare Web Analytics (cookieless). Code changes deploy on `git push`; data changes need `make tiles deploy-data`.
2. ~~Weekly automated refresh~~ ✅ 2026-11-19: GitHub Actions every Monday 03:00 UTC; first full run published (test run 10). Checks before publishing, weekly note as a GitHub issue (email), "Updates" list on `/date/`, watch on offline sources, "waiting for official data" list of OSM-only national roads. Servers that refuse CI (Geofabrik at times, legislatie.just.ro, sometimes data.gov.ro) fall back to copies in the private bucket `borna-raw`, refreshed weekly by the Mac helper (`make fetch-install`; skips hotspots/Low Data Mode). Owner wants the email every week for now; switch to notable-only later.
3. **Data-list redesign** (owner's design, 2026-11-19; do before batch 1 so new data types land in it):
   - Hover shows only the value of the current colouring at that spot (`90 km/h`, `asfalt`, `12 400 vehicule/zi`, `drum național`), no road name: the road label is visible elsewhere on the map.
   - The top tabs go; one compact "Colorează harta după" choice remains (only one data type colours the lines at a time).
   - A "Date" list grouped like NVDB (Rețea, Drum, Circulație, Obiecte pe hartă, later Teren): tick any number of data types to show them in the left panel; one radio picks the colouring; point objects (bridges, level crossings, junctions, borders, tolls) are icons that can be on together. Choices remembered in localStorage.
   - Clicking a road: panel shows "La acest punct" (the ticked types' values at the clicked km, each with source and date) and the strip diagrams for the ticked types along the road.
   - Keep it calm: new data types become rows in the list, never new tabs.
4. **NVDB-style attributes, batch 1** (Phase 4.7, all data already open): E-roads, interchanges, level crossings, border crossings and tolls, ferries, DRDP. Then gradient and curves (4.8).
5. Bridges/tunnels as point objects, Mapillary signs, "report an error" link (Phase 4). ~~DN roads missing from HG 540~~ ✅ 2026-11-19: 36 national roads from OSM (incl. Centura Brașov, Făgăraș and Sfântu Gheorghe bypasses); review list in `data/out/lrs/osm_only.csv` (A8/A13/DX6 under construction, Centura Beclean 1.5 km, Brănești bypass tagged secondary, …).
6. Waiting on others (rechecked 2026-11-19: still down): ANCPI orthophoto (0.5 m), geoportal.ancpi.ro has no DNS record at all, so the service may have moved; TENtec, tentec.transport.ec.europa.eu answers 503 → EC "server temporarily unavailable" page; Phase 5 requests (CESTRIN traffic census, widths, bridge inventory).

### Resuming
`make db-up` (PostGIS in Docker keeps all data) · `make web-dev` → http://localhost:4321.
Full rebuild after new data: `make download import register lrs attributes qa tiles` (~10 min). Secrets live in git-ignored files: `.env` (`ERM_TOKEN`), `web/.env` (`PUBLIC_MAPTILER_KEY`).

---

## 0. What we're building

**Goal:** an NVDB-style public portal for Romania. You can look up any road segment and see its official number and class, its owner/administrator, km chainage, surface, lanes, speed limit, AADT, bridges and works. Everything is downloadable and reachable through an API, in Romanian and English.

**Design principles**
1. **Linear referencing first.** Road number + km position is the "primary key" engineers think in. This is what separates Bornă from a pretty OSM map.
2. **Source and date on every value.** Never mix sources without labelling them.
3. **Static first, free hosting.** Pre-built vector tiles and downloads mean no server and no cost.
4. **Bilingual from day one.** Romanian is the default, with English one click away. Hungarian is an option later.

---

## 1. Setup (week 0)

| # | Step | You | Claude helps by |
|---|------|-----|-----------------|
| 1.1 | Pick and register the domain (list above) | Register (~€10/yr) | Checking alternatives, logo brief |
| 1.2 | Create a GitHub account/org and public repo `borna` (MIT for code) | Create account | Scaffolding the whole repo |
| 1.3 | Create a Cloudflare account (Pages + R2, free tier) | Sign up | Deploy config |
| 1.4 | Install the toolchain on your Mac (section 6) | Run the brew command | Troubleshooting |

---

## 2. Public data inventory: what we can use *without asking anyone*

### 2a. The surprise goldmine: the official road register is in the law
**HG 540/2000** (*încadrarea în categorii funcționale a drumurilor publice*) has annexes listing **every national, county (DJ) and communal (DC) road, county by county**. Each entry gives the road number, the route described by its start/end junctions, the **start and end km positions**, and the length. For example, a Suceava communal-road row reads *DC 15B, Brăiești (DN 2E) – gara Lucăcești – Măzănăești (DJ 209C), 0+000 to 2+078*.
- The annexes are amended by many later HGs. Examples: one HG changed the Tulcea county DJ annex (no. 2.38) and set the network's real length to 632.369 km; HG 782/2014 amended the communal-road annexes.
- **Why it matters:** this gives Bornă an *official* list of road numbers, routes and km ranges for DN, DJ and DC, which is exactly what calibrating the km system needs.
- **Licence:** official legislative texts are excluded from copyright under Romanian law (Legea 8/1996, art. 9), so we can reuse them freely. Cite the act.
- **Work:** parse the consolidated text (legislatie.just.ro, "forma consolidată") into a table, then apply the amending HGs that consolidation might have missed.

**Related public sources of the same kind**
- **Public-domain inventories:** the state inventory (HG 1705/2006 and its amendments) for DN sectors, and county council decisions (HCJ) with annexed DJ inventories. Mureș, for example, publishes an annex listing its county roads. Transfer decisions often give exact km and structures. One example lists a road sector of 12.426 km, two bridges at km 1+391 and km 6+089, and a culvert at km 11+434.
- **County regulations and decisions** published as PDFs on CJ websites (weight limits, works, km positions).

### 2b. Geometry and attributes

| Source | What it gives us | Access | Licence | Role |
|---|---|---|---|---|
| **OpenStreetMap** (Geofabrik `romania-latest.osm.pbf`) | Geometry of all roads; `ref` (A1, DN1, DJ103…), surface, lanes, maxspeed, bridges, tunnels, milestones | Daily download | ODbL (share-alike) | **Backbone** |
| **Overture Maps, transportation theme** | A global road network of segments and connectors, built from OSM and enhanced with other data, with speed limits, widths and access restrictions; GeoParquet download by bbox; stable segment IDs (GERS) | Free download | ODbL | Alternative backbone with **stable IDs**; compare with OSM |
| **TENtec (European Commission)** | TEN-T road sections with attributes: core/comprehensive network, corridors, road type, international and national road numbers, section length, status | Public ArcGIS REST service on webgate.ec.europa.eu | EC reuse policy (generally CC BY 4.0; confirm) | Official cross-check for the main network |
| **EuroRegionalMap** (EuroGeographics / Open Maps for Europe) | Topographic open data at 1:250 000 from the national mapping agencies (ANCPI for Romania), including roads with numbers | Download or WFS; access needs a free token | Open licence | Official cross-check of DN/DJ classification |
| **CESTRIN public web maps** (CNAIR) | AADT per national-road sector from the 2022 traffic census; projects, parking/service areas, road status | Public ArcGIS Online maps. Find the feature service URLs in the browser network tab | No licence stated. Publicly released public-sector data is arguably reusable under Legea 179/2022; publish **with attribution and a take-down-on-request policy** | AADT layer, projects |
| **Mapillary** | Street-level imagery and detected traffic signs (speed limits) | API | CC BY-SA | Speed-limit gap filling (later) |

### 2c. Boundaries and statistics

| Source | Use | Licence |
|---|---|---|
| **Eurostat GISCO**: NUTS and LAU (communes) | County/UAT tagging of every segment | Open (Eurostat reuse policy) |
| **ANCPI geoportal (INSPIRE)** | Official admin boundaries, WMS backdrop | Check each dataset |
| **INS Tempo Online, TRN139A** | Road lengths per county and category, split into modernised / light pavement / gravel / earth | Open | QA: compare our lengths and surfaces against official statistics |

---

## 3. Technical architecture

```
             ┌──────────────────── pipeline (GitHub Actions, free for public repos) ──────────────────┐
 OSM / Overture ─► osm2pgsql / duckdb ─┐
 HG 540 annexes ─► parser (PDF/HTML) ──┤
 TENtec / ERM   ─► ogr2ogr ────────────┼─► PostGIS ─► LRS build ─► exports:
 CESTRIN AADT   ─► ArcGIS REST fetch ──┤               (road+km)     • PMTiles (vector tiles)
 GISCO / INS    ─► loaders ────────────┘                             • GPKG / GeoJSON / Parquet per county
                                                                     • road-index JSON (search)
             └────────────────────────────────────────────────────────────────────────────────────────┘
                                          ▼
     Static site (Astro + MapLibre GL JS + PMTiles) ─► Cloudflare Pages (site) + R2 (tiles/downloads)
     /ro /en: map · road search · "DN1 km 27+400" lookup · road pages · downloads · API docs
```

**Free hosting:** Cloudflare Pages (free) + R2 free tier (~10 GB storage, no egress fees; Romania's tiles plus downloads should fit in a few GB) + GitHub Actions. **Running cost: €0 plus the domain.** Live queries later: `pg_featureserv` on a free Oracle Cloud "Always Free" VM. Free-tier limits change, so re-check them at sign-up.

**Stack:** PostgreSQL 16 + PostGIS 3, osm2pgsql (flex), DuckDB (Overture GeoParquet), GDAL, Python 3.12 (`geopandas`, `shapely`, `pdfplumber`), `tippecanoe` → PMTiles, Astro (built-in i18n) + MapLibre GL JS, Protomaps or OpenFreeMap basemap.
**CRS:** store in EPSG:4326; compute lengths and chainage in **EPSG:3844 (Stereo 70)**.

**Core data model (NVDB-like)**
```
road            (road_id, ref 'DJ103', category A|DX|DN|DJ|DC|street, county, route_desc,
                 km_from_official, km_to_official, length_official, legal_source)   ← from HG 540
road_segment    (seg_id, road_id, km_from, km_to, geom, length_m, sequence, km_quality)
attribute_event (event_id, road_id, km_from, km_to, type, value, source, source_date, licence)
                 -- surface | lanes | maxspeed | aadt | width | bridge | tunnel | works | ten_t
point_object    (obj_id, road_id, km, type, props, geom, source, source_date)
source          (source_id, name, url, licence, retrieved_at)
```

---

## 4. Phased plan

### Phase 1: Harvest all public data (weeks 1–3)
1. Repo scaffold: `pipeline/`, `web/`, `data/` (git-ignored), `docs/`, `Makefile`, `docker-compose.yml` (PostGIS).
2. **OSM import** (osm2pgsql flex, roads and road points only) plus a **Overture** download for the Romania bbox.
3. **HG 540/2000 register parser:** consolidated annexes → `road` table (DN + 41 counties' DJ + DC). Then a list of amending HGs and a diff against the consolidated text.
4. **TENtec** roads layer and **EuroRegionalMap** roads for Romania.
5. **CESTRIN AADT 2022** layer from its public feature service (snapshot, with date and attribution).
6. **GISCO** LAU/NUTS boundaries and **INS TRN139A** statistics.
7. Source registry (`source` table) filled in for everything above.

*Exit:* every source in a local PostGIS, each with licence and date.

### Phase 2: Build the reference network (weeks 3–5)
1. Normalise OSM `ref` (split "DN1;E60", classify, flag missing refs).
2. **Match each HG 540 road to geometry:** use the route endpoints (the junctions with other DN/DJ roads and the named localities) to pick and stitch OSM ways.
3. **Calibrate km:** official km_from/km_to from HG 540 at the ends, OSM milestones and CESTRIN sector boundaries as interior control points, interpolation in Stereo 70. Report `km_quality` per segment.
4. **Gap report:** HG 540 roads missing in OSM, OSM refs not in HG 540, and length differences above 5 %. This is also a useful contribution back to the OSM Romania community.
5. QA against INS lengths and surfaces per county; publish the differences.

*Exit:* "DN1 km 27.4" and "DJ103 km 5.2" resolve within ±50 m on a test set of ~30 known points.

### Phase 3: Portal MVP (weeks 5–8)
1. `tippecanoe` → `borna.pmtiles` (A/DN from z5, DJ from z9, DC/streets from z12).
2. Astro site, RO/EN:
   - `/` map with layer toggles (category, surface, speed, AADT, TEN-T)
   - `/drum/DJ103` road page: official route, length (official vs measured), counties, km strip diagram
   - `/cauta?q=DN1 km 27+400` position lookup
   - `/date` per-county downloads + changelog
   - `/despre` sources, licences, methodology, error reporting
3. Segment panel: value · source · date · licence for every attribute.
4. Mobile-friendly and accessible; cookieless analytics (Umami / Plausible free tier).
5. Deploy to Cloudflare Pages + R2.

*Exit:* public beta.

### Phase 4: Depth and community (weeks 8–12)
1. Weekly automated refresh (GitHub Actions) with a data changelog.
2. Read-only API: static JSON on R2 first, `pg_featureserv` on a free VM later.
3. Bridges/tunnels/level crossings from OSM + public HCJ/HG inventories.
4. Mapillary speed-limit signs where OSM lacks `maxspeed`.
5. Error reports → GitHub issues; fixes flow back to OSM.
6. Allies: the OSM Romania community, Code for Romania, Asociația Pro Infrastructură, university road departments.
7. **NVDB-style attributes from open data, batch 1** (small; new rows on the road page and point markers on the map, each with source/date/licence):
   - E-roads (*Europaväg*): OSM `network=e-road` route relations (30 in Romania), checked against the UNECE AGR list.
   - Interchanges (*Trafikplats*): OSM `motorway_junction` (436, with number and name), km on A/DX.
   - Level crossings (*Järnvägskorsning*): OSM, 9,609 already in `raw.osm_road_points`.
   - Border crossings and toll points: OSM, 146 + 23 already imported.
   - Ferries (*Färjeled*): OSM `route=ferry` (Danube crossings), linked to the roads they join.
   - Regional administrator: the CNAIR DRDP managing each DN, from CNAIR's published organisation.
8. **NVDB-style attributes, batch 2** (medium): gradient and height profile (*Lutning*) from Copernicus DEM GLO-30 (free, attribution) along each road; curves (*Kurvatur*) from our own geometry; built-up stretches (*Tättbebyggt område*) from GISCO LAU crossings + OSM `maxspeed:type=RO:urban`.
9. **Thin in OSM today, revisit with Mapillary** (open sign detections, CC BY-SA): one-way (46% of main roads tagged, 2026-11-19), lighting (10%), sidewalks (12%), weight/axle/height limits (≤2%), no-overtaking (0.3%). OSM `smoothness` is on 78% but is a mapper's judgement: show it only labelled as such, never as measured condition.
10. **Not open in Romania** (Phase 5 requests): full traffic census (CESTRIN), bridge inventory with load classes, winter maintenance classes, carriageway widths, accident locations (only county totals are public). TEN-T comes back with TENtec (on the weekly watch).

### Phase 5: Formal data requests (only for the remaining gaps)
Done only once Phases 1–4 have shown exactly what's missing. Likely candidates: BDTR attributes (width, pavement structure), the full bridge inventory, AADT for DJ roads, and the 2026 census results.
- Levers: Legea 544/2001 (answer within 10/30 days), Legea 179/2022 (open data), Reg. (EU) 2023/138 (High-Value Datasets, applicable since June 2024), Delegated Reg. (EU) 2022/670 (NAP static road data), INSPIRE.
- By then you'll have a live portal to show, which makes the request (and any partnership offer to CESTRIN) far more persuasive. Draft letter in Appendix A.

---

## 5. Licensing
- **Code:** MIT.
- **OSM/Overture-derived road layer:** **ODbL** (mandatory share-alike).
- **HG 540 register:** public (official acts); publish as a separate CSV.
- **Other official layers (TENtec, ERM, CESTRIN):** separate files under their original terms, credited.
- **Map attribution:** "© OpenStreetMap contributors (ODbL) · Overture Maps · CNAIR/CESTRIN · EuroGeographics · EC TENtec · Eurostat GISCO · Bornă".

---

## 6. Running this with Claude in the terminal (Claude Code)
1. Prerequisites: Docker Desktop, Homebrew, then
   `brew install gdal osm2pgsql tippecanoe node python@3.12 duckdb`
2. `mkdir borna && cd borna`, save this file as `docs/ROADMAP.md`, run `claude`.
3. First prompt:
   > Read docs/ROADMAP.md. Scaffold Phase 1 step 1: repo structure, docker-compose with PostGIS 16, a Makefile with targets `download`, `import`, `register`, `lrs`, `tiles`, `web-dev`, and a CLAUDE.md capturing the conventions (EPSG:3844 for lengths, source/date/licence on every attribute, RO default + EN, public data only). Stop after scaffolding and show me the tree.
4. Then one step at a time ("Do Phase 1 step 3, the HG 540 parser"), committing after each.
5. Keep `tests/lrs_checkpoints.csv` (road, km, lat, lon, note) under version control as the quality gate. Seed it with roads you know in Covasna.

---

## 7. Timeline

| Week | Milestone |
|---|---|
| 0 | Domain, accounts, toolchain |
| 1–3 | All public sources harvested (OSM, Overture, HG 540, TENtec, ERM, CESTRIN, GISCO, INS) |
| 3–5 | Official register matched to geometry; km lookup working; gap report |
| 5–8 | Bilingual public beta live, free hosting |
| 8–12 | Refresh automation, API, bridges, community |
| 12+ | Targeted data requests for the remaining gaps |

At ~6–10 h/week with Claude. The main risks are the HG 540 parsing (scanned or inconsistent annexes, scattered amendments) and the km calibration.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| HG 540 annexes outdated or inconsistent across amendments | Track the amending HGs; flag conflicts with OSM/INS; show "official as of <act>" |
| CESTRIN objects to republication | Attribution, a take-down-on-request policy, link-out fallback; formal licence request in Phase 5 |
| Weak OSM `ref` and milestone coverage | "Estimated chainage" flag; gap report shared with OSM RO |
| Scope creep | Phase gates; v1 = register + network + km + basic attributes |

---

## Appendix A — Draft data request (for Phase 5, not now)

> **Către:** Compania Națională de Administrare a Infrastructurii Rutiere S.A. — Centrul de Studii Tehnice Rutiere și Informatică (CESTRIN)
> **Subiect:** Solicitare de informații de interes public și de reutilizare a datelor (Legea nr. 544/2001 și Legea nr. 179/2022)
>
> Stimată doamnă / Stimate domn,
>
> În temeiul Legii nr. 544/2001 privind liberul acces la informațiile de interes public și al Legii nr. 179/2022 privind datele deschise și reutilizarea informațiilor din sectorul public, vă rog să-mi comunicați, în format electronic prelucrabil automat (de ex. GeoPackage, Shapefile, CSV), următoarele:
>
> 1. Rețeaua de drumuri naționale și autostrăzi, cu pozițiile kilometrice de început și sfârșit ale sectoarelor, așa cum sunt înregistrate în Baza de Date Tehnico-Rutieră (BDTR);
> 2. Intensitatea medie zilnică anuală (MZA) pe sectoare de drum, rezultată din Recensământul General de Circulație 2026, după finalizarea prelucrării;
> 3. Inventarul podurilor și pasajelor de pe drumurile naționale (identificator, drum, poziție kilometrică, lungime, an construcție, după caz);
> 4. Lista seturilor de date publicate sau planificate pentru publicare prin Punctul Național de Acces, conform Regulamentului delegat (UE) 2022/670.
>
> De asemenea, vă rog să precizați condițiile de reutilizare (licența) aplicabile datelor afișate în aplicațiile web-GIS publice ale CESTRIN, pe care le reutilizăm, cu atribuire, în portalul public și gratuit [domeniu].
>
> Doresc să primesc răspunsul în format electronic la adresa: [email].
>
> Cu stimă,
> [Nume], [data]

*Variant for county councils:* ask for the inventory of county and communal roads with surface type and administrator, and AADT where available.

---

## Appendix B — Next actions
See **Progress → Next steps** at the top. (Toolchain installed and Claude Code set up on 2026-11-18.)
