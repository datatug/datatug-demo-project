#!/usr/bin/env python3
"""Build the standalone walkthrough from the running direct OVDB demo server."""

import json
import pathlib
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:6832/v1/databases/northwind_evidence"
TARGET = ROOT / "docs/logs/walkthrough.html"
TEMPLATE = ROOT / "docs/logs/walkthrough.template.html"


def query(collection):
    body = json.dumps({
        "collection": collection,
        "orderBy": [{"field": "timestamp", "desc": False}],
        "limit": 100,
    }).encode()
    request = urllib.request.Request(
        BASE + "/query", body, {"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"{collection}: HTTP {response.status}")
        result = json.load(response)
    return result["records"]


def main():
    fulfillment = query("fulfillment_events")
    carrier = query("carrier_events")
    order = [entry for entry in fulfillment if entry["data"].get("order_id") == "11039"]
    if len(order) != 6 or not any("retry_budget=0" in row["data"].get("message", "") for row in order):
        raise RuntimeError("the running server does not match the committed Northwind evidence fixture")
    if not any("CarrierClient.createLabel" in row["data"].get("raw", "") for row in carrier):
        raise RuntimeError("the multiline carrier evidence is unavailable")
    data = json.dumps({"fulfillment": fulfillment, "carrier": carrier}, ensure_ascii=False).replace("<", "\\u003c")
    html = TEMPLATE.read_text().replace("<!--EVIDENCE_DATA-->", '<script id="evidence-data" type="application/json">' + data + "</script>")
    TARGET.write_text(html)
    print(f"Wrote {TARGET} from {len(fulfillment)} JSONL and {len(carrier)} text entries")


if __name__ == "__main__":
    main()
