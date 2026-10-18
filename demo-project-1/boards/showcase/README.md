# Orders in motion

`board.json` is the shareable showcase. `?mode=tutorial` derives a browser session
copy and reveals the cards in order: `orders-by-month-country`,
`northwind-shipping-countries`, then `source-inspector`. Tutorial actions do not
edit the saved project.

The normal board and tutorial execute read-only DTQL on `ovdb.demodb.dev`.
They do not download SQLite fixtures. The existing browser SQL examples remain
available as explicit saved queries; `/demo/sqlite` provides the editable local
clone journey.

The race binds `demodb/northwind-orders-full-sqlite`, the exact published
14-field DTQL projection of all 830 Northwind Orders. Despite the historical
query ID, execution happens on the server. The browser derives 23 monthly
shipping-country frames from the complete result. The country bar binds
`demodb/northwind-shipping-country-count-sqlite`, the exact published aggregate
of 21 countries and 830 total orders.

These two chart queries use the existing publisher admission: the app fetches
a small pinned rights publication, checks the exact saved query text and full
result, and preserves attribution. They do not inherit rights from the generic
server runtime. Changed or incomplete results fail closed.

The inspector uses `demodb/northwind-orders-server`,
`demodb/northwind-country-counts-server`, and `demodb/chinook-billing-server`.
Their relational server responses include columns, execution sources and
completion. The board reads all retained result pages up to 1,000 rows before
disposing the worker session. Chinook joins Customer and Invoice, groups by
customer, and shows the top ten with `InvoiceCount` and `Total` in currency
units. It is a separate dataset and measure.

Held results are shared within the board for an exact query definition and
runtime; context changes invalidate reuse. Chart/grid switches do not execute
queries. The chart's publisher-admitted Orders query and the inspector's
relational Orders query have different text and identities, so opening both
executes two Orders requests. The same applies to the two country queries.
The current public server omits structured source-rights evidence. Generic
inspector results preserve that absence and do not claim publisher admission.
