# DemoDB guided investigations

These 18 saved SQLite queries give each public DemoDB dataset three concrete
ways to investigate its data. Each `.query.sql` has matching `.query.json`
metadata that points at that dataset's `*-sqlite` connection in the Dev
environment. The queries are read-only and cap their results at ten rows for
quick exploration. Open a query in DataTug, choose the matching SQLite
connection, then edit a filter or `LIMIT` to continue the investigation.

## Verified inputs

The input files match the `fixtureSha256` pins in the project's
[connection catalogue](../../connections/demo-db.json). The checked-out source
revisions below are clean at `origin/main`; the verifier checks each SQLite
file against the catalogue pin before running any saved SQL.

| Dataset | Dev connection | Source revision | Fixture SHA-256 |
| --- | --- | --- | --- |
| Chinook | `chinook-sqlite` | [411cb7a](https://github.com/demo-db/chinook/tree/411cb7aead96a0b4314f3068c0a0455f869dfdee) | `7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15` |
| Northwind | `northwind-sqlite` | [adb71d1](https://github.com/demo-db/northwind/tree/adb71d17af9aa457d19326d0d275f7b924267659) | `279b34136771aee75d802094b3329515a2b01da65d2a20a4a9e3b58c29b4fd20` |
| Pubs | `pubs-sqlite` | [3e37e01](https://github.com/demo-db/pubs/tree/3e37e01e28f610f1d65c9e809a79ab6522928ad2) | `b45b08b7c06441cc0b138b031ea5bd32bd5866aebf874c89d2ebf7fc6abb3691` |
| Sakila | `sakila-sqlite` | [7e7de96](https://github.com/demo-db/sakila/tree/7e7de96d904dedc130165691e59a8268ce5fb6d2) | `9bebeee50fecb1fee115c206a4f380f2f6d1f009e7796b18b8a8cfba7c810454` |
| AdventureWorks | `adventureworks-sqlite` | [b4f6a99](https://github.com/demo-db/adventureworks/tree/b4f6a9909c0de58767663dce9006c7ac522ce6a7) | `6a105e1982becfe003fc7a307d7cad9d738390cedd79d166c2167fd817168109` |
| Employees | `employees-sqlite` | [397f3e3](https://github.com/demo-db/employees/tree/397f3e32cb970e55bc4a528bb255c41272f6103f) | `46b49dd0e141cd8db66d57680a10febfccc15e6f54dc7b8f3c2316b55e11c5f0` |

To verify the saved SQL against those same SQLite files, stage them in one
directory as `chinook.sqlite`, `northwind.sqlite`, `pubs.sqlite`,
`sakila.sqlite`, `adventureworks.sqlite`, and `employees.sqlite`, then run:

```sh
python3 scripts/verify-demodb-guided-queries.py /path/to/sqlite-fixtures
```

The verifier opens inputs read-only, checks their catalogue SHA-256 values, and
compares every returned row with the checked-in result snapshot. It needs only
Python's standard library. No database files are copied into this project.

## Chinook

1. [Rank customer spend](chinook/top-customer-spend.query.sql) — Join customers
   to invoices and compare total spend. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fchinook%2Ftop-customer-spend?id=demodb%2Fchinook%2Ftop-customer-spend).
   Expected: 10 rows; Helena Holý leads with 7 invoices and 4,962 cents.
2. [Explore a customer's genre mix](chinook/customer-genre-mix.query.sql) —
   Follow invoices through line items, tracks, and genres for customer 5.
   [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fchinook%2Fcustomer-genre-mix?id=demodb%2Fchinook%2Fcustomer-genre-mix).
   Expected: 8 genres; Rock leads with 4 invoices and 1,485 cents.
3. [Compare playlist coverage](chinook/playlist-composition.query.sql) — Use
   the `(PlaylistId, TrackId)` bridge to count tracks and albums without
   multiplying duplicate playlist names. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fchinook%2Fplaylist-composition?id=demodb%2Fchinook%2Fplaylist-composition).
   Expected: 10 rows; “Music” has 3,290 distinct tracks across 335 albums.

Money totals are represented as integer cents before aggregation, so the
exercise does not add floating-point invoice amounts directly.

## Northwind

1. [Compare customer orders](northwind/top-customer-orders.query.sql) — Join
   customers, orders, and the composite-key `Order Details` table. Discounted
   line totals are rounded to cents before summing. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fnorthwind%2Ftop-customer-orders?id=demodb%2Fnorthwind%2Ftop-customer-orders).
   Expected: 10 customers; QUICK-Stop leads with 28 orders and 11,027,732 cents.
2. [Inspect territory coverage](northwind/territory-coverage.query.sql) —
   Trace Regions through Territories and the composite-key EmployeeTerritories
   bridge. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fnorthwind%2Fterritory-coverage?id=demodb%2Fnorthwind%2Fterritory-coverage).
   Expected: 10 territories; Eastern / Westboro has one assigned employee.
3. [Find products to reorder](northwind/reorder-watchlist.query.sql) — Join
   products to category and supplier, then compare stock with reorder level.
   [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fnorthwind%2Freorder-watchlist?id=demodb%2Fnorthwind%2Freorder-watchlist).
   Expected: 10 products; Gorgonzola Telino has 0 units in stock against a
   reorder level of 20.

## Pubs

1. [Browse author portfolios](pubs/author-catalog.query.sql) — Join authors,
   titleauthor, and titles; `titleauthor` has a composite author/title key.
   [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fpubs%2Fauthor-catalog?id=demodb%2Fpubs%2Fauthor-catalog).
   Expected: 10 authors; Stearns MacFeather is linked to 2 titles worth 3,354
   cents at list price.
2. [Compare store sales](pubs/store-title-sales.query.sql) — Join stores,
   sales, and titles and count orders by title. `sales` uses a composite key.
   [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fpubs%2Fstore-title-sales?id=demodb%2Fpubs%2Fstore-title-sales).
   Expected: 10 store/title pairs; Barnum's sold 75 copies of “Is Anger the
   Enemy?”.
3. [Inspect royalty steps](pubs/royalty-steps.query.sql) — Follow each
   royalty range back to its title. `roysched` has no declared key, so do not
   treat a row position as a stable identifier. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fpubs%2Froyalty-steps?id=demodb%2Fpubs%2Froyalty-steps).
   Expected: 10 ranges; BU1032 starts at 10% for 0–5,000 copies.

Pubs and Sakila monetary values are returned as integer cents to keep the
aggregates exact at the currency's two-decimal scale.

## Sakila

1. [Compare category revenue](sakila/category-revenue.query.sql) — Join
   categories to films, inventory, rentals, and payments. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fsakila%2Fcategory-revenue?id=demodb%2Fsakila%2Fcategory-revenue).
   Expected: 10 categories; Sports leads with 1,179 rentals and 531,421 cents.
2. [Browse actor filmographies](sakila/actor-filmographies.query.sql) — Follow
   the composite-key film_actor bridge and count distinct films per actor.
   [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fsakila%2Factor-filmographies?id=demodb%2Fsakila%2Factor-filmographies).
   Expected: 10 actors; Gina Degeneres appears in 42 films.
3. [Find overdue open rentals](sakila/overdue-open-rentals.query.sql) — Join
   customers, rentals, inventory, and films; compare due dates against the
   fixed snapshot date of 2005-08-31. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fsakila%2Foverdue-open-rentals?id=demodb%2Fsakila%2Foverdue-open-rentals).
   Expected: one overdue open rental: ACADEMY DINOSAUR, due 2005-08-27.

