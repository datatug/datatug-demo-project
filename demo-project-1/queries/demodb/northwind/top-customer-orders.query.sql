SELECT
    c.CustomerID,
    c.CompanyName,
    COUNT(DISTINCT o.OrderID) AS OrderCount,
    SUM(CAST(ROUND(od.UnitPrice * od.Quantity * (1.0-od.Discount) * 100) AS INTEGER)) AS SalesCents
FROM Customers c
JOIN Orders o
    ON o.CustomerID = c.CustomerID
JOIN "Order Details" od
    ON od.OrderID = o.OrderID
GROUP BY c.CustomerID,c.CompanyName
ORDER BY SalesCents DESC,c.CustomerID
LIMIT 10
