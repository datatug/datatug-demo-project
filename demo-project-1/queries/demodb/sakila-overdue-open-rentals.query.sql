SELECT
    r.rental_id,
    c.customer_id,
    c.first_name || ' ' || c.last_name AS Customer,
    f.title AS Film,
    r.rental_date,
    date(r.rental_date,'+' || f.rental_duration || ' days') AS DueDate
FROM rental r
JOIN customer c
    ON c.customer_id = r.customer_id
JOIN inventory i
    ON i.inventory_id = r.inventory_id
JOIN film f
    ON f.film_id = i.film_id
WHERE r.return_date IS NULL
    AND date(r.rental_date,'+' || f.rental_duration || ' days') < '2005-08-31'
ORDER BY DueDate,r.rental_id
LIMIT 10
