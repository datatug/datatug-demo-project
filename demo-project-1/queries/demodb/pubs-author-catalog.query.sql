SELECT
    a.au_id,
    a.au_fname || ' ' || a.au_lname AS Author,
    COUNT(DISTINCT ta.title_id) AS TitleCount,
    SUM(CAST(ROUND(COALESCE(t.price,0) * 100) AS INTEGER)) AS LinkedListPriceCents
FROM authors a
JOIN titleauthor ta
    ON ta.au_id = a.au_id
JOIN titles t
    ON t.title_id = ta.title_id
GROUP BY a.au_id,a.au_fname,a.au_lname
ORDER BY TitleCount DESC,LinkedListPriceCents DESC,a.au_id
LIMIT 10
