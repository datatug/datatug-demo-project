SELECT
    p.ProductID,
    p.ProductName,
    c.CategoryName,
    s.CompanyName AS Supplier,
    p.UnitsInStock,
    p.ReorderLevel,
    CAST(ROUND(p.UnitPrice * 100) AS INTEGER) AS UnitPriceCents
FROM Products p
LEFT JOIN Categories c
    ON c.CategoryID = p.CategoryID
LEFT JOIN Suppliers s
    ON s.SupplierID = p.SupplierID
WHERE p.UnitsInStock <= p.ReorderLevel
    AND CAST(p.Discontinued AS INTEGER) = 0
ORDER BY p.UnitsInStock-p.ReorderLevel,p.ProductID
LIMIT 10
