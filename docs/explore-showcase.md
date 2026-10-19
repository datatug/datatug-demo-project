# Explore the Northwind and Chinook showcase

[Open the dashboard](https://datatug.app/project/github.com/datatug/datatug-demo-project/tree/HEAD/demo-project-1/-/board/showcase).
You can inspect the public results without copying a project or database.

Sorting and Monthly trend below describe the next exploration update. They
are not a claim that those controls are already deployed.

## Compare customer records

**Customer records by shared country** compares Northwind and Chinook counts
for 17 exact country labels present in both sources. These are customer
records, not identified people shared between the databases. UK variants and
null country labels are excluded; the comparison does not normalize names.
Both series use customer-record units and the same zero-based scale.

Choose **Country**, **Northwind**, **Chinook**, or **Difference** to reorder the
comparison. Difference means **Northwind minus Chinook**, in customer records:
positive values favour Northwind and negative values favour Chinook. Count
and difference sorts put larger values first; Country sorts labels
alphabetically. Ties use the country label. Sorting changes presentation,
not the source query or counts.

Select **Canada**: the comparison shows Northwind **3** and Chinook **8**.
The linked Orders inspector shows **30 of 830 orders shipped to Canada**.
This is a shipping-destination filter, not a join between those customer
records and Orders. **Clear** restores all 830 Orders. The other inspector
tabs remain independent saved queries.

## See the monthly pattern

In the Orders card, choose **Monthly trend** alongside the race and source
rows. This reusable presentation uses the same held, complete 830 Orders,
grouped by **OrderDate** calendar month: July 2016 through May 2018,
23 months, with monthly counts summing to 830. It does not sum the race's
visible Top N countries. The line counts all orders, not revenue, customer
records or shipment completion dates. Missing months within the observed
range are shown as zero.

Changing presentation does not run another query, copy a database or save a
new line-chart definition. The paused race keeps its position. Use the data
alternative to inspect month labels and exact counts without relying on the
line or colour.

## Inspect, refresh and recover

Switch **Chart/Rows** to inspect the held result. Open the saved query or
source details to check its columns, source identity and data terms. In
**Inspect saved query results**, the Northwind Orders tab exposes the full
14-column result; the other tabs expose their own saved queries.

- [Comparison query definition](../demo-project-1/queries/demodb/customer-country-comparison-server.query.json)
- [Complete Orders query definition](../demo-project-1/queries/demodb/northwind-orders-full-sqlite.query.json)
- [Canonical dashboard definition](../demo-project-1/boards/showcase/board.json)

**Refresh** deliberately executes the query again. If loading fails, read the
error and use **Retry**; an incomplete result must not be presented as a
complete trend. Sorting, selection, Clear and presentation switching reuse
held data.

## Take the guided tour

[Start the tutorial](https://datatug.app/project/github.com/datatug/datatug-demo-project/tree/HEAD/demo-project-1/-/board/showcase?mode=tutorial).
It constructs a browser-session presentation of the dashboard. Next,
Previous and Restart do not save changes to the canonical project.
**Show Full Dashboard** returns to the saved dashboard from any stage.

## Make it yours

Project copying and database exporting serve different purposes:

- **GitHub project:** choose a repository you can write to, review the source
  and destination, and follow the setup pull request. Reopen the destination
  after merging. The authenticated copy → setup PR → merge → reopen →
  **Query This Table** journey is still being accepted; it is not yet a
  verified end-to-end result. A real sign-in may be required.
- **Local / DataTug CLI:** use the existing local project destination with
  your DataTug CLI connection. The released CLI can read this project's
  definitions; this does not turn server queries into downloaded databases.
- **Browser database copy/export:** a separate flow creates an editable local
  SQLite database and exports its database bytes, including local edits.
  That export is not a GitHub project copy or a copy of hosted DemoDB services.

The [direct log investigation](logs/guide.md) is a separate walkthrough using
real Northwind records and explicitly synthetic log inputs.
