# Table: [main](..).[Customer]
<no value>

```
USE chinook;
SELECT * FROM main.Customer;
```



## Primary key
`PK_Customer` (**CustomerId**)

## Foreign keys
- `FK_Customer2{Employee true}` (**EmployeeId**) ⇒ [main](../../../main).[Employee](../../../main/tables/Employee)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Customer%0ALEFT+JOIN+main.Employee+ON+Employee.EmployeeId+%3D+Customer.EmployeeId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Customer%0AINNER+JOIN+main.Employee+ON+Employee.EmployeeId+%3D+Customer.EmployeeId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Customer%0ARIGHT+JOIN+main.Employee+ON+Employee.EmployeeId+%3D+Customer.EmployeeId' target='_blank'>RIGHT</a>

## Columns
- `CustomerId` INTEGER
  - *Indexes*: `IPK_Customer`
- `FirstName` NVARCHAR(40)
- `LastName` NVARCHAR(20)
- `Company` NVARCHAR(80)
- `Address` NVARCHAR(70)
- `City` NVARCHAR(40)
- `State` NVARCHAR(40)
- `Country` NVARCHAR(40)
- `PostalCode` NVARCHAR(10)
- `Phone` NVARCHAR(24)
- `Fax` NVARCHAR(24)
- `Email` NVARCHAR(60)
- `SupportRepId` INTEGER
  - *Indexes*: `IFK_CustomerSupportRepId`

## Indexes
- IFK_CustomerSupportRepId (SupportRepId) ``
- IPK_Customer (CustomerId) `` - `UNIQUE`

## Referenced by

- [main](../../../main).[Invoice](../../../main/tables/Invoice)
  - `FK_Invoice2{Customer true}_CustomerId`
    <br>by columns: `CustomerId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Customer%0ALEFT+JOIN+main.Invoice+ON+Invoice.CustomerId+%3D+Customer.CustomerId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Customer%0AINNER+JOIN+main.Invoice+ON+Invoice.CustomerId+%3D+Customer.CustomerId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Customer%0ARIGHT+JOIN+main.Invoice+ON+Invoice.CustomerId+%3D+Customer.CustomerId' target='_blank'>RIGHT</a>
    </small>

  - Referenced by:

    - [main](../../../main).[InvoiceLine](../../../main/tables/InvoiceLine)
      - `FK_InvoiceLine2{Invoice true}_InvoiceId`
        <br>by columns: `InvoiceId` &mdash;
        <small>JOIN:
        <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Invoice%0ALEFT+JOIN+main.InvoiceLine+ON+InvoiceLine.InvoiceId+%3D+Invoice.InvoiceId' target='_blank'>LEFT</a> |
        <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Invoice%0AINNER+JOIN+main.InvoiceLine+ON+InvoiceLine.InvoiceId+%3D+Invoice.InvoiceId' target='_blank'>INNER</a> |
        <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Invoice%0ARIGHT+JOIN+main.InvoiceLine+ON+InvoiceLine.InvoiceId+%3D+Invoice.InvoiceId' target='_blank'>RIGHT</a>
        </small>

