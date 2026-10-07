SELECT
    e.BusinessEntityID,
    p.FirstName,
    p.LastName,
    e.JobTitle,
    d.DepartmentID,
    d.Name AS Department,
    h.StartDate
FROM "HumanResources.EmployeeDepartmentHistory" h
JOIN "HumanResources.Employee" e
    ON e.BusinessEntityID = h.BusinessEntityID
JOIN "Person.Person" p
    ON p.BusinessEntityID = e.BusinessEntityID
JOIN "HumanResources.Department" d
    ON d.DepartmentID = h.DepartmentID
WHERE h.EndDate IS NULL
ORDER BY d.Name,p.LastName,p.FirstName,e.BusinessEntityID
LIMIT 10
