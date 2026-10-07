SELECT
    e.emp_no,
    e.first_name,
    e.last_name,
    s.salary,
    s.from_date AS salary_since
FROM employees e
JOIN salaries s
    ON s.emp_no = e.emp_no
WHERE s.to_date = '9999-01-01'
ORDER BY s.salary DESC,e.emp_no
LIMIT 10
