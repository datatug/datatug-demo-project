#!/usr/bin/env bash
# Refresh demo-project-1/data/geo from a geo-ingitdb checkout.
#
#   scripts/sync-geo-data.sh [GEO_INGITDB_DIR]
#
# Copies the three collections the hero query needs (countries, population_wb,
# country_aliases) and writes a root-collections file listing only them. The
# World Bank records carry their own provenance (indicator, source_url,
# fetched_at); geo-ingitdb Git history is the snapshot history.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
geo="${1:-${GEO_INGITDB_DIR:-$root/../../ingitdb/geo-ingitdb}}"
dest="$root/demo-project-1/data/geo"

collections=(countries population_wb country_aliases)
for c in "${collections[@]}"; do
  [ -d "$geo/$c/\$records" ] || { echo "sync-geo-data: $geo/$c/\$records not found (pass the geo-ingitdb checkout)" >&2; exit 1; }
done

rm -rf "$dest"
mkdir -p "$dest/.ingitdb"
cp "$geo/.ingitdb/settings.yaml" "$dest/.ingitdb/settings.yaml"
: > "$dest/.ingitdb/root-collections.yaml"
for c in "${collections[@]}"; do
  mkdir -p "$dest/$c"
  cp -R "$geo/$c/.collection" "$dest/$c/.collection"
  cp -R "$geo/$c/\$records" "$dest/$c/\$records"
  echo "$c: $c" >> "$dest/.ingitdb/root-collections.yaml"
done
ingitdb validate --path "$dest"
