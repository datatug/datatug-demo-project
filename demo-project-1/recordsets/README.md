# Recordsets

- [support-notes](support-notes.recordset.json) — dataset definition (columns, types,
  `ChinookCustomer.ID` on `CustomerId`, and `Country.Name` on `Country`) for the
  `support-notes` collection. The actual records live outside this definition, in the
  inGitDB database at [`../data/ingitdb`](../data/ingitdb) (collection
  `support-notes`), loaded through `ingitdb://<path-to-data/ingitdb>`. This file
  documents the shape; it carries no `files`
  entry because the row data is not duplicated here.
