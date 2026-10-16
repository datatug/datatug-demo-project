# Orders in motion

`board.json` is the shareable showcase. `?mode=tutorial` derives a browser session
copy and reveals the cards in order: `orders-by-month-country`,
`northwind-shipping-countries`, then `source-inspector`. Tutorial actions do not
edit the saved project.

The race binds `demodb/northwind-orders-browser-sqlite`: read-only SQL selecting
all 830 Orders and all 14 fields. The browser derives monthly shipping-country
order counts from these records. The country bar binds
`demodb/northwind-country-counts-browser-sqlite`, independently executing SQL
for all 21 countries and 830 total orders. These charts count orders.

The inspector has three independent saved SQL tabs: the complete Northwind
Orders projection, the Northwind country counts, and Chinook customer billing.
Chinook `TotalCents` sums invoice billing in integer cents per customer. It is a
separate dataset and measure.

## Browser execution

The DataTug app bundles immutable SQLite snapshots and runs these queries in its
existing sql.js WASM worker. The connection catalog declares each relative asset
URL, size and SHA-256. The runtime admits only the shipped asset paths with their
exact pins, checks the download size and hash, validates each saved query's SQL
identity and complete result shape, then creates snapshot execution evidence.
The browser runtime has a 1,000-row cap; the complete Orders result is 830 rows.
No Cloudflare Worker query endpoint is required for these three tabs or charts.

- Northwind: 602112 bytes, SHA-256
  `279b34136771aee75d802094b3329515a2b01da65d2a20a4a9e3b58c29b4fd20`,
  from `demo-db/northwind` revision
  `76fe0a1ccc82b6c0c5a035d76c9df7522713d618`, `artifacts/northwind.sqlite`.
- Chinook: 1007616 bytes, SHA-256
  `7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15`,
  from `demo-db/chinook` revision
  `85ad3b4d4014dd5a6ee506410beee99771801811`, `artifacts/data/chinook.sqlite`.

Both datasets retain their upstream MIT notices beside the app assets. Source
usage details show the original repository, pin, attribution and transformations.
Results and receipts stay in the viewer session. Unavailable or changed sources
show an error. The older public DTQL queries and their historical live API
receipt remain separate assets; browser SQLite does not inherit that receipt.
