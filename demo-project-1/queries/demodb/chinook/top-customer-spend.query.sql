SELECT
    c.CustomerId,
    c.FirstName || ' ' || c.LastName AS CustomerName,
    c.Country,
    COUNT(i.InvoiceId) AS InvoiceCount,
    SUM(CAST(ROUND(i.Total * 100) AS INTEGER)) AS TotalCents
FROM Customer c
JOIN Invoice i
    ON i.CustomerId = c.CustomerId
GROUP BY c.CustomerId,c.FirstName,c.LastName,c.Country
ORDER BY TotalCents DESC,c.CustomerId
LIMIT 10
