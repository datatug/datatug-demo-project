# Orders in motion

`board.json` is the shareable showcase. `?mode=tutorial` derives a browser session
copy from the saved canonical cards and guides their construction in board
order: `orders-by-month-country`, `northwind-shipping-countries`,
`shared-customer-countries`, `customer-country-sources`, and `source-inspector`.
The independent-source card starts with one source before adding the second.
Tutorial actions do not edit the saved project.

The normal board and tutorial execute read-only server DTQL. The existing
Northwind shipping sources use `ovdb.demodb.dev`; customer comparisons use
`cloud.openvaultdb.com` through the normal direct OVDB dispatcher.
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
The current public server publishes an empty server identity and omits structured source-rights evidence. The inspector uses the existing legacy mode, binding HTTPS requests to the selected base URL and database without asserting a server identity. Generic
inspector results preserve that absence and do not claim publisher admission.

The saved-query inspector occupies its own full-width row; the shipping-country chart keeps its six-column slot for future chart space. Tabs retain their stable IDs and saved query references; layout changes do not rerun held results.


## Independent customer-country sources

The full-width `customer-country-sources` plain bar card compares two saved
queries: `demodb/northwind-customer-country-counts-server` and
`demodb/chinook-customer-country-counts-server`. Each independently counts
unique customer keys in its own physical table (`northwind/Customers` and
`chinook/Customer`), groups exact `Country` labels, and returns `country`
(string) plus `customers` (integer), ordered by country with a 100-group bound.
The common declared unit is **customer records**. This is an independent-source
comparison; it does not identify the same people in the two samples.

Each query explicitly excludes null countries. The card discloses the dated
local fixture observation: on 2026-10-21, Northwind had two excluded customer
records and Chinook had none. Those are fixture observations, not dynamically
measured exclusions in the live result. Live data can change. No country alias
normalization occurs: `UK` and `United Kingdom` remain separate categories.
Only complete source results can be combined. The chart uses the full union of
observed country labels and retains an absent source value as missing.

This new card is separate from the existing `shared-customer-countries` card.
That card retains the single server federation query
`demodb/customer-country-comparison-server`, distinct per-source counts, and
its exact-label shared-country scope. Adding independent sources does not
change its query, selection behavior, or the Shipping board.

The local fixture checks used read-only SQLite connections to these existing
artifacts (no fixture download or browser database execution):

| Source | Artifact SHA-256 | Non-null groups | Customer records counted |
| --- | --- | ---: | ---: |
| Northwind | `279b34136771aee75d802094b3329515a2b01da65d2a20a4a9e3b58c29b4fd20` | 21 | 91 |
| Chinook | `7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15` | 24 | 59 |

These observations validate the measure and null disclosure; they do not prove
current server results or browser acceptance. Deployment of the Apps support
for independent chart sources must precede publishing this board revision.


## Pending customer-collection rights publication

The five customer-reading server definitions now bind the selected API base to
its canonical operator identity, `https://demodb.dev/ovdb`: the two independent
customer-country aggregates, the existing shared-country federation, Chinook
billing, and the hosted customer preview. The client normalizes the preview's
legacy `https://demodb.dev/ovdb` API base to `https://ovdb.demodb.dev` for both
execution and identity comparison.

This binding depends on the provider owner publishing that stable identity and
structured server-declared terms for exactly `northwind/Customers` and
`chinook/Customer`, with matching live source usage evidence. Until that
publication is verified, these staged definitions may refuse execution. The
empty-identity observation above describes the preceding server state; it is
not a claim that this dependency has been deployed. Server-declared terms are
separate from the existing publisher-verified Orders sidecars. The Orders
query bodies, publisher pins, and strict 830-order/21-country admissions stay
unchanged. Customer terms must not be expanded to Orders through a database or
server-wide declaration as part of this publication.
