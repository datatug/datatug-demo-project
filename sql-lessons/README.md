# SQL lessons

A separate public read-only project for educational query links. Opening a link creates an **unsaved editor**; this project contains no saved query definitions or query text parameters in project files.

- `chinook-teaching-sqlite` uses the reviewed teaching extract: four customers and 21 invoices. Customer 4 deliberately has no invoices **in this extract**. The complete source has that customer's invoices.
- `chinook-sqlite` retains the exact full connection from `demo-project-1`: 59 customers and 412 invoices.

Both run against pinned SQLite files served by DataTug, using its existing read-only worker. The teaching artifact, fixture SQL, rights and single contract in `fixtures/` are copies of the reviewed Apps publication. They make this project's CI self-contained; there is no hidden sibling checkout requirement.

The extract projects only the lesson columns, retains source values unchanged, and preserves the MIT licence and original full provider pin. Its rights publication names the pinned source SQL and explicitly describes the derivative transformations. It is not the complete Chinook database. `chinook-teaching-contract.json` records the output SHA-256/size and upstream/input pins.

Links use `/project/github.com/datatug/datatug-demo-project/sql-lessons/-/query?q=<encoded exact text>&queryType=sql&connection=chinook-teaching-sqlite&run=1`. `queryType` is required; only SQL is supported by this read-only link workflow. Select `connection=chinook-sqlite` explicitly for full-database exploration, whose results can differ from the lesson tables.
