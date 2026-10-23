#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
adapter_repo="${DALGO2LOGS_REPO:-$repo_root/../dalgo2logs}"
if [[ ! -f "$adapter_repo/go.mod" ]]; then
  echo 'Set DALGO2LOGS_REPO to the local dalgo2logs checkout.' >&2
  exit 2
fi
if ! command -v go >/dev/null 2>&1; then
  echo 'Go is required.' >&2
  exit 2
fi

scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
GOWORK=off go -C "$adapter_repo" build -o "$scratch/dalgo2logs-ovdb" ./cmd/dalgo2logs-ovdb
cd "$repo_root"
"$scratch/dalgo2logs-ovdb" --config "$repo_root/demo-project-1/fixtures/logs/ovdb-direct.json"
