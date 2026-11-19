"""Phase 4.1: weekly refresh: compare the new export with the published one, check it, report.

Usage: python -m borna.refresh [--previous URL]    (after `make tiles`; default URL: the live data)

Reads web/public/data/ (just built) and the published meta/summary.json + changes.json.
Writes data/out/refresh/report.md (the weekly note) and data/out/refresh/status
("published" or "held"). Only when every check passes does it also write the new
meta/summary.json and changes.json into web/public/data/, so `make deploy-data` publishes them.
Exit code 0 = publish, 3 = held back (checks failed, keep last week's data online).
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import date

import requests

from borna.config import DATA_OUT
from borna.tiles import WEB_DATA

LIVE_DATA = "https://data.bornakm.ro"
OUT = DATA_OUT / "refresh"
HISTORY_KEEP = 104  # weeks of changes kept in changes.json (two years)

# Checks. A run that breaks one is held back, not published.
CHECKPOINT_MAX_M = 50          # every public checkpoint (tests/lrs_checkpoints.csv)
HOLDOUT_SHARE_DROP = 0.05      # held-out milestones within 50 m may fall at most 5 points
HOLDOUT_MEDIAN_MAX_M = 25
ROAD_COUNT_DROP = 0.01         # at most 1% of roads may disappear in a week
CATEGORY_KM_DROP = 0.02        # mapped km per category (A, DX, DN) may fall at most 2%
MAIN_ROAD_DROP_KM = 5          # an A/DX road losing more than 5 km and 10% is suspicious
MAIN_ROAD_DROP_SHARE = 0.10
NOTABLE_KM = 1.0               # A/DX/DN length changes reported in the note
MAIN = ("A", "DX")
NATIONAL = ("A", "DX", "DN")


def summarize(web_data=WEB_DATA, lrs_out=DATA_OUT / "lrs") -> dict:
    """Compact fingerprint of one export: per road its category, mapped km and file hash."""
    roads = {}
    for f in sorted((web_data / "roads").glob("*.json")):
        raw = f.read_bytes()
        d = json.loads(raw)
        roads[d["key"]] = {
            "ref": d["ref"], "county": d["county"], "cat": d["category"],
            "status": d["lrs"].get("status"), "km": round(d["lrs"].get("path_km") or 0, 3),
            "hash": hashlib.md5(raw).hexdigest()[:12],
        }
    checkpoints = []
    report = lrs_out / "checkpoints.csv"
    if report.exists():
        with open(report, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["file"] == "lrs_checkpoints.csv":  # private QA points never leave the machine
                    err = row["error_m"]
                    checkpoints.append({"road": row["road"], "km": row["km"],
                                        "error_m": float(err) if err else None})
    sources = {s["id"]: s["version"] for s in json.loads((web_data / "sources.json").read_text())}
    return {
        "date": date.today().isoformat(),
        "sources": sources,
        "accuracy": json.loads((web_data / "accuracy.json").read_text()),
        "checkpoints": checkpoints,
        "roads": roads,
    }


def _km_by_cat(s: dict) -> dict:
    out: dict[str, float] = {}
    for r in s["roads"].values():
        out[r["cat"]] = out.get(r["cat"], 0) + r["km"]
    return out


def compare(prev: dict | None, cur: dict) -> dict:
    """What changed since the previous published export."""
    roads = cur["roads"]
    if prev is None:
        return {"baseline": True, "roads": len(roads)}
    old = prev["roads"]
    added = sorted(set(roads) - set(old))
    removed = sorted(set(old) - set(roads))
    changed = sorted(k for k in set(roads) & set(old) if roads[k]["hash"] != old[k]["hash"])
    length = []
    for k in changed:
        a, b = old[k], roads[k]
        if b["cat"] in NATIONAL and abs(b["km"] - a["km"]) >= NOTABLE_KM:
            length.append({"key": k, "from": a["km"], "to": b["km"]})
    status = [{"key": k, "from": old[k]["status"], "to": roads[k]["status"]}
              for k in changed if old[k]["status"] != roads[k]["status"]]
    sources = {k: {"from": prev["sources"].get(k), "to": v}
               for k, v in cur["sources"].items() if prev["sources"].get(k) != v}
    for k in set(prev["sources"]) - set(cur["sources"]):
        sources[k] = {"from": prev["sources"][k], "to": None}
    return {
        "baseline": False, "roads": len(roads), "since": prev["date"],
        "added": [{"key": k, "cat": roads[k]["cat"], "km": roads[k]["km"]} for k in added],
        "removed": [{"key": k, "cat": old[k]["cat"]} for k in removed],
        "changed": len(changed), "length": length, "status": status, "sources": sources,
    }


def check(prev: dict | None, cur: dict) -> list[str]:
    """Reasons to hold this export back; empty when it is fit to publish."""
    problems = []
    for cp in cur["checkpoints"]:
        if cp["error_m"] is None or cp["error_m"] > CHECKPOINT_MAX_M:
            got = "not located" if cp["error_m"] is None else f"{cp['error_m']:.0f} m off"
            problems.append(f"checkpoint {cp['road']} km {cp['km']}: {got} (limit {CHECKPOINT_MAX_M} m)")
    acc = cur["accuracy"]
    if acc.get("median_m") is not None and acc["median_m"] > HOLDOUT_MEDIAN_MAX_M:
        problems.append(f"held-out milestones: median error {acc['median_m']} m "
                        f"(limit {HOLDOUT_MEDIAN_MAX_M} m)")
    if prev is None:
        return problems
    pacc = prev["accuracy"]
    if acc.get("within_50m_share", 0) < pacc.get("within_50m_share", 0) - HOLDOUT_SHARE_DROP:
        problems.append(f"held-out milestones within 50 m fell from {pacc['within_50m_share']:.1%} "
                        f"to {acc['within_50m_share']:.1%}")
    n_old, n_new = len(prev["roads"]), len(cur["roads"])
    if n_new < n_old * (1 - ROAD_COUNT_DROP):
        problems.append(f"road count fell from {n_old:,} to {n_new:,}")
    km_old, km_new = _km_by_cat(prev), _km_by_cat(cur)
    for cat in NATIONAL:
        a, b = km_old.get(cat, 0), km_new.get(cat, 0)
        if a and b < a * (1 - CATEGORY_KM_DROP):
            problems.append(f"{cat} roads: mapped length fell from {a:,.1f} to {b:,.1f} km")
    for k, a in prev["roads"].items():
        if a["cat"] not in MAIN:
            continue
        b = cur["roads"].get(k)
        if b is None:
            problems.append(f"{k} disappeared")
        elif a["km"] - b["km"] > MAIN_ROAD_DROP_KM and b["km"] < a["km"] * (1 - MAIN_ROAD_DROP_SHARE):
            problems.append(f"{k}: mapped length fell from {a['km']:.1f} to {b['km']:.1f} km")
    return problems


def _km(x: float) -> str:
    return f"{x:,.1f} km"


def report(cur: dict, changes: dict, problems: list[str], run_url: str | None) -> str:
    """The weekly note (Markdown, English: it goes to the maintainer)."""
    held = bool(problems)
    lines = [(f"**{'Held back' if held else 'Published'}**: OpenStreetMap data from "
             f"{cur['sources'].get('osm', '?')} · {changes['roads']:,} roads"), ""]
    if held:
        lines += [("The checks below failed, so **last week's data stays online**. "
                  "Nothing on bornakm.ro changed."), ""]
        lines += [f"- {p}" for p in problems] + [""]
    if changes["baseline"]:
        lines += ["First run: this export is the baseline for next week's comparison.", ""]
    else:
        lines.append(f"### Changes since {changes['since']}")
        if not (changes["added"] or changes["removed"] or changes["changed"] or changes["sources"]):
            lines.append("No changes.")
        for r in changes["added"]:
            lines.append(f"- New: **{r['key']}** ({_km(r['km'])})")
        for r in changes["removed"]:
            lines.append(f"- Gone: **{r['key']}**")
        for r in changes["length"]:
            d = r["to"] - r["from"]
            lines.append(f"- {r['key']}: {_km(r['from'])} → {_km(r['to'])} ({d:+.1f} km)")
        for r in changes["status"]:
            lines.append(f"- {r['key']}: network status {r['from']} → {r['to']}")
        for k, v in sorted(changes["sources"].items()):
            lines.append(f"- Source {k}: {v['from'] or 'none'} → {v['to'] or 'not loaded'}")
        if changes["changed"]:
            lines.append(f"- {changes['changed']:,} road files changed in total")
        lines.append("")
    acc = cur["accuracy"]
    ok = sum(1 for c in cur["checkpoints"] if c["error_m"] is not None
             and c["error_m"] <= CHECKPOINT_MAX_M)
    lines += ["### Checks",
              f"- Checkpoints: {ok}/{len(cur['checkpoints'])} within {CHECKPOINT_MAX_M} m",
              (f"- Held-out milestones: median {acc.get('median_m')} m, "
              f"{acc.get('within_50m_share', 0):.1%} within 50 m")]
    km = _km_by_cat(cur)
    lines.append("- Mapped length: " + " · ".join(f"{c} {_km(km.get(c, 0))}" for c in NATIONAL))
    if run_url:
        lines += ["", f"[Run log]({run_url})"]
    return "\n".join(lines) + "\n"


def history_entry(cur: dict, changes: dict) -> dict:
    """One week in changes.json, shown on the site's data page (/date/)."""
    if changes["baseline"]:
        return {"date": cur["date"], "osm": cur["sources"].get("osm"), "roads": changes["roads"],
                "baseline": True}
    return {
        "date": cur["date"], "osm": cur["sources"].get("osm"), "roads": changes["roads"],
        "added": [r["key"] for r in changes["added"]],
        "removed": [r["key"] for r in changes["removed"]],
        "length": changes["length"], "changed": changes["changed"],
        "sources": {k: v["to"] for k, v in changes["sources"].items()},
    }


