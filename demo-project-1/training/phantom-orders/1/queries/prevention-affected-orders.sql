SELECT order_id
FROM payments
WHERE status='succeeded'
GROUP BY order_id
HAVING COUNT(*)>1;
