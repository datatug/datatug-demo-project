#!/usr/bin/env bash
# Run the DataTug.ai hero question for real, end to end, with zero AI tokens:
#
#   "Which countries buy the most music relative to their population?"
#
#   Chinook invoices -> country alias -> ISO country -> World Bank population
#   -> sales per million people
#
# What is on the query path, exactly:
#   * The DataTug CLI runs the saved DTQL query sales/chinook-sales-per-capita and
#     reads the `local` environment's catalogs DIRECTLY: the derived Chinook SQLite
#     file and the vendored inGitDB directory data/geo. OpenVaultDB (OVDB) is NOT
#     on the CLI's path.
#   * OVDB serves the same two databases for the DataTug web app (the browser
#     federated executor reads through the query's federation.ovdbBaseUrl). This
#     script starts that server so the web path can be used and cross-checks it:
#     the OVDB record for Ireland must carry the same population the CLI joined.
#     It does not run the query through OVDB or the browser.
#
# Steps:
#   1. Checks the tool versions and finds the Chinook file pinned in
#      demo-project-1/fixtures/chinook/phase1-acceptance.json (repository, revision
#      and SHA-256 all come from that one file), cloning that exact revision under
#      demo-project-1/.demo-data when no local copy is given.
#   2. Derives demo-project-1/.demo-data/chinook.sqlite from it (adds the `id`
#      column OVDB's SQLite adapter needs).
#   3. Starts ONE ovdb server with the chinook and geo manifests from
#      demo-project-1/fixtures/ovdb on the port in federation.ovdbBaseUrl (50501).
#      If that port is taken it says so and serves on another free port instead.
#   4. Checks that the server answers for both databases.
#   5. Runs the saved query with the DataTug CLI (--format json).
#   6. Prints the top countries and stops the server it started (only that PID).
#
# Usage: scripts/run-hero-demo.sh [--json]
#   --json            print the CLI's full result as JSON (totals unrounded, as
#                     the engine returns them) instead of the summary table
# Environment:
#   CHINOOK_SQLITE    the pinned Chinook_Sqlite.sqlite (default: ../chinook-database
#                     beside this repository, else the pinned revision is fetched
#                     under demo-project-1/.demo-data); its SHA-256 is verified
#   OVDB_PORT         serve OVDB on exactly this port, no fallback
#   DATATUG, OVDB     binaries (default: from PATH)
# Needs: bash, python3 (3.10+), curl, datatug >= 0.51.0, ovdb >= 0.19.0 (the
# versions this was verified with), and git when the Chinook file must be fetched.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project="$root/demo-project-1"
data="$project/.demo-data"
datatug="${DATATUG:-datatug}"
ovdb="${OVDB:-ovdb}"
min_datatug="0.51.0"
min_ovdb="0.19.0"
as_json=0
[ "${1:-}" = "--json" ] && as_json=1

die() { echo "run-hero-demo: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' not found on PATH"; }
need "$datatug"; need "$ovdb"; need python3; need curl

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' ||
  die "python3 3.10 or newer is required (found $(python3 -c 'import sys; print(sys.version.split()[0])'))"

# version_ok BINARY NAME MINIMUM: print what is installed, fail clearly when too old.
version_ok() {
  local found
  found="$("$1" --version 2>&1 | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
  [ -n "$found" ] || die "cannot read the version of $2 from '$1 --version'; $2 >= $3 is required"
  if [ "$(printf '%s\n%s\n' "$3" "$found" | sort -V | head -1)" != "$3" ]; then
    die "$2 $found is too old; $2 >= $3 is required (install a newer release of $2)"
  fi
  echo "$2 $found (>= $3)" >&2
}
version_ok "$datatug" datatug "$min_datatug"
version_ok "$ovdb" ovdb "$min_ovdb"

mkdir -p "$data"

# 1. Chinook: the pinned source (one pin file: repository, revision, SHA-256).
pin() { python3 "$root/scripts/prepare_chinook.py" --pin "$1"; }
chinook_src="${CHINOOK_SQLITE:-$root/../chinook-database/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite}"
if [ ! -f "$chinook_src" ]; then
  need git
  repository="$(pin repository)"; revision="$(pin revision)"
  clone="$data/chinook-database"
  echo "Chinook source not found at $chinook_src; fetching $repository at $revision..." >&2
  if [ ! -d "$clone/.git" ]; then
    git init --quiet "$clone"
    git -C "$clone" remote add origin "$repository"
  fi
  if [ "$(git -C "$clone" rev-parse HEAD 2>/dev/null || true)" != "$revision" ]; then
    git -C "$clone" fetch --quiet --depth 1 origin "$revision"
    git -C "$clone" checkout --quiet --detach FETCH_HEAD
  fi
  [ "$(git -C "$clone" rev-parse HEAD)" = "$revision" ] || die "$clone is not at the pinned revision $revision; remove it and re-run"
  chinook_src="$clone/$(pin path)"
fi
python3 "$root/scripts/prepare_chinook.py" "$chinook_src" "$data/chinook.sqlite"

