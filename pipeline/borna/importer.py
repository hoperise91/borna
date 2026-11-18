"""Phase 1: load data/raw/ into PostGIS (raw schema) and register each source in borna.source.

Usage: python -m borna.importer [source ...]    (default: all)
Every import replaces its raw.* tables.
"""

import subprocess
import sys

import duckdb
import psycopg

from borna import sources
from borna.config import CRS_STORAGE, DATA_RAW, PG_DSN, ROOT

OSM_STYLE = ROOT / "pipeline" / "osm2pgsql" / "roads.lua"


def _require(source_id: str) -> dict:
    m = sources.read_manifest(source_id)
    if not sources.files_present(m):
        raise SystemExit(f"{source_id}: no download found, run `make download SOURCES={source_id}`")
    return m


def import_osm(conn) -> dict:
    m = _require("osm")
    subprocess.run(
        ["osm2pgsql", "--create", "--output=flex", f"--style={OSM_STYLE}",
         "--schema=raw", f"--database={PG_DSN}", str(DATA_RAW / "osm" / m["files"][0])],
        check=True,
    )
    return m


def import_overture(conn) -> dict:
    m = _require("overture")
    con = duckdb.connect()
    con.execute("INSTALL postgres; LOAD postgres; INSTALL spatial; LOAD spatial")
    con.execute(f"ATTACH '{PG_DSN}' AS pg (TYPE postgres)")

    for type_, geom_type in (("segment", "LineString"), ("connector", "Point")):
        table = f"raw.overture_{type_}"
        path = DATA_RAW / "overture" / f"{type_}.parquet"
        # Nested columns go over as JSON text and geometry as hex WKB, then get proper
        # PostGIS types below. Driven by the file's own schema so new Overture columns pass through.
        cols, json_cols = [], []
        for name, type_str, *_ in con.execute(f"DESCRIBE SELECT * FROM '{path}'").fetchall():
            if name == "bbox":
                continue
            if type_str.startswith("GEOMETRY"):
                cols.append(f"ST_AsHEXWKB({name}) AS geom")
            elif type_str.startswith(("STRUCT", "MAP")) or type_str.endswith("]"):
                cols.append(f'to_json("{name}")::VARCHAR AS "{name}"')
                json_cols.append(name)
            else:
                cols.append(f'"{name}"')

        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        print(f"overture: loading {path.name} into {table}…", flush=True)
        con.execute(f"CREATE TABLE pg.{table} AS SELECT {', '.join(cols)} FROM '{path}'")

        alters = [f'ALTER COLUMN "{c}" TYPE jsonb USING "{c}"::jsonb' for c in json_cols]
        alters.append(f"ALTER COLUMN geom TYPE geometry({geom_type}, {CRS_STORAGE}) "
                      f"USING ST_SetSRID(geom::geometry, {CRS_STORAGE})")
        conn.execute(f"ALTER TABLE {table} {', '.join(alters)}")
        conn.execute(f"ALTER TABLE {table} ADD PRIMARY KEY (id)")
        conn.execute(f"CREATE INDEX ON {table} USING gist (geom)")
        conn.execute(f"ANALYZE {table}")
        conn.commit()
    return m


SUMMARY_SQL = {
    "osm": """
        SELECT 'raw.osm_roads' AS "table", count(*) AS rows,
               count(*) FILTER (WHERE ref IS NOT NULL) AS with_ref FROM raw.osm_roads
        UNION ALL SELECT 'raw.osm_road_points', count(*),
               count(*) FILTER (WHERE kind = 'milestone') FROM raw.osm_road_points
        UNION ALL SELECT 'raw.osm_road_routes', count(*),
               count(*) FILTER (WHERE ref IS NOT NULL) FROM raw.osm_road_routes
    """,
    "overture": """
        SELECT 'raw.overture_segment' AS "table", count(*) AS rows,
               count(*) FILTER (WHERE routes IS NOT NULL) AS with_ref FROM raw.overture_segment
        UNION ALL SELECT 'raw.overture_connector', count(*), NULL FROM raw.overture_connector
    """,
}

SOURCES = {"osm": import_osm, "overture": import_overture}


def main(argv: list[str]) -> int:
    names = argv or list(SOURCES)
    unknown = set(names) - set(SOURCES)
    if unknown:
        print(f"unknown source(s): {', '.join(sorted(unknown))}; known: {', '.join(SOURCES)}",
              file=sys.stderr)
        return 2
    with psycopg.connect(PG_DSN) as conn:
        for name in names:
            manifest = SOURCES[name](conn)
            sources.register(conn, manifest)
            conn.commit()
            print(f"{name}: registered in borna.source (version {manifest['version']})")
            for row in conn.execute(SUMMARY_SQL[name]).fetchall():
                print(f"  {row[0]:<24} {row[1]:>10,}  {'' if row[2] is None else f'({row[2]:,} ref/milestone)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
