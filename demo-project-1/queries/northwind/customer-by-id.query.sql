SELECT CustomerID, CompanyName, ContactName, ContactTitle, City, Country, Phone
FROM Customers
WHERE CustomerID = @CustomerID
