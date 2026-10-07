SELECT
    a.actor_id,
    a.first_name || ' ' || a.last_name AS Actor,
    COUNT(DISTINCT fa.film_id) AS FilmCount,
    MIN(f.release_year) AS FirstReleaseYear,
    MAX(f.release_year) AS LastReleaseYear
FROM actor a
JOIN film_actor fa
    ON fa.actor_id = a.actor_id
JOIN film f
    ON f.film_id = fa.film_id
GROUP BY a.actor_id,a.first_name,a.last_name
ORDER BY FilmCount DESC,a.actor_id
LIMIT 10
