#!/usr/bin/env python3
"""Verify guided DemoDB SQL and expected rows against pinned SQLite editions.

The fixture directory must contain <dataset>.sqlite files whose SHA-256 values
match demo-project-1/connections/demo-db.json. Inputs are opened read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "demo-project-1"
RESULTS = ROOT / "tests/fixtures/demodb-guided-query-results.json"
DATASETS = ("chinook", "northwind", "pubs", "sakila", "adventureworks", "employees")


def canonical_rows(rows: list[dict[str, object]]) -> bytes:
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures_dir", type=Path, help="directory containing <dataset>.sqlite files")
    args = parser.parse_args()

    catalog = json.loads((PROJECT / "connections/demo-db.json").read_text(encoding="utf-8"))
    sqlite_connections = {
        entry["dataset"]: entry
        for entry in catalog["connections"]
        if entry.get("storage") == "sqlite"
    }
    expected = json.loads(RESULTS.read_text(encoding="utf-8"))
    if expected.get("format") != "demodb-guided-query-results/v1":
        raise SystemExit("unsupported guided-query result fixture format")

    discovered: set[str] = set()
    for dataset in DATASETS:
        connection = sqlite_connections.get(dataset)
        if not connection:
            raise SystemExit(f"missing {dataset}-sqlite connection in demo-db.json")
        db_path = args.fixtures_dir / f"{dataset}.sqlite"
        if not db_path.is_file():
            raise SystemExit(f"missing SQLite fixture: {db_path}")
        source_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()
        if source_sha != connection.get("fixtureSha256"):
            raise SystemExit(f"{dataset}: fixture SHA-256 {source_sha} does not match catalogue pin")

        query_dir = PROJECT / "queries/demodb" / dataset
        with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True) as db:
            db.execute("PRAGMA query_only = ON")
            for sql_path in sorted(query_dir.glob("*.query.sql")):
                query_key = f"{dataset}/{sql_path.name.removesuffix('.query.sql')}"
                discovered.add(query_key)
                query_def_path = sql_path.with_name(sql_path.name.removesuffix(".sql") + ".json")
                if not query_def_path.is_file():
                    raise SystemExit(f"{query_key}: missing query metadata {query_def_path}")
                definition = json.loads(query_def_path.read_text(encoding="utf-8"))
                if definition.get("type") != "SQL" or definition.get("targets") != [{"catalog": connection["id"]}]:
                    raise SystemExit(f"{query_key}: query type or SQLite target does not match the catalogue")
                sql = sql_path.read_text(encoding="utf-8").strip()
                if not sql.upper().startswith(("SELECT", "WITH")):
                    raise SystemExit(f"{query_key}: only read-only SELECT queries are allowed")
                cursor = db.execute(sql)
                names = [column[0] for column in cursor.description or ()]
                rows = [dict(zip(names, row)) for row in cursor.fetchall()]
                recordsets = definition.get("recordsets") or []
                actual_columns = [column["name"] for column in recordsets[0].get("columns", [])] if recordsets else []
                if names != actual_columns:
                    raise SystemExit(f"{query_key}: query metadata columns {actual_columns} do not match SQL columns {names}")
                expected_query = expected.get("queries", {}).get(query_key)
                if not expected_query:
                    raise SystemExit(f"{query_key}: missing expected result")
                actual_sha = hashlib.sha256(canonical_rows(rows)).hexdigest()
                if len(rows) != expected_query.get("rowCount") or actual_sha != expected_query.get("sha256"):
                    raise SystemExit(f"{query_key}: result differs from pinned snapshot (rows={len(rows)}, sha256={actual_sha})")
                if rows[:2] != expected_query.get("sampleRows"):
                    raise SystemExit(f"{query_key}: visible expected sample differs from query output")
                print(f"ok {query_key}: {len(rows)} rows, fixture {source_sha[:12]}")

    if discovered != set(expected.get("queries", {})):
        missing = sorted(set(expected.get("queries", {})) - discovered)
        extra = sorted(discovered - set(expected.get("queries", {})))
        raise SystemExit(f"query/result fixture mismatch; missing={missing}, extra={extra}")
    if len(discovered) != 18:
        raise SystemExit(f"expected 18 guided queries, found {len(discovered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
