#!/usr/bin/env bash
# Refresh, or verify, demo-project-1/data/geo from a geo-ingitdb checkout.
#
#   scripts/sync-geo-data.sh [GEO_INGITDB_DIR]           refresh the vendored copy
#   scripts/sync-geo-data.sh --check [GEO_INGITDB_DIR]   fail when it differs from the checkout
#
# Vendors the three collections the hero query needs (countries, population_wb,
# country_aliases), a root-collections file listing only them, and geo-ingitdb's
# DATA-LICENSE.md (the World Bank and GeoNames attribution, CC BY 4.0), and
# records the geo-ingitdb commit in data/geo/.vendored-from. Only those managed
# paths are replaced: data/geo/README.md is hand-written and is preserved.
# The World Bank records carry their own provenance (indicator, source_url,
# fetched_at); geo-ingitdb Git history is the snapshot history.
#
# --check stages what a refresh would write and diffs it against the committed
# copy (README.md and .vendored-from aside), so edits to the vendored data, and a
# copy that no longer matches the recorded geo-ingitdb commit, are caught. CI runs
# it against a checkout of that recorded commit.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
check=0
if [ "${1:-}" = "--check" ]; then check=1; shift; fi
geo="${1:-${GEO_INGITDB_DIR:-$root/../../ingitdb/geo-ingitdb}}"
dest="$root/demo-project-1/data/geo"

die() { echo "sync-geo-data: $*" >&2; exit 1; }

collections=(countries population_wb country_aliases)
for c in "${collections[@]}"; do
  [ -d "$geo/$c/\$records" ] || die "$geo/$c/\$records not found (pass the geo-ingitdb checkout)"
done
[ -f "$geo/DATA-LICENSE.md" ] || die "$geo/DATA-LICENSE.md not found (the attribution must travel with the data)"

commit="$(git -C "$geo" rev-parse HEAD 2>/dev/null)" || die "$geo is not a git checkout; the vendored commit must be recorded"
if [ "$check" = 0 ] && [ -n "$(git -C "$geo" status --porcelain -- "${collections[@]}" .ingitdb DATA-LICENSE.md)" ]; then
  die "$geo has uncommitted changes to the vendored paths; commit and push them first so .vendored-from is true"
fi

# stage DIR: write the managed files (everything except README.md and .vendored-from).
stage() {
  local out="$1" c
  mkdir -p "$out/.ingitdb"
  cp "$geo/.ingitdb/settings.yaml" "$out/.ingitdb/settings.yaml"
  : > "$out/.ingitdb/root-collections.yaml"
  for c in "${collections[@]}"; do
    mkdir -p "$out/$c"
    cp -R "$geo/$c/.collection" "$out/$c/.collection"
    cp -R "$geo/$c/\$records" "$out/$c/\$records"
    echo "$c: $c" >> "$out/.ingitdb/root-collections.yaml"
  done
  cp "$geo/DATA-LICENSE.md" "$out/DATA-LICENSE.md"
}

staged="$(mktemp -d)"
trap 'rm -rf "$staged"' EXIT
stage "$staged"

if [ "$check" = 1 ]; then
  recorded="$(sed -n 's/^commit=//p' "$dest/.vendored-from" 2>/dev/null || true)"
  [ -n "$recorded" ] || die "$dest/.vendored-from has no commit= line; run scripts/sync-geo-data.sh"
  [ "$recorded" = "$commit" ] || echo "sync-geo-data: note: vendored from $recorded, checkout is at $commit" >&2
  if diff -r -x README.md -x .vendored-from "$staged" "$dest" >&2; then
    echo "sync-geo-data: demo-project-1/data/geo matches geo-ingitdb at $commit"
    exit 0
  fi
  die "demo-project-1/data/geo differs from geo-ingitdb at $commit (see the diff above); run scripts/sync-geo-data.sh"
fi

mkdir -p "$dest"
rm -rf "$dest/.ingitdb" "$dest/DATA-LICENSE.md"
for c in "${collections[@]}"; do rm -rf "${dest:?}/$c"; done
cp -R "$staged"/. "$dest"/
printf 'repository=ingitdb/geo-ingitdb\ncommit=%s\n' "$commit" > "$dest/.vendored-from"
[ -f "$dest/README.md" ] || echo "sync-geo-data: warning: $dest/README.md is missing (it is hand-written and not generated)" >&2
ingitdb validate --path "$dest"
echo "sync-geo-data: vendored geo-ingitdb at $commit into demo-project-1/data/geo"
