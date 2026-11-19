#!/bin/bash
# Weekly fetch helper (runs on the owner's Mac via launchd, see deploy/ro.bornakm.fetch.plist).
# Some public servers refuse CI machines (Geofabrik at times, legislatie.just.ro always), so the
# Mac downloads fresh OpenStreetMap + HG 540 once a week and saves them to the private R2 bucket;
# the GitHub weekly refresh uses these copies when a server refuses it.
# launchd starts this every few hours; it does the work at most once every 6 days.
set -euo pipefail
cd "$(dirname "$0")/.."
stamp=data/out/fetch/last_success
log=data/out/fetch/fetch.log
mkdir -p data/out/fetch
if [ -f "$stamp" ] && [ -z "$(find "$stamp" -mtime +6)" ]; then
  exit 0   # fetched less than 6 days ago
fi
{
  echo "=== $(date '+%F %T') weekly fetch"
  make download SOURCES="osm hg540"
  make snapshot-raw
  touch "$stamp"
  echo "=== done"
} >> "$log" 2>&1
