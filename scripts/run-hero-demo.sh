#!/usr/bin/env bash
# Run the DataTug.ai hero question for real, end to end, with zero AI tokens:
#
#   "Which countries buy the most music relative to their population?"
#
#   Chinook invoices -> country alias -> ISO country -> World Bank population
#   -> sales per million people
#
# What it does:
#   1. Derives demo-project-1/.demo-data/chinook.sqlite from the pinned Chinook
#      SQLite file (adds the `id` column OpenVaultDB's SQLite adapter needs).
#   2. Starts ONE local OpenVaultDB server (ovdb serve) on a free port with the
#      chinook and geo manifests from demo-project-1/fixtures/ovdb, the same
#      endpoint the DataTug web app reads via the query's federation.ovdbBaseUrl.
#   3. Checks that the server answers for both databases.
#   4. Runs the saved DTQL query with the DataTug CLI (--format json). The CLI
#      reads the project environment's catalogs directly (SQLite file, inGitDB
#      directory); it does not go through the OVDB server.
#   5. Prints the top countries and stops the server it started (only that PID).
#
# Usage: scripts/run-hero-demo.sh [--json]
#   --json            print the full result as JSON instead of the summary table
# Environment:
#   CHINOOK_SQLITE    pinned Chinook_Sqlite.sqlite (default: ../chinook-database
#                     beside this repository, else a shallow clone is made under
#                     demo-project-1/.demo-data)
#   OVDB_PORT         listen port (default: a free port chosen at run time)
#   DATATUG, OVDB     binaries (default: from PATH)
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project="$root/demo-project-1"
data="$project/.demo-data"
datatug="${DATATUG:-datatug}"
ovdb="${OVDB:-ovdb}"
as_json=0
[ "${1:-}" = "--json" ] && as_json=1

need() { command -v "$1" >/dev/null 2>&1 || { echo "run-hero-demo: '$1' not found on PATH" >&2; exit 1; }; }
need "$datatug"; need "$ovdb"; need python3; need curl; need lsof

mkdir -p "$data"

# 1. Chinook: pinned source -> OVDB-readable copy.
chinook_src="${CHINOOK_SQLITE:-$root/../chinook-database/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite}"
if [ ! -f "$chinook_src" ]; then
  need git
  echo "Chinook source not found at $chinook_src; cloning datatug/chinook-database (shallow)..." >&2
  [ -d "$data/chinook-database" ] || git clone --quiet --depth 1 https://github.com/datatug/chinook-database "$data/chinook-database"
  chinook_src="$data/chinook-database/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
fi
python3 "$root/scripts/prepare_chinook.py" "$chinook_src" "$data/chinook.sqlite"

# 2. A free port. Pick one the OS reports free, then confirm with lsof; never
#    touch whatever else is listening.
port="${OVDB_PORT:-$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')}"
if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "run-hero-demo: port $port is already in use (not touching it); set OVDB_PORT to another port" >&2
  exit 1
fi

log="$data/ovdb.log"
"$ovdb" serve --addr "127.0.0.1:$port" \
  --manifest "$project/fixtures/ovdb/chinook.ovdb.yaml" \
  --manifest "$project/fixtures/ovdb/geo.ovdb.yaml" >"$log" 2>&1 &
ovdb_pid=$!
cleanup() {
  kill "$ovdb_pid" 2>/dev/null || true
  wait "$ovdb_pid" 2>/dev/null || true
  echo "stopped ovdb (pid $ovdb_pid, port $port)" >&2
}
trap cleanup EXIT

base="http://127.0.0.1:$port"
for _ in $(seq 1 50); do
  curl -fsS "$base/.well-known/openvaultdb" >/dev/null 2>&1 && break
  kill -0 "$ovdb_pid" 2>/dev/null || { echo "run-hero-demo: ovdb exited early:" >&2; cat "$log" >&2; exit 1; }
  sleep 0.2
done
curl -fsS "$base/.well-known/openvaultdb" >/dev/null 2>&1 || { echo "run-hero-demo: ovdb did not start" >&2; cat "$log" >&2; exit 1; }
echo "ovdb serving chinook + geo on $base (pid $ovdb_pid)" >&2

# 3. The server answers for both databases.
ovdb_ireland="$(curl -fsS "$base/v1/databases/geo/records/population_wb/ie")"
curl -fsS "$base/v1/databases/chinook/records/Invoice/1" >/dev/null

# 4. The saved query, through the DataTug CLI.
result="$data/last-result.json"
(cd "$root" && "$datatug" query run --project demo-project-1 --query sales/chinook-sales-per-capita \
  --env local --as alex --role admin --format json >"$result")

# 5. Report.
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
    print(f"{i:>2}  {r['country']:<16} {r['totalSales']:>9.2f} {r['population']:>14,} {r['salesPerMillion']:>14.2f}")
print(f"\nfull result: {os.environ['HERO_JSON']}")
PY
