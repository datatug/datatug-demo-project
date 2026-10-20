SELECT r.order_id,r.request_id,p.partner_id,p.enabled
FROM requests r CROSS JOIN workspace_state w
JOIN routes x ON x.shipper_id=r.shipper_id AND x.revision=w.current_config
JOIN partners p ON p.partner_id=x.partner_id
WHERE r.order_id=@order_id AND p.enabled=1
AND (SELECT COUNT(*) FROM routes c WHERE c.shipper_id=r.shipper_id AND c.revision=w.current_config)=1
