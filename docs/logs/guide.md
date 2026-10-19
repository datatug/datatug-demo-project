# Investigate Northwind order 11039 in DataTug

This local demo reads the committed synthetic files directly. It creates no
log database, copy, index or snapshot. The order is a real record in the pinned
Northwind DemoDB SQLite edition; the log entries are invented for this test.
The DataTug page presents them in AG Grid. The standalone
walkthrough uses an illustrative HTML table with similar columns and row
selection; it is not AG Grid and is not a product screenshot. See the
[working AG Grid screenshot](screenshot-datatug-ag-grid.png) and
[selected raw evidence](screenshot-datatug-ag-grid-detail.png).

## Start

Use Go 1.26.1 or newer, Node.js and pnpm. Check out current
`dal-go/dalgo2logs`, `datatug/datatug-demo-project` and
`datatug/datatug-apps` in sibling folders. The adapter pins the OVDB revision
containing the generic external mount. The script builds the adapter with
`GOWORK=off` and removes its temporary binary when the server stops:

```sh
cd /path/to/datatug-demo-project
DALGO2LOGS_REPO=/path/to/dalgo2logs bash scripts/run-northwind-evidence.sh
```

The script starts the server on `127.0.0.1:6832`. Stop it with Ctrl-C. The demo configuration is
deliberately unauthenticated and must remain on loopback with synthetic data.
For a private Google Cloud Logging source, configure a fixed project and set
`OVDB_LOGS_OWNER_TOKEN` before starting; enter that token only in the local
DataTug page. Do not publish this single-owner server for multiple users.

In another terminal, install DataTug's dependencies and build the demo UI.
The `--excludeTaskDependencies` flag bypasses the app's unrelated
RecordsetCompare release-asset preparation, which currently returns HTTP 404
on this local path. The order and log investigation does not use that feature.
The build itself still compiles DataTug and copies its browser assets:

```sh
cd /path/to/datatug-apps
pnpm install --frozen-lockfile
NX_DAEMON=false NX_ISOLATE_PLUGINS=false node_modules/.bin/nx run datatug-app:stamp-build-info
NX_DAEMON=false NX_ISOLATE_PLUGINS=false node_modules/.bin/nx run datatug-app:stamp-ag-grid-license
NX_DAEMON=false NX_ISOLATE_PLUGINS=false node_modules/.bin/nx build datatug-app \
  --configuration=development --excludeTaskDependencies --skip-nx-cache
python3 /path/to/datatug-demo-project/scripts/serve-built-datatug.py \
  dist/apps/datatug-app/browser
```

The helper serves only on `127.0.0.1:4200`; stop it with Ctrl-C. It requires
Python 3.9 or newer and does not fetch or prepare the RecordsetCompare package.
Open `http://127.0.0.1:4200/demo/sqlite/northwind/table/Orders?record=11039`.
The first use downloads the public pinned Northwind SQLite fixture to the
browser and creates an editable local copy after the page's confirmation.
Select order 11039 and follow **Related log evidence**. The link uses the
explicit `Orders.OrderID → fulfillment_events.order_id` mapping.

## Expected path

1. In the order, confirm `CustomerID=LINOD`, `ShipVia=2`, and an unset
   `ShippedDate`. The saved [record query](../../demo-project-1/queries/demodb/northwind-order-11039.query.sql)
   joins the Shippers table to show United Package; four order-detail rows
   exist for this order.
2. The evidence page at `/demo/logs?order=11039` queries the ordinary OVDB
   `northwind_evidence/fulfillment_events` collection. DataTug renders the
   results in AG Grid with Timestamp, Severity, Service, Source and Message
   columns, newest first. Selecting a row opens its parse status, correlation
   and order IDs, source reference, original entry and structured fields. The
   query returns six related entries from 09:13:00 through 09:13:06 UTC. A
   request for `order_id=11040` returns one noise entry; an unknown ID is empty.
3. Select the 09:13:06 event: `orders-api` says the shipment update was
   deferred. Select the 09:13:05.300 WARN event: `retry_budget=0` made the
   retryable failure terminal. Then select the 09:13:05 ERROR event: the
   synthetic carrier gateway returned HTTP 503. These entries explain this
   **synthetic** run; the real database never recorded the historical cause
   of its unset `ShippedDate`.
4. Switch collection to `carrier_events` and keep order 11039 to inspect the
   raw multiline stack. Set severity to `ERROR` or narrow the UTC range to
   isolate events. Set correlation ID to `nw-11039-f1` to follow this run.
   Clear the order filter and select **Include untimed or malformed entries**
   to see parser failures. That control intentionally skips the time bounds;
   it is available only for the local file adapter.
5. Copy a source reference from the selected row's details and use **Open the
   order record** to return to the selected database record. The route, order
   ID, fixture revision and copied reference are the current reproducible
   investigation mechanism. Persisted Detective cases are not implemented.

## Direct API check

This uses the unchanged OVDB query route and returns the same six entries:

```sh
curl -fsS http://127.0.0.1:6832/v1/databases/northwind_evidence
curl -fsS -X POST http://127.0.0.1:6832/v1/databases/northwind_evidence/query \
  -H 'Content-Type: application/json' \
  -d '{"collection":"fulfillment_events","where":[{"field":"order_id","op":"==","value":"11039"}],"orderBy":[{"field":"timestamp","desc":false}],"limit":100}'
```

The server's public OVDB protocol has no log type. Its programmatic mount
returns ordinary collection metadata; DataTug supplies the presentation.
Files remain under the explicitly configured root and are rescanned on each
query. A reference changes when the file content changes. The default query
shows at most 100 entries; there is no live tail, free text search, regex or
unbounded pagination.

See the [interactive standalone walkthrough](walkthrough.html) for the same
versioned evidence and the [adapter feature spec](https://github.com/dal-go/dalgo2logs/blob/main/spec/features/direct-log-evidence/README.md)
for the contract and remaining decisions.
