SELECT ShipCountry, COUNT(*) AS orders
FROM Orders
GROUP BY ShipCountry
ORDER BY ShipCountry
