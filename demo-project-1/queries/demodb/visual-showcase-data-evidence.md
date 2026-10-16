# Visual showcase data evidence

Observed 2026-10-16. This note separates immutable local SQLite checks, live
public OpenVaultDB executions, and DataTug app behavior. The six datasets below
are the SQLite/PostgreSQL editions in the project's
[`connections/demo-db.json`](../../connections/demo-db.json). That catalogue
also lists InGitDB editions, six BigQuery imports that require a user's Google
account and execution project, and two BigQuery ideas marked `setup-required`;
those are not browser-ready sources for this showcase.

## Six-dataset comparison

The table and row counts below are **catalogue-reported BigQuery import
counts**, not measurements from the live OVDB endpoints. The SHA-256 pins
belong to the SQLite editions, not the PostgreSQL copies. The four marked
local fixtures were present and read-only queried at the paths shown below.
Sakila and AdventureWorks SQLite fixture files were not available in this
checkout, though their public OVDB endpoints are catalogued.

| Dataset | Domain and candidate charts | Tables / rows in catalogue import | SQLite pin prefix | Local fixture present | Selection limit |
| --- | --- | ---: | --- | --- | --- |
| Chinook | Music sales; genre/category, customer spend, invoice time series | 11 / 15,607 | `7651ba37` | yes | Only 412 invoices; limited visual scale |
| Northwind | Orders, countries, products, shippers; bars, monthly race, order detail | 13 / 3,310 | `279b3413` | yes | 830 orders and 23 months; countries are shipping destinations, not a map geometry |
| Pubs | Authors, titles, stores, royalties; categorical breakdowns | 11 / 255 | `b45b08b7` | yes | Only 21 sales rows |
| Sakila | Film rentals, category and payment measures | 16 / 47,268 | `9bebeee5` | no | Temporal and nullable-field quality not measured here |
| AdventureWorks | Sales, territories, products, hierarchy; broad chart range | 71 / 759,240 | `6a105e19` | no | Full daily-territory aggregate needs paging; browser import is too large |
| Employees | Headcount, department, titles, salary history | 6 / 13,584 | `46b49dd0` | yes | `9999-01-01` means open-ended validity, not a real future observation |

The local checks used read-only SQLite connections to these exact paths:
`/Users/alex/projects/demo-db/chinook/artifacts/data/chinook.sqlite`,
`/Users/alex/projects/demo-db/northwind/artifacts/northwind.sqlite`,
`/Users/alex/projects/demo-db/pubs/artifacts/pubs.sqlite`, and
`/Users/alex/projects/demo-db/employees/artifacts/employees.sqlite`. Reproduce
the temporal checks with:

```sql
SELECT count(*), min(InvoiceDate), max(InvoiceDate), sum(InvoiceDate IS NULL) FROM Invoice; -- Chinook: 412, 2021-01-01 00:00:00, 2025-12-22 00:00:00, 0
SELECT count(*), min(OrderDate), max(OrderDate), sum(OrderDate IS NULL), sum(ShipCountry IS NULL) FROM Orders; -- Northwind: 830, 2016-07-04, 2018-05-06, 0, 0
SELECT count(*), min(ord_date), max(ord_date), sum(ord_date IS NULL) FROM sales; -- Pubs: 21, 1992-06-15, 1994-09-14, 0
SELECT count(*), min(from_date), max(from_date), sum(from_date IS NULL) FROM salaries; -- Employees: 9876, 1985-01-01, 2002-08-01, 0
```

### Weighted selection

This is a **source selection score**, not an acceptance or DataTug app
readiness score. Each dimension is rated 0–4; the total is
`sum(weight × rating / 4)`. Diversity (30) measures distinct defensible chart
shapes; temporal depth (20) measures observed useful dates; reproducibility
and runtime access (25) rewards pinned inputs and executed public/app paths;
cross-source potential (15) rewards a defensible common meaning; limitations
(10) is higher when fewer material limits remain. Unmeasured quality is
scored conservatively. An existing app query path earns access points, but
**none of these scores proves the new dashboard composition path**.

| Rank | Dataset | Diversity (30%) | Time (20%) | Access (25%) | Cross-source (15%) | Few limits (10%) | Total /100 | Evidence affecting score |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Northwind | 3 | 3 | 2 | 3 | 2 | 66.25 | Pinned 830 orders, live two-edition parity and race; single-environment app path missing |
| 2 | Chinook | 2 | 2 | 4 | 2 | 2 | 62.50 | Pinned local fixture and earlier observed browser query path; only 412 invoices |
| 3 | AdventureWorks | 4 | 3 | 1 | 1 | 0 | 55.00 | Broad 71-table catalogue; 5,404-group estimate provisional and full series needs paging |
| 4 | Employees | 2 | 3 | 2 | 1 | 2 | 51.25 | Pinned 9,876 salary-history rows; sentinel end dates need explicit treatment |
| 5 | Sakila | 2 | 1 | 1 | 1 | 1 | 32.50 | Rich catalogue but local temporal/null quality was not checked |
| 6 | Pubs | 1 | 1 | 2 | 1 | 0 | 28.75 | Pinned local fixture but only 21 sales rows |

The five numeric rating columns are 0–4, not weighted point contributions;
the header shows their weights. Northwind is the first source candidate for an
executable showcase; Chinook is the secondary, smaller source with an existing
app query path. AdventureWorks is a richer future candidate, gated by source
paging and a proven app route. Pubs' sales volume is too sparse for a flagship;
Sakila's date quality remains unmeasured; Employees fits workforce history
better than the sales story. Cross-business revenue must not be described as
competing sales: currency, unit, business meaning, and date alignment differ.

