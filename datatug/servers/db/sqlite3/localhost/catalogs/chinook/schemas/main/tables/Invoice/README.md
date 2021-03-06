# Table: [main](..).[Invoice]
<no value>

```
USE chinook;
SELECT * FROM main.Invoice;
```



## Primary key
`PK_Invoice` (**InvoiceId**)

## Foreign keys
- `FK_Invoice2{Customer true}_CustomerId` (**CustomerId**) ⇒ [main](../../../main).[Customer](../../../main/tables/Customer)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Invoice%0ALEFT+JOIN+main.Customer+ON+Customer.CustomerId+%3D+Invoice.CustomerId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Invoice%0AINNER+JOIN+main.Customer+ON+Customer.CustomerId+%3D+Invoice.CustomerId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Invoice%0ARIGHT+JOIN+main.Customer+ON+Customer.CustomerId+%3D+Invoice.CustomerId' target='_blank'>RIGHT</a>

## Columns
- `InvoiceId` INTEGER
  - *Indexes*: `IPK_Invoice`
- `CustomerId` INTEGER
  - *Indexes*: `IFK_InvoiceCustomerId`
  - *Foreign key*: `FK_Invoice2{Customer true}_CustomerId`
- `InvoiceDate` DATETIME
- `BillingAddress` NVARCHAR(70)
- `BillingCity` NVARCHAR(40)
- `BillingState` NVARCHAR(40)
- `BillingCountry` NVARCHAR(40)
- `BillingPostalCode` NVARCHAR(10)
- `Total` NUMERIC(10,2)

## Indexes
- IFK_InvoiceCustomerId (CustomerId) ``
- IPK_Invoice (InvoiceId) `` - `UNIQUE`

## Referenced by

- [main](../../../main).[InvoiceLine](../../../main/tables/InvoiceLine)
  - `FK_InvoiceLine2{Invoice true}_InvoiceId`
    <br>by columns: `InvoiceId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Invoice%0ALEFT+JOIN+main.InvoiceLine+ON+InvoiceLine.InvoiceId+%3D+Invoice.InvoiceId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Invoice%0AINNER+JOIN+main.InvoiceLine+ON+InvoiceLine.InvoiceId+%3D+Invoice.InvoiceId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Invoice%0ARIGHT+JOIN+main.InvoiceLine+ON+InvoiceLine.InvoiceId+%3D+Invoice.InvoiceId' target='_blank'>RIGHT</a>
    </small>

