SELECT email
FROM customers
GROUP BY email
HAVING COUNT(*) > 1
