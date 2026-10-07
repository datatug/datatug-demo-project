SELECT
    dm.dept_no,
    d.dept_name,
    e.emp_no,
    e.first_name,
    e.last_name,
    dm.from_date AS manager_since
FROM dept_manager dm
JOIN departments d
    ON d.dept_no = dm.dept_no
JOIN employees e
    ON e.emp_no = dm.emp_no
WHERE dm.to_date = '9999-01-01'
ORDER BY dm.dept_no,e.emp_no
LIMIT 10
