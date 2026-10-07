SELECT
    c.category_id,
    c.name AS Category,
    COUNT(DISTINCT r.rental_id) AS Rentals,
    SUM(CAST(ROUND(p.amount * 100) AS INTEGER)) AS RevenueCents
FROM category c
JOIN film_category fc
    ON fc.category_id = c.category_id
JOIN film f
    ON f.film_id = fc.film_id
JOIN inventory i
    ON i.film_id = f.film_id
JOIN rental r
    ON r.inventory_id = i.inventory_id
JOIN payment p
    ON p.rental_id = r.rental_id
GROUP BY c.category_id,c.name
ORDER BY RevenueCents DESC,c.category_id
LIMIT 10
