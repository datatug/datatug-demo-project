# Explore the Northwind and Chinook showcase

[Open the dashboard](https://datatug.app/project/github.com/datatug/datatug-demo-project/demo-project-1/-/board/showcase).
You can inspect the public results without copying a project or database.

## Compare customer records

**Customer records by shared country** compares Northwind and Chinook counts
for 17 exact country labels present in both sources. These are customer
records, not identified people shared between the databases. UK variants and
null country labels are excluded; the comparison does not normalize names.
Both series use customer-record units and the same zero-based scale.

Use **Chart order** to choose **Country (A–Z)**, **Northwind (high to low)**,
**Chinook (high to low)**, or **Difference (Northwind − Chinook)**.
Difference means **Northwind minus Chinook**, in customer records:
positive values favour Northwind and negative values favour Chinook. Count
and difference sorts put larger values first; Country sorts labels
alphabetically. Ties use the country label. Sorting changes presentation,
not the source query or counts.

Select **Canada**: the comparison shows Northwind **3** and Chinook **8**.
The linked Orders inspector shows **30 of 830 orders shipped to Canada**.
This is a shipping-destination filter, not a join between those customer
records and Orders. **Clear country** restores all 830 Orders. The other
inspector tabs remain independent saved queries.

## See the monthly pattern

In the Orders card, choose **Chart** for the race, **Monthly trend** for the
overview, or **Source rows** for its held data. The monthly presentation uses
the same complete 830 Orders, grouped by **OrderDate** calendar month:
July 2016 through May 2018,
23 months, with monthly counts summing to 830. The observed **OrderDate**
range is **2016-07-04–2018-05-06**. Counts cover the available observed sample
dates; boundary months may be partial.

Selecting a country or changing the race's Top N does not filter this
overview. The line counts all orders, not revenue, customer records or
shipment completion dates. Missing months within the observed
range are shown as zero.

Changing presentation does not run another query, copy a database or save a
new line-chart definition. The paused race keeps its position. Use the data
alternative, **Monthly data (23 months)**, to inspect every month and exact
count without relying on the line or colour. Its table is titled
**All source orders per calendar month** and includes a total of **830**.

## Inspect, refresh and recover

In the comparison card, switch **Chart** or **Rows** to inspect its held
result. The Orders card has its own **Source rows** view. Open the saved
query or source details to check columns, source identity and data terms. In
**Inspect saved query results**, the Northwind Orders tab exposes the full
14-column result; the other tabs expose their own saved queries.

- [Comparison query definition](../demo-project-1/queries/demodb/customer-country-comparison-server.query.json)
- [Complete Orders query definition](../demo-project-1/queries/demodb/northwind-orders-full-sqlite.query.json)
- [Canonical dashboard definition](../demo-project-1/boards/showcase/board.json)

**Refresh chart** deliberately executes the query again. If loading fails,
read the error and use **Retry chart**; an incomplete result must not be
presented as a complete trend. Sorting, selection, **Clear country** and
presentation switching reuse held data.

## Take the guided tour

[Start the tutorial](https://datatug.app/project/github.com/datatug/datatug-demo-project/demo-project-1/-/board/showcase?mode=tutorial).
It constructs a browser-session presentation of the dashboard. **Next Step**,
**Previous** and **Restart** do not save changes to the canonical project.
The guide introduces the monthly trend, then source rows, then the paused
race. Each step's heading describes the next action.
**Show Full Dashboard** returns to the saved dashboard from any stage.

## Make it yours

Project copying and database exporting serve different purposes:

- **GitHub project:** choose a repository you can write to, review the source
  and destination, and follow the setup pull request. Reopen the destination
  after merging. The authenticated copy → setup PR → merge → reopen →
  **Query This Table** journey is still being accepted; it is not yet a
  verified end-to-end result. A real sign-in may be required.
- **Local Git / DataTug CLI:** choose **Clone a local Git repository** in the
  editable database's project-copy offer. The generated commands clone the
  project files and register the project with the CLI. **Download edited
  SQLite** exports the database you have edited in the browser; enter the
  actual **Downloaded SQLite file path** so the generated commands can
  register that file in the cloned project's local environment. The CLI then
  opens its generated local project link. Cloning project definitions alone
  does not download the browser's edited database or hosted DemoDB services.
- **Browser database copy/export:** a separate flow creates an editable local
  SQLite database and exports its database bytes, including local edits.
  That export is not a GitHub project copy or a copy of hosted DemoDB services.

The local handoff above describes the application's generated flow. The
complete browser handoff with released DataTug CLI **v0.103.2** is **not yet
accepted**. Follow the commands generated for your actual project and file
path; this page is not a separately executed command runbook.

The [direct log investigation](logs/guide.md) is a separate walkthrough using
real Northwind records and explicitly synthetic log inputs.
