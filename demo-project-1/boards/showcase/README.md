# Orders in motion

`board.json` defines the canonical end state for the shareable showcase. The
Apps runtime and tutorial overlay are being integrated separately. The planned
`?mode=tutorial` route derives a sparse browser-session copy from this board and
reveals canonical card IDs in order: `orders-by-month-country`,
`northwind-shipping-countries`, then `source-inspector`. Tutorial actions must
not edit this file or the saved project.

The race card binds `demodb/northwind-orders-full-sqlite`, a saved DTQL query
for all 14 Orders fields, then derives monthly shipping-country order counts from
the admitted 830 records. It is an **order-count** race, not revenue. The
country bar binds an independent SQLite aggregate. The current chart wire's
`orders-monthly-country-count` transform supports the race only; admitting the
bar's separate 21-row aggregate requires its own verified runtime result and
publisher rights for the underlying Orders source. Chart presentation should
change without changing either source query.

The inspector defines three independent saved-query tabs: the raw SQLite Orders
projection, the PostgreSQL country-count aggregate, and a Chinook customer
billing SQL query. They are not a federated query or a combined chart. Chinook
`TotalCents` is invoice billing in cents; the Northwind cards count orders by
shipping destination. Those measures cannot be compared on one numeric scale.

## Runtime evidence and gates

- The full Orders query body matches the provider's pinned public projection
  in `demo-db/northwind/artifacts/hosting-imports/public-orders-evidence-2026-10-16.json`.
  Its local SQLite and observed public API results contained 830 rows with
  14 fields and canonical row digest
  `69e054b6e952a3c1df7b549fdf7b474a353f18edd9f968560ad1d4bfb6894f0a`.
  The app must verify current complete response, schema, row count and digest
  at runtime before admitting it to the race. The digest is evidence, not saved
  chart data.
- The SQLite country-count and PostgreSQL country-count queries each returned
  21 distinct countries and 830 total orders in the
  [saved source receipt](../../queries/demodb/visual-showcase-source-receipt.json).
  These are separate public API executions. The bar may render only after the
  current aggregate response is independently admitted and its source rights
  verified. PostgreSQL is inspect-only until its hosting provider supplies
  suitable chart rights evidence.
- The Chinook SQL tab targets the existing `chinook-sqlite` pinned browser
  fixture and has a saved standalone query. It remains a grid/inspection tab;
  this board does not infer Chinook chart rights from Northwind's publisher.
- The saved board contains only query IDs and chart settings. Results,
  execution receipts, rights, and tutorial action history are resolved or kept
  in the viewer session. An unavailable, incomplete, or unauthorized source
  must show a visible limited/error state instead of a fabricated chart.
- Rendering nested saved-query tabs and automatically executing them is an Apps
  integration gate. This board definition does not prove that browser path.
