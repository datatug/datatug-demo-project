SELECT o.OrderID, o.CustomerID, c.CompanyName AS CustomerName, o.OrderDate, o.ShippedDate,
       o.ShipVia, s.CompanyName AS ShipperName
FROM Orders o
JOIN Customers c ON c.CustomerID = o.CustomerID
LEFT JOIN Shippers s ON s.ShipperID = o.ShipVia
WHERE o.OrderID = 11039;
