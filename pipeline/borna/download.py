"""Phase 1: fetch public sources into data/raw/<source_id>/.

Usage: python -m borna.download [source ...]    (default: all)
Each download is skipped when the local copy already matches the published version.
"""

import hashlib
import re
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime

import duckdb
import requests

from borna import sources
from borna.config import RO_BBOX

GEOFABRIK_URL = "https://download.geofabrik.de/europe/romania-latest.osm.pbf"
OVERTURE_STAC = "https://stac.overturemaps.org/catalog.json"
OVERTURE_S3 = "s3://overturemaps-us-west-2/release/{release}/theme=transportation/type={type}/*"
LEGIS = "https://legislatie.just.ro/Public/"
HG540_DOC_ID = 23370  # HG 540/2000, base act; its consolidations and annexes are separate documents


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


def _legis_get(path: str) -> str:
    r = requests.get(LEGIS + path, headers={"User-Agent": "borna-pipeline"}, timeout=300)
    r.raise_for_status()
    return r.text


def download_hg540() -> None:
    # The base act's page lists every consolidation ("Consolidarea din DD.MM.YYYY"); take the newest.
    page = _legis_get(f"DetaliiDocumentAfis/{HG540_DOC_ID}")
    consolidations = {
        datetime.strptime(d, "%d.%m.%Y").date(): doc_id
        for d, doc_id in re.findall(r"Consolidarea din ([\d.]{10})'[^>]*href='[^']*DetaliiDocument/(\d+)'", page)
    }
    if not consolidations:
        raise RuntimeError("hg540: no consolidations found on legislatie.just.ro, page layout changed?")
    date = max(consolidations)
    current = sources.read_manifest("hg540")
    if sources.files_present(current) and current["version"] == date.isoformat():
        print(f"hg540: up to date (forma consolidată {date:%d.%m.%Y})")
        return

    consolidated = _legis_get(f"DetaliiDocument/{consolidations[date]}")
    m = re.search(r'DetaliiDocumentAfis/(\d+)">ANEXE', consolidated)
    if not m:
        raise RuntimeError("hg540: annex link not found in the consolidated text")
    annex_url = LEGIS + f"DetaliiDocumentAfis/{m.group(1)}"
    print(f"hg540: fetching annexes, forma consolidată {date:%d.%m.%Y} (~11 MB)…", flush=True)
    out = sources.raw_dir("hg540") / "anexe.html"
    out.write_text(_legis_get(f"DetaliiDocumentAfis/{m.group(1)}"), encoding="utf-8")

    sources.write_manifest(
        "hg540",
        name="HG 540/2000, anexele 1-4 (încadrarea în categorii funcționale a drumurilor publice)",
        url=annex_url,
        licence="public domain (official act, Legea 8/1996 art. 9)",
        attribution=f"HG 540/2000, forma consolidată {date:%d.%m.%Y}, legislatie.just.ro",
        version=date.isoformat(),
        files=[out.name],
        consolidated_doc_url=LEGIS + f"DetaliiDocument/{consolidations[date]}",
    )
    print(f"hg540: saved {out.name}")


SOURCES = {"osm": download_osm, "overture": download_overture, "hg540": download_hg540}


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
