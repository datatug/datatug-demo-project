# Table: [main](..).[InvoiceLine]
<no value>

```
USE chinook;
SELECT * FROM main.InvoiceLine;
```



## Primary key
`PK_InvoiceLine` (**InvoiceLineId**)

## Foreign keys
- `FK_InvoiceLine2{Track true}_TrackId` (**TrackId**) ⇒ [main](../../../main).[Track](../../../main/tables/Track)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.InvoiceLine%0ALEFT+JOIN+main.Track+ON+Track.TrackId+%3D+InvoiceLine.TrackId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.InvoiceLine%0AINNER+JOIN+main.Track+ON+Track.TrackId+%3D+InvoiceLine.TrackId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.InvoiceLine%0ARIGHT+JOIN+main.Track+ON+Track.TrackId+%3D+InvoiceLine.TrackId' target='_blank'>RIGHT</a>
- `FK_InvoiceLine2{Invoice true}_InvoiceId` (**InvoiceId**) ⇒ [main](../../../main).[Invoice](../../../main/tables/Invoice)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.InvoiceLine%0ALEFT+JOIN+main.Invoice+ON+Invoice.InvoiceId+%3D+InvoiceLine.InvoiceId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.InvoiceLine%0AINNER+JOIN+main.Invoice+ON+Invoice.InvoiceId+%3D+InvoiceLine.InvoiceId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.InvoiceLine%0ARIGHT+JOIN+main.Invoice+ON+Invoice.InvoiceId+%3D+InvoiceLine.InvoiceId' target='_blank'>RIGHT</a>

## Columns
- `InvoiceLineId` INTEGER
  - *Indexes*: `IPK_InvoiceLine`
- `InvoiceId` INTEGER
  - *Indexes*: `IFK_InvoiceLineInvoiceId`
  - *Foreign key*: `FK_InvoiceLine2{Invoice true}_InvoiceId`
- `TrackId` INTEGER
  - *Indexes*: `IFK_InvoiceLineTrackId`
  - *Foreign key*: `FK_InvoiceLine2{Track true}_TrackId`
- `UnitPrice` NUMERIC(10,2)
- `Quantity` INTEGER

## Indexes
- IFK_InvoiceLineTrackId (TrackId) ``
- IFK_InvoiceLineInvoiceId (InvoiceId) ``
- IPK_InvoiceLine (InvoiceLineId) `` - `UNIQUE`

## Referenced by
*None*

