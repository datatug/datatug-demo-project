SELECT r.order_id,r.request_id,a.attempt_id,a.config_revision,x.assignment_id,x.partner_id,x.accepted_at,x.deduplication_key
FROM requests r
JOIN latest_attempts a ON a.request_id=r.request_id
JOIN assignments x ON x.attempt_id=a.attempt_id
JOIN workspace_state w ON w.current_config=a.config_revision
JOIN current_routes c ON c.request_id=r.request_id AND c.partner_id=x.partner_id
JOIN partners p ON p.partner_id=c.partner_id AND p.enabled=1
WHERE r.order_id=@order_id AND a.state='accepted'
AND (SELECT COUNT(*) FROM current_routes other WHERE other.request_id=r.request_id AND other.route_id IS NOT NULL)=1
