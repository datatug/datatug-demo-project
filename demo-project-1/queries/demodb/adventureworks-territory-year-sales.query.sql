SELECT
    st.TerritoryID,
    st.Name AS Territory,
    strftime('%Y',h.OrderDate) AS SalesYear,
    COUNT(DISTINCT h.SalesOrderID) AS OrderCount,
    SUM(CAST(REPLACE(d.LineTotal, '.', '') AS INTEGER)) AS LineTotalMicros
FROM "Sales.SalesOrderHeader" h
JOIN "Sales.SalesOrderDetail" d
    ON d.SalesOrderID = h.SalesOrderID
JOIN "Sales.SalesTerritory" st
    ON st.TerritoryID = h.TerritoryID
GROUP BY st.TerritoryID,st.Name,strftime('%Y',h.OrderDate)
ORDER BY SalesYear DESC,LineTotalMicros DESC,st.TerritoryID
LIMIT 10
