SELECT
    r.RegionID,
    r.RegionDescription,
    t.TerritoryID,
    t.TerritoryDescription,
    COUNT(DISTINCT et.EmployeeID) AS EmployeeCount
FROM Regions r
JOIN Territories t
    ON t.RegionID = r.RegionID
LEFT JOIN EmployeeTerritories et
    ON et.TerritoryID = t.TerritoryID
GROUP BY r.RegionID,r.RegionDescription,t.TerritoryID,t.TerritoryDescription
ORDER BY r.RegionID,t.TerritoryID
LIMIT 10