# 2. OVDB on the port the saved query names (federation.ovdbBaseUrl). ovdb's own
#    bind is the arbiter: a port that is taken makes it exit, and only then do we
#    try another, so there is no check-then-bind race.
configured_port="$(python3 - "$project/queries/sales/chinook-sales-per-capita.query.json" <<'PY'
import json, sys
from urllib.parse import urlparse
print(urlparse(json.load(open(sys.argv[1]))["federation"]["ovdbBaseUrl"]).port)
PY
)"
log="$data/ovdb.log"
ovdb_pid=""
cleanup() {
  [ -n "$ovdb_pid" ] || return 0
  kill "$ovdb_pid" 2>/dev/null || true
  wait "$ovdb_pid" 2>/dev/null || true
  echo "stopped ovdb (pid $ovdb_pid, port $port)" >&2
}
trap cleanup EXIT

# owns_port PID PORT: PID is alive and (when lsof exists) is the listener on PORT,
# so an answer from some other process on that port is never mistaken for ours.
owns_port() {
  kill -0 "$1" 2>/dev/null || return 1
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -a -p "$1" -iTCP:"$2" -sTCP:LISTEN >/dev/null 2>&1
  else
    sleep 0.5; kill -0 "$1" 2>/dev/null
  fi
}

# try_port PORT: start ovdb there; succeed once it answers and owns the port.
try_port() {
  port="$1"
  "$ovdb" serve --addr "127.0.0.1:$port" \
    --manifest "$project/fixtures/ovdb/chinook.ovdb.yaml" \
    --manifest "$project/fixtures/ovdb/geo.ovdb.yaml" >"$log" 2>&1 &
  ovdb_pid=$!
  for _ in $(seq 1 50); do
    kill -0 "$ovdb_pid" 2>/dev/null || { wait "$ovdb_pid" 2>/dev/null || true; ovdb_pid=""; return 1; }
    if curl -fsS "http://127.0.0.1:$port/.well-known/openvaultdb" >/dev/null 2>&1; then
      if owns_port "$ovdb_pid" "$port"; then return 0; fi
      if ! kill -0 "$ovdb_pid" 2>/dev/null; then wait "$ovdb_pid" 2>/dev/null || true; ovdb_pid=""; return 1; fi
    fi
    sleep 0.2
  done
  kill "$ovdb_pid" 2>/dev/null || true; wait "$ovdb_pid" 2>/dev/null || true; ovdb_pid=""
  return 1
}

port=""
if [ -n "${OVDB_PORT:-}" ]; then
  try_port "$OVDB_PORT" || { cat "$log" >&2; die "ovdb could not serve on OVDB_PORT=$OVDB_PORT (see the log above)"; }
elif ! try_port "$configured_port"; then
  echo "run-hero-demo: port $configured_port (the saved query's federation.ovdbBaseUrl) is not available; trying another port." >&2
  echo "run-hero-demo: the CLI result is unaffected (it does not read through OVDB), but the web app looks for OVDB on $configured_port." >&2
  started=0
  for _ in 1 2 3 4 5; do
    candidate="$(python3 -c 'import random; print(random.randint(49152, 65000))')"
    if try_port "$candidate"; then started=1; break; fi
  done
  [ "$started" = 1 ] || { cat "$log" >&2; die "ovdb did not start on any port (see the log above)"; }
fi
base="http://127.0.0.1:$port"
echo "ovdb serving chinook + geo on $base (pid $ovdb_pid)" >&2

# 3. The server answers for both databases.
ovdb_ireland="$(curl -fsS "$base/v1/databases/geo/records/population_wb/ie")"
curl -fsS "$base/v1/databases/chinook/records/Invoice/1" >/dev/null

# 4. The saved query, through the DataTug CLI (reads the catalogs directly).
result="$data/last-result.json"
(cd "$root" && "$datatug" query run --project demo-project-1 --query sales/chinook-sales-per-capita \
  --env local --as boss --role admin --format json >"$result")

# 5. Report. Totals are floating point (Chinook stores Total as REAL), so the table rounds them.
HERO_JSON="$result" HERO_OVDB_IE="$ovdb_ireland" HERO_AS_JSON="$as_json" python3 - <<'PY'
import json, os

rows = json.load(open(os.environ["HERO_JSON"]))
if os.environ["HERO_AS_JSON"] == "1":
    print(json.dumps(rows, indent=2))
    raise SystemExit(0)

ovdb = json.loads(os.environ["HERO_OVDB_IE"])["data"]
ireland = next(r for r in rows if r["country"] == "Ireland")
assert ireland["population"] == ovdb["population"], "CLI and OVDB disagree about Ireland's population"

print(f"{len(rows)} countries; top 10 by sales per million people "
      f"(population: World Bank SP.POP.TOTL, {rows[0]['populationYear']})")
print(f"{'#':>2}  {'country':<16} {'sales':>9} {'population':>14} {'sales/million':>14}")
for i, r in enumerate(rows[:10], 1):
    print(f"{i:>2}  {r['country']:<16} {round(r['totalSales'], 2):>9.2f} {r['population']:>14,} {round(r['salesPerMillion'], 2):>14.2f}")
print(f"\nfull result: {os.environ['HERO_JSON']}")
PY