def _fetch_json(url: str):
    # A fresh query string skips Cloudflare's edge cache, so we compare with what was uploaded.
    r = requests.get(url, params={"t": int(time.time())}, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="borna.refresh")
    ap.add_argument("--previous", default=LIVE_DATA, help="base URL of the published data")
    ap.add_argument("--run-url", help="link to the CI run, for the note")
    args = ap.parse_args(argv)

    cur = summarize()
    prev = _fetch_json(f"{args.previous}/meta/summary.json")
    history = _fetch_json(f"{args.previous}/changes.json") or []
    changes = compare(prev, cur)
    problems = check(prev, cur)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.md").write_text(report(cur, changes, problems, args.run_url), encoding="utf-8")
    (OUT / "status").write_text("held\n" if problems else "published\n")
    print((OUT / "report.md").read_text())
    if problems:
        return 3

    (WEB_DATA / "meta").mkdir(exist_ok=True)
    (WEB_DATA / "meta" / "summary.json").write_text(json.dumps(cur, separators=(",", ":")))
    history = [h for h in history if h["date"] != cur["date"]]  # a re-run replaces the same day
    history.insert(0, history_entry(cur, changes))
    (WEB_DATA / "changes.json").write_text(
        json.dumps(history[:HISTORY_KEEP], indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
