SELECT OrderID, OrderDate, ShippedDate, ShipCountry, Freight
FROM Orders
WHERE CustomerID = @CustomerID
ORDER BY OrderDate DESC, OrderID DESC
LIMIT 20
