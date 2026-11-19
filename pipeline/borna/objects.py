"""Phase 4.7: point objects on the network (borna.point_object).

OSM nodes already imported into raw.osm_road_points, placed on the nearest Bornă road and its km:
  - level_crossing  railway=level_crossing (road × railway)
  - junction        highway=motorway_junction (exit number `ref`, name)
  - border          barrier=border_control (border crossing points)
  - toll            barrier=toll_booth

A node is kept when a road's centreline passes within ON_ROAD_M; when several roads do (a level
crossing at a junction), the most important category wins. Every object keeps source, date and
licence. Run after `make lrs`; re-running replaces the OSM objects.
"""

import json
import sys

import psycopg
from shapely import wkb

from borna import sources
from borna.attributes import load_roads
from borna.config import CRS_METRIC, PG_DSN

ON_ROAD_M = 30
KINDS = {  # raw.osm_road_points.kind -> point_object.type
    "level_crossing": "level_crossing",
    "motorway_junction": "junction",
    "border_control": "border",
    "toll_booth": "toll",
}
RANK = {c: i for i, c in enumerate(["A", "DX", "DN", "V", "DJ", "DC", "DP"])}


def main() -> int:
    manifest = sources.read_manifest("osm")
    if not manifest:
        print("objects: no OSM download", file=sys.stderr)
        return 1
    with psycopg.connect(PG_DSN) as conn:
        roads, _ = load_roads(conn)
        category = dict(conn.execute("SELECT road_id, category FROM borna.road").fetchall())
        rows, skipped = [], 0
        for osm_id, kind, ref, tags, g, cands in conn.execute(f"""
                SELECT p.osm_id, p.kind, p.ref, p.tags, ST_AsBinary(ST_Transform(p.geom, {CRS_METRIC})),
                       ARRAY(SELECT DISTINCT s.road_id FROM borna.road_segment s
                             -- index prefilter (0.0006° ≥ 46 m here), then the exact metric distance
                             WHERE s.geom && ST_Expand(p.geom, 0.0006)
                               AND ST_DWithin(ST_Transform(s.geom, {CRS_METRIC}),
                                              ST_Transform(p.geom, {CRS_METRIC}), {ON_ROAD_M}))
                FROM raw.osm_road_points p WHERE p.kind = ANY(%s)""", (list(KINDS),)):
            if not cands:
                skipped += 1
                continue
            pt = wkb.loads(bytes(g))
            best = min(cands, key=lambda rid: (RANK.get(category[rid], 9),
                                               roads[rid].measure(pt)[1]))
            km, _ = roads[best].measure(pt)
            props = {k: v for k, v in {
                "name": tags.get("name"), "ref": ref or tags.get("ref"), "osm_id": osm_id,
                "barrier": tags.get("crossing:barrier"), "operator": tags.get("operator"),
            }.items() if v}
            rows.append((best, round(km, 3), KINDS[kind], json.dumps(props, ensure_ascii=False),
                         osm_id))
        conn.execute("DELETE FROM borna.point_object WHERE source_id = 'osm'")
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO borna.point_object (road_id, km, type, props, geom, source_id, source_date, licence)
                SELECT %s, %s, %s, %s::jsonb, p.geom, 'osm', %s, %s
                FROM raw.osm_road_points p WHERE p.osm_id = %s""",
                [(rid, km, typ, props, manifest["version"], manifest["licence"], osm_id)
                 for rid, km, typ, props, osm_id in rows])
        conn.commit()
        summary = conn.execute("""
            SELECT type, count(*), count(DISTINCT road_id) FROM borna.point_object
            WHERE source_id = 'osm' GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    for typ, n, nroads in summary:
        print(f"objects: {typ:<15}{n:>7,} on {nroads:,} roads")
    print(f"objects: {skipped:,} nodes not within {ON_ROAD_M} m of a Bornă road (left out)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
