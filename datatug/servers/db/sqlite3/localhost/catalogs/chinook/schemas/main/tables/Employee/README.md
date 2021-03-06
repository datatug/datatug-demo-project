# Table: [main](..).[Employee]
<no value>

```
USE chinook;
SELECT * FROM main.Employee;
```



## Primary key
`PK_Employee` (**EmployeeId**)

## Foreign keys
- `FK_Employee2{Employee true}` (**EmployeeId**) ⇒ [main](../../../main).[Employee](../../../main/tables/Employee)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Employee%0ALEFT+JOIN+main.Employee+ON+main.Employee.EmployeeId+%3D+main.Employee.EmployeeId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Employee%0AINNER+JOIN+main.Employee+ON+main.Employee.EmployeeId+%3D+main.Employee.EmployeeId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Employee%0ARIGHT+JOIN+main.Employee+ON+main.Employee.EmployeeId+%3D+main.Employee.EmployeeId' target='_blank'>RIGHT</a>

## Columns
- `EmployeeId` INTEGER
  - *Indexes*: `IPK_Employee`
  - *Foreign key*: `FK_Employee2{Employee true}`
- `LastName` NVARCHAR(20)
- `FirstName` NVARCHAR(20)
- `Title` NVARCHAR(30)
- `ReportsTo` INTEGER
  - *Indexes*: `IFK_EmployeeReportsTo`
- `BirthDate` DATETIME
- `HireDate` DATETIME
- `Address` NVARCHAR(70)
- `City` NVARCHAR(40)
- `State` NVARCHAR(40)
- `Country` NVARCHAR(40)
- `PostalCode` NVARCHAR(10)
- `Phone` NVARCHAR(24)
- `Fax` NVARCHAR(24)
- `Email` NVARCHAR(60)

## Indexes
- IFK_EmployeeReportsTo (ReportsTo) ``
- IPK_Employee (EmployeeId) `` - `UNIQUE`

## Referenced by

- [main](../../../main).[Customer](../../../main/tables/Customer)
  - `FK_Customer2{Employee true}`
    <br>by columns: `EmployeeId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Employee%0ALEFT+JOIN+main.Customer+ON+Customer.EmployeeId+%3D+Employee.EmployeeId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Employee%0AINNER+JOIN+main.Customer+ON+Customer.EmployeeId+%3D+Employee.EmployeeId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Employee%0ARIGHT+JOIN+main.Customer+ON+Customer.EmployeeId+%3D+Employee.EmployeeId' target='_blank'>RIGHT</a>
    </small>

  - Referenced by:

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

