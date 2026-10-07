SELECT
    g.GenreId,
    g.Name AS Genre,
    COUNT(DISTINCT i.InvoiceId) AS InvoiceCount,
    SUM(CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity) AS TotalCents
FROM Invoice i
JOIN InvoiceLine il
    ON il.InvoiceId = i.InvoiceId
JOIN Track t
    ON t.TrackId = il.TrackId
JOIN Genre g
    ON g.GenreId = t.GenreId
WHERE i.CustomerId = 5
GROUP BY g.GenreId,g.Name
ORDER BY TotalCents DESC,g.GenreId
LIMIT 10
