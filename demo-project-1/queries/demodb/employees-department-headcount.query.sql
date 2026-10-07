SELECT
    d.dept_no,
    d.dept_name,
    COUNT(DISTINCT de.emp_no) AS CurrentEmployees
FROM departments d
LEFT JOIN dept_emp de
    ON de.dept_no = d.dept_no
    AND de.to_date = '9999-01-01'
GROUP BY d.dept_no,d.dept_name
ORDER BY CurrentEmployees DESC,d.dept_no
LIMIT 10
