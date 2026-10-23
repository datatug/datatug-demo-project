#!/usr/bin/env python3
"""Verify two independent Northwind aggregates and the PostgreSQL race input.

Uses only the Python standard library. By default it POSTs the saved queries.
Pass all three response-file flags to recheck captured JSON offline. It fails
closed on HTTP, completion, shape, provenance, or parity errors. The receipt
printed on success contains hashes, not row data.
"""

import argparse
import collections
import hashlib
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
QUERIES = ROOT / "demo-project-1" / "queries" / "demodb"
EXPECTED_MAPPED_SHA256 = "10180147a7752d4006c28d438d7deed96461336b865156036c2c017f5c82b235"
PG_COLLECTION = "pg1_AAAACW5vcnRod2luZAAAAAZPcmRlcnM"
SOURCES = (
    (
        "sqlite",
        "northwind",
        "Orders",
        "https://demodb.dev/ovdb/v1/databases/northwind/dtql",
        "northwind-shipping-country-count-sqlite.query.dtql",
    ),
    (
        "postgresql",
        "northwind-postgresql",
        PG_COLLECTION,
        "https://cloud.openvaultdb.com/v1/databases/northwind-postgresql/dtql",
        "northwind-shipping-country-count-postgresql.query.dtql",
    ),
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError(f"unexpected HTTP redirect {code} to {newurl}")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def fetch(url, query):
    body = json.dumps({"query": query}, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "curl/8.7.1",
        },
        method="POST",
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError(f"{url}: HTTP {response.status}, expected 200")
            raw = response.read(2_000_001)
    except urllib.error.HTTPError as error:
        raise ValueError(f"{url}: HTTP {error.code}, expected 200") from error
    except urllib.error.URLError as error:
        raise ValueError(f"{url}: request failed: {error.reason}") from error
    if len(raw) > 2_000_000:
        raise ValueError(f"{url}: response exceeded 2 MB verification bound")
    return raw


def verify(raw, label, expected_database, expected_collection):
    try:
        response = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label}: response is not UTF-8 JSON") from error
    if not isinstance(response, dict) or response.get("complete") is not True:
        raise ValueError(f"{label}: response is not complete=true")
    records = response.get("records")
    if not isinstance(records, list) or len(records) != 21:
        raise ValueError(f"{label}: expected exactly 21 records")
    execution = response.get("execution")
    if not isinstance(execution, dict) or execution.get("rowsReturned") != 21:
        raise ValueError(f"{label}: execution.rowsReturned must be 21")
    sources = execution.get("sources")
    if not isinstance(sources, list) or len(sources) != 1:
        raise ValueError(f"{label}: expected exactly one execution source")
    source = sources[0]
    if not isinstance(source, dict) or source.get("database") != expected_database:
        raise ValueError(f"{label}: execution source database mismatch: {source!r}")
    collection = source.get("collection")
    if collection != expected_collection:
        raise ValueError(f"{label}: execution source collection mismatch: {source!r}")

    rows = []
    for i, record in enumerate(records):
        data = record.get("data") if isinstance(record, dict) else None
        if not isinstance(data, dict):
            raise ValueError(f"{label}: record {i} lacks a data object")
        country, count = data.get("ShipCountry"), data.get("orders")
        if not isinstance(country, str) or not country:
            raise ValueError(f"{label}: record {i} has no ShipCountry")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"{label}: record {i} has invalid orders count")
        rows.append([country, count])
    if len({country for country, _ in rows}) != 21:
        raise ValueError(f"{label}: ShipCountry is not unique")
    if rows != sorted(rows, key=lambda row: row[0]):
        raise ValueError(f"{label}: records are not ordered by ShipCountry")
    canonical = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return rows, {
        "database": source["database"],
        "collection": collection,
        "complete": True,
        "rows": len(rows),
        "rawResponseSha256": sha256(raw),
        "mappedRowsSha256": sha256(canonical),
    }