## AdventureWorks

1. [Compare yearly territory sales](adventureworks/territory-year-sales.query.sql)
   — Join order headers, composite-key order details, and territories by year.
   [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fadventureworks%2Fterritory-year-sales?id=demodb%2Fadventureworks%2Fterritory-year-sales).
   Expected: 10 territory/year pairs; Southwest leads 2025 with 2,375 orders
   and 3,966,506,678,222 micro-units.
2. [Rank products by category sales](adventureworks/top-product-categories.query.sql)
   — Join sales details through products, subcategories, and categories.
   [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fadventureworks%2Ftop-product-categories?id=demodb%2Fadventureworks%2Ftop-product-categories).
   Expected: 10 products; Mountain-200 Black, 38 leads with 2,977 units.
3. [Inspect current department history](adventureworks/current-department-roster.query.sql)
   — Join department history to employees, people, and departments. The source
   marks current assignments with a null EndDate and uses a composite key for
   history rows. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Fadventureworks%2Fcurrent-department-roster?id=demodb%2Fadventureworks%2Fcurrent-department-roster).
   Expected: 10 employees; the first is Zainal Arifin in Document Control.

AdventureWorks stores `LineTotal` as decimal text with six fractional digits.
The queries convert each value to integer micro-units before summing.

## Employees

1. [Compare current salaries](employees/top-current-salaries.query.sql) — Join
   employees to the effective-dated salaries table and select the open-ended
   current row. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Femployees%2Ftop-current-salaries?id=demodb%2Femployees%2Ftop-current-salaries).
   Expected: 10 employees; Arno Kumaresan leads at 136,004.
2. [Count department headcount](employees/department-headcount.query.sql) —
   Join department assignments and count distinct employees whose assignment
   has no end date. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Femployees%2Fdepartment-headcount?id=demodb%2Femployees%2Fdepartment-headcount).
   Expected: 9 departments; Development has 205 current employees.
3. [Inspect department managers](employees/department-managers.query.sql) —
   Join current manager assignments to departments and employees. [Open in DataTug](https://datatug.app/pwa/agent/github/project/datatug-demo-project@datatug/query/demodb%2Femployees%2Fdepartment-managers?id=demodb%2Femployees%2Fdepartment-managers).
   Expected: 9 managers; Marketing is led by Vishwani Minakawa from 1991-10-01.

The effective-dated `salaries`, `titles`, `dept_emp`, and `dept_manager` tables
use composite primary keys; the examples select current salary rows by their
open-ended end date, and current department rows by a null end date.