## Public OVDB executions and saved definitions

The committed [verification script](../../../scripts/verify-visual-showcase-sources.py)
made two **independent** 2026-10-16 live POST executions in a network-enabled
shell. Both returned HTTP 200, `complete=true`, 21 distinct country rows and
the same 830-order total. Their mapped rows were byte-for-byte equal after
canonicalization; the observed source IDs and SHA-256 digests are retained in
the sanitized [source receipt](visual-showcase-source-receipt.json). The
default sandbox shell could not resolve these hosts; the network-enabled run
succeeded. These are public OVDB executions, not DataTug app executions.

| Saved query | Endpoint | Result |
| --- | --- | --- |
| [`northwind-shipping-country-count-sqlite.query.dtql`](northwind-shipping-country-count-sqlite.query.dtql) | `https://demodb.dev/ovdb/v1/databases/northwind/dtql` | 21 country rows, complete, source `northwind/Orders` |
| [`northwind-shipping-country-count-postgresql.query.dtql`](northwind-shipping-country-count-postgresql.query.dtql) | `https://cloud.openvaultdb.com/v1/databases/northwind-postgresql/dtql` | 21 country rows, complete, source `northwind-postgresql/pg1_AAAACW5vcnRod2luZAAAAAZPcmRlcnM` |

From the repository root, execute all three saved query bodies as
JSON-wrapped DTQL. The checker verifies HTTP 200, `complete=true`, 21
distinct ordered countries, integer order counts, one expected execution
source per response, and exact mapped-row parity for the two aggregates.
It also verifies the 830-row PostgreSQL race input:

```sh
python3 scripts/verify-visual-showcase-sources.py
```

It emits a sanitized JSON receipt with endpoint, query SHA-256, raw-response
SHA-256, mapped-row SHA-256, exact `execution.sources` database/collection IDs,
and parity. It checks the 830-order total and the observed mapped-row digest,
then exits nonzero on any mismatch, incomplete result, HTTP error, redirect,
or network failure. To recheck captured responses without network, pass
`--sqlite-response <file> --postgresql-response <file> --race-response <file>`.
The receipt preserves
digests rather than full business rows; a fresh run is required to validate
the current remote state.

The SQLite body uses `from: {name: Orders}`; PostgreSQL uses
`from: {schema: northwind, name: Orders}`. Both group by `ShipCountry`,
select `ShipCountry` and `count(*) as orders`, sort by country, and limit to
100. The 2026-10-16 verification proves source parity for this aggregate at
that point in time. It does not prove federation, a visual comparison, or browser
composition.

The [race input](northwind-shipping-country-race.query.dtql) selects
`OrderID`, `OrderDate`, and `ShipCountry` from Northwind PostgreSQL, orders by
date and ID, and limits to 1000. The pinned local SQLite fixture and a live
PostgreSQL execution both returned 830 rows. The live execution was HTTP 200,
`complete=true`, source `northwind-postgresql/pg1_AAAACW5vcnRod2luZAAAAAZPcmRlcnM`,
with zero null dates/countries and ordered date bounds 2016-07-04 through
2018-05-06. The [source receipt](visual-showcase-source-receipt.json) records
the raw and mapped digests. A local read-only reproduction is:

```sql
SELECT OrderID, OrderDate, ShipCountry
FROM Orders
ORDER BY OrderDate, OrderID;
```

It returns 830 rows, 0 null dates, 0 null countries, and 21 countries. Group
the date's `YYYY-MM` prefix with `ShipCountry` and count orders. The hosted
PostgreSQL import declares `OrderDate` as `TEXT`, so its saved recordset calls
the field a string and the chart must parse its ISO date text explicitly. The resulting
23 monthly frames span 2016-07 through 2018-05; each has 9–21 nonzero
countries and 14–74 orders. Fill absent country/month pairs with zero, sort
ties by country name, and rank all 21 countries per frame: 22 adjacent
full-rank changes, 16 leader changes, and five distinct leaders (`USA` 9
months, `Germany` 6, `Brazil` 5, `France` 2, `UK` 1). This is an order-count
race, never a revenue race. The chart must aggregate the returned records;
these frames are measurements for validation, not saved synthetic data.

The orchestrating agent reported 103 June 2022 grouped `OrderDate`/
`TerritoryID` rows from the public AdventureWorks endpoint and 5,404 grouped
day/territory rows for a full 35-month input. The exact derivation and
responses have not been committed, so both numbers are provisional. The DTQL
server's reported maximum `limit` is 1000. A static saved QueryDef has no
complete deterministic paging contract, so no full-series AdventureWorks
showcase QueryDef is added.
The app must first implement ordered paging, completeness checks, and a
failure path before using that full series.

## DataTug runtime gates

The connection catalogue admits `northwind-sqlite` to `dev` and
`northwind-postgresql` to `QA`/`UAT`. **No existing project environment
admits both.** Before an Add Source step promises both cards in one dashboard,
the app and project configuration must agree on a single authorized execution
context or explicit per-tab environment binding. The current saved QueryDefs
alone cannot establish that behavior.

The browser must execute these source-bound DTQL definitions, preserve source
identity and `orders` units on each result, and expose errors/incomplete
responses. Only after an observed app run may UI copy claim working
cross-source composition. The country-count pair involves two source
executions; any same-chart overlay is a client composition of two recordsets,
not one federated database query. The race's live source receipt establishes
input completeness, but the app still needs the monthly transform, stable tie
handling, manual stepping, pause, and reduced-motion behavior.
