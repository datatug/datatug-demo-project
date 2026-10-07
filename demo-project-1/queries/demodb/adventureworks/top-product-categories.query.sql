SELECT
    pc.ProductCategoryID,
    pc.Name AS Category,
    p.ProductID,
    p.Name AS Product,
    SUM(d.OrderQty) AS UnitsSold,
    SUM(CAST(ROUND(CAST(d.LineTotal AS REAL) * 1000000) AS INTEGER)) AS LineTotalMicros
FROM "Sales.SalesOrderDetail" d
JOIN "Production.Product" p
    ON p.ProductID = d.ProductID
JOIN "Production.ProductSubcategory" ps
    ON ps.ProductSubcategoryID = p.ProductSubcategoryID
JOIN "Production.ProductCategory" pc
    ON pc.ProductCategoryID = ps.ProductCategoryID
GROUP BY pc.ProductCategoryID,pc.Name,p.ProductID,p.Name
ORDER BY LineTotalMicros DESC,p.ProductID
LIMIT 10
