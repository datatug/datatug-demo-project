SELECT
    st.stor_id,
    st.stor_name,
    t.title_id,
    t.title,
    COUNT(DISTINCT s.ord_num) AS OrderCount,
    SUM(s.qty) AS UnitsSold
FROM stores st
JOIN sales s
    ON s.stor_id = st.stor_id
JOIN titles t
    ON t.title_id = s.title_id
GROUP BY st.stor_id,st.stor_name,t.title_id,t.title
ORDER BY UnitsSold DESC,st.stor_id,t.title_id
LIMIT 10
