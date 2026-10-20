WITH evidence AS (
SELECT r.order_id,r.request_id,w.current_config,w.business_clock,w.generation,
(SELECT COUNT(*) FROM current_routes c WHERE c.request_id=r.request_id AND c.route_id IS NOT NULL) AS route_count,
(SELECT COUNT(*) FROM routes c WHERE c.shipper_id=r.shipper_id AND c.revision=w.current_config) AS configured_count,
(SELECT COUNT(*) FROM routes c JOIN partners p ON p.partner_id=c.partner_id WHERE c.shipper_id=r.shipper_id AND c.revision=w.current_config AND p.enabled=1) AS enabled_count,
(SELECT COUNT(*) FROM latest_attempts a JOIN assignments x ON x.attempt_id=a.attempt_id JOIN current_routes c ON c.request_id=a.request_id AND c.partner_id=x.partner_id JOIN partners p ON p.partner_id=c.partner_id AND p.enabled=1 WHERE a.request_id=r.request_id AND a.config_revision=w.current_config AND a.state='accepted') AS accepted_count
FROM requests r CROSS JOIN workspace_state w WHERE r.order_id=@order_id
), cells AS (
SELECT *, 'Effective route' AS expectation, CASE WHEN route_count=1 THEN 'pass' ELSE 'fail' END AS status, CASE WHEN route_count=0 THEN 'No effective route' WHEN route_count>1 THEN 'Ambiguous effective routes' ELSE 'One effective route' END AS explanation FROM evidence
UNION ALL
SELECT *, 'Partner enabled',CASE WHEN configured_count=0 THEN 'unknown' WHEN configured_count=1 AND enabled_count=1 THEN 'pass' ELSE 'fail' END,CASE WHEN configured_count=0 THEN 'No configured partner' WHEN configured_count>1 THEN 'Ambiguous configured partners' WHEN enabled_count=0 THEN 'Partner disabled' ELSE 'Configured partner enabled' END FROM evidence
UNION ALL
SELECT *, 'Accepted assignment',CASE WHEN route_count=1 AND accepted_count=1 THEN 'pass' ELSE 'fail' END,CASE WHEN route_count=1 AND accepted_count=1 THEN 'Latest assignment matches current route' ELSE 'No accepted latest assignment for current route; replay may be required' END FROM evidence
)
SELECT order_id,request_id,expectation,status,explanation,current_config,business_clock,request_id || ':' || expectation AS row_key,NULL AS evidence_ref,generation AS source_generation,'requests' AS source_collection,request_id AS source_record_key FROM cells ORDER BY request_id,expectation
