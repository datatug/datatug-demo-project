SELECT
    rs.title_id,
    t.title,
    rs.lorange,
    rs.hirange,
    rs.royalty
FROM roysched rs
LEFT JOIN titles t
    ON t.title_id = rs.title_id
ORDER BY rs.title_id,rs.lorange,rs.hirange,rs.royalty
LIMIT 10