def verify_race(raw):
    try:
        response = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("race: response is not UTF-8 JSON") from error
    if not isinstance(response, dict) or response.get("complete") is not True:
        raise ValueError("race: response is not complete=true")
    records, execution = response.get("records"), response.get("execution")
    if not isinstance(records, list) or len(records) != 830:
        raise ValueError("race: expected exactly 830 records")
    if response.get("columns") != ["OrderID", "OrderDate", "ShipCountry"]:
        raise ValueError("race: unexpected projection columns")
    if not isinstance(execution, dict) or execution.get("rowsReturned") != 830:
        raise ValueError("race: execution.rowsReturned must be 830")
    sources = execution.get("sources")
    if sources != [{"database": "northwind-postgresql", "collection": PG_COLLECTION}]:
        raise ValueError("race: execution source identity mismatch")
    rows = []
    for i, record in enumerate(records):
        data = record.get("data") if isinstance(record, dict) else None
        if not isinstance(data, dict):
            raise ValueError(f"race: record {i} lacks a data object")
        order_id, date, country = (data.get(k) for k in ("OrderID", "OrderDate", "ShipCountry"))
        if isinstance(order_id, bool) or not isinstance(order_id, int):
            raise ValueError(f"race: record {i} has invalid OrderID")
        if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError(f"race: record {i} has invalid OrderDate")
        if not isinstance(country, str) or not country:
            raise ValueError(f"race: record {i} has invalid ShipCountry")
        rows.append([date, order_id, country])
    if rows != sorted(rows, key=lambda row: (row[0], row[1])):
        raise ValueError("race: records are not ordered by OrderDate and OrderID")
    if len({row[1] for row in rows}) != 830:
        raise ValueError("race: OrderID is not unique")
    months = sorted({row[0][:7] for row in rows})
    countries = sorted({row[2] for row in rows})
    counts = collections.Counter((date[:7], country) for date, _, country in rows)
    ranks = [tuple(sorted(countries, key=lambda country: (-counts[month, country], country))) for month in months]
    rank_changes = sum(left != right for left, right in zip(ranks, ranks[1:]))
    leader_changes = sum(left[0] != right[0] for left, right in zip(ranks, ranks[1:]))
    if (len(months), months[0], months[-1], len(countries), rank_changes, leader_changes) != (
        23, "2016-07", "2018-05", 21, 22, 16
    ):
        raise ValueError("race: monthly frame or ranking metrics differ from verified baseline")
    canonical = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "database": "northwind-postgresql",
        "collection": PG_COLLECTION,
        "complete": True,
        "rows": 830,
        "firstDate": rows[0][0],
        "lastDate": rows[-1][0],
        "countries": len(countries),
        "months": len(months),
        "rankChanges": rank_changes,
        "leaderChanges": leader_changes,
        "rawResponseSha256": sha256(raw),
        "mappedRowsSha256": sha256(canonical),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-response", type=pathlib.Path)
    parser.add_argument("--postgresql-response", type=pathlib.Path)
    parser.add_argument("--race-response", type=pathlib.Path)
    args = parser.parse_args()
    if len([v for v in (args.sqlite_response, args.postgresql_response, args.race_response) if v]) not in (0, 3):
        parser.error("supply all three response files or none")
    offline = {"sqlite": args.sqlite_response, "postgresql": args.postgresql_response}
    results = {}
    for label, database, collection, url, filename in SOURCES:
        query = (QUERIES / filename).read_text(encoding="utf-8")
        raw = offline[label].read_bytes() if offline[label] else fetch(url, query)
        rows, receipt = verify(raw, label, database, collection)
        receipt["endpoint"] = url
        receipt["querySha256"] = sha256(query.encode("utf-8"))
        results[label] = (rows, receipt)
    if results["sqlite"][0] != results["postgresql"][0]:
        raise ValueError("SQLite and PostgreSQL mapped rows differ")
    total = sum(count for _, count in results["sqlite"][0])
    if total != 830:
        raise ValueError(f"Northwind aggregate sums to {total} orders, expected 830")
    if results["sqlite"][1]["mappedRowsSha256"] != EXPECTED_MAPPED_SHA256:
        raise ValueError("Northwind mapped rows differ from the verified 2026-10-16 baseline")
    race_url = "https://cloud.openvaultdb.com/v1/databases/northwind-postgresql/dtql"
    race_query = (QUERIES / "northwind-shipping-country-race.query.dtql").read_text(encoding="utf-8")
    race_raw = args.race_response.read_bytes() if args.race_response else fetch(race_url, race_query)
    race_receipt = verify_race(race_raw)
    race_receipt["endpoint"] = race_url
    race_receipt["querySha256"] = sha256(race_query.encode("utf-8"))
    print(json.dumps({
        "parity": True,
        "ordersTotal": total,
        "sources": {k: v[1] for k, v in results.items()},
        "race": race_receipt,
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"visual showcase source verification failed: {error}", file=sys.stderr)
        sys.exit(1)
