"""Phase 1: fetch public sources into data/raw/<source_id>/.

Usage: python -m borna.download [source ...]    (default: all)
Each download is skipped when the local copy already matches the published version.
"""

import hashlib
import sys
from email.utils import parsedate_to_datetime

import duckdb
import requests

from borna import sources
from borna.config import RO_BBOX

GEOFABRIK_URL = "https://download.geofabrik.de/europe/romania-latest.osm.pbf"
OVERTURE_STAC = "https://stac.overturemaps.org/catalog.json"
OVERTURE_S3 = "s3://overturemaps-us-west-2/release/{release}/theme=transportation/type={type}/*"


def _md5(path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_osm() -> None:
    out = sources.raw_dir("osm") / "romania-latest.osm.pbf"
    remote_md5 = requests.get(GEOFABRIK_URL + ".md5", timeout=30).text.split()[0]
    current = sources.read_manifest("osm")
    if sources.files_present(current) and current.get("md5") == remote_md5:
        print(f"osm: up to date ({current['version']})")
        return

    tmp = out.with_suffix(".part")
    with requests.get(GEOFABRIK_URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        data_date = parsedate_to_datetime(r.headers["Last-Modified"]).date().isoformat()
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\rosm: {done / total:6.1%} of {total / 1e6:.0f} MB", end="", flush=True)
    print()
    if _md5(tmp) != remote_md5:
        tmp.unlink()
        raise RuntimeError("osm: md5 mismatch, download corrupted")
    tmp.rename(out)

    sources.write_manifest(
        "osm",
        name="OpenStreetMap (Geofabrik Romania extract)",
        url=GEOFABRIK_URL,
        licence="ODbL-1.0",
        attribution="© OpenStreetMap contributors",
        version=data_date,
        files=[out.name],
        md5=remote_md5,
    )
    print(f"osm: saved {out.name} ({data_date})")


def download_overture() -> None:
    release = requests.get(OVERTURE_STAC, timeout=30).json()["latest"]
    current = sources.read_manifest("overture")
    if sources.files_present(current) and current["version"] == release:
        print(f"overture: up to date ({release})")
        return

    out_dir = sources.raw_dir("overture")
    xmin, ymin, xmax, ymax = RO_BBOX
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2'")

    files = []
    for type_, where in (("segment", "subtype = 'road'"), ("connector", "TRUE")):
        out = out_dir / f"{type_}.parquet"
        tmp = out.with_suffix(".part")
        print(f"overture: fetching {type_}s for the Romania bbox (release {release})…", flush=True)
        con.execute(f"""
            COPY (
                SELECT * EXCLUDE (theme, type)
                FROM read_parquet('{OVERTURE_S3.format(release=release, type=type_)}', hive_partitioning = 1)
                WHERE bbox.xmin <= {xmax} AND bbox.xmax >= {xmin}
                  AND bbox.ymin <= {ymax} AND bbox.ymax >= {ymin}
                  AND {where}
            ) TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)
        """)
        tmp.rename(out)
        n = con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0]
        print(f"overture: {type_}.parquet, {n:,} rows")
        files.append(out.name)

    sources.write_manifest(
        "overture",
        name="Overture Maps, transportation theme",
        url=f"https://docs.overturemaps.org/release/{release}/",
        licence="ODbL-1.0",
        attribution="© OpenStreetMap contributors, Overture Maps Foundation",
        version=release,
        files=files,
        bbox=list(RO_BBOX),
    )


SOURCES = {"osm": download_osm, "overture": download_overture}


def main(argv: list[str]) -> int:
    names = argv or list(SOURCES)
    unknown = set(names) - set(SOURCES)
    if unknown:
        print(f"unknown source(s): {', '.join(sorted(unknown))}; known: {', '.join(SOURCES)}",
              file=sys.stderr)
        return 2
    for name in names:
        SOURCES[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
