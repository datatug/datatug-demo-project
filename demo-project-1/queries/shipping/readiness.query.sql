WITH evidence AS (
SELECT r.order_id,r.request_id,w.current_config,w.business_clock,w.generation,
a.attempt_id,a.config_revision AS attempt_config,a.started_at AS attempt_started_at,
(SELECT COUNT(*) FROM current_routes c WHERE c.request_id=r.request_id AND c.route_id IS NOT NULL) AS route_count,
(SELECT COUNT(*) FROM routes c WHERE c.shipper_id=r.shipper_id AND c.revision=w.current_config) AS configured_count,
(SELECT COUNT(*) FROM routes c JOIN partners p ON p.partner_id=c.partner_id WHERE c.shipper_id=r.shipper_id AND c.revision=w.current_config AND p.enabled=1) AS enabled_count,
(SELECT COUNT(*) FROM latest_attempts a JOIN assignments x ON x.attempt_id=a.attempt_id JOIN current_routes c ON c.request_id=a.request_id AND c.partner_id=x.partner_id JOIN partners p ON p.partner_id=c.partner_id AND p.enabled=1 WHERE a.request_id=r.request_id AND a.config_revision=w.current_config AND a.state='accepted') AS accepted_count,
(SELECT COUNT(*) FROM routes c WHERE c.shipper_id=r.shipper_id AND c.revision=a.config_revision AND c.valid_from<=a.started_at AND (c.valid_until IS NULL OR a.started_at<c.valid_until)) AS attempt_route_count,
(SELECT COUNT(*) FROM assignments x JOIN routes c ON c.partner_id=x.partner_id AND c.shipper_id=r.shipper_id AND c.revision=a.config_revision AND c.valid_from<=a.started_at AND (c.valid_until IS NULL OR a.started_at<c.valid_until) WHERE x.attempt_id=a.attempt_id AND a.state='accepted') AS attempt_accepted_count
FROM requests r CROSS JOIN workspace_state w LEFT JOIN latest_attempts a ON a.request_id=r.request_id WHERE r.order_id=@order_id
), cells AS (
SELECT *, 1 AS ordinal, 'Route at attempt' AS expectation, 'attempt' AS basis, CASE WHEN attempt_id IS NULL THEN 'unknown' WHEN attempt_route_count=1 THEN 'pass' ELSE 'fail' END AS status, CASE WHEN attempt_id IS NULL THEN 'No attempt recorded' WHEN attempt_route_count=0 THEN 'No route was effective for the attempt''s configuration at its start' WHEN attempt_route_count>1 THEN 'Ambiguous routes for the attempt''s configuration at its start' ELSE 'One route was effective for the attempt''s configuration at its start' END AS explanation FROM evidence
UNION ALL
SELECT *, 2, 'Assignment at attempt', 'attempt', CASE WHEN attempt_id IS NULL THEN 'unknown' WHEN attempt_route_count=1 AND attempt_accepted_count=1 THEN 'pass' ELSE 'fail' END, CASE WHEN attempt_id IS NULL THEN 'No attempt recorded' WHEN attempt_route_count=1 AND attempt_accepted_count=1 THEN 'The attempt was accepted with an assignment on its effective route' ELSE 'The attempt has no accepted assignment on a route effective at its start' END FROM evidence
UNION ALL
SELECT *, 3, 'Effective route', 'current', CASE WHEN route_count=1 THEN 'pass' ELSE 'fail' END, CASE WHEN route_count=0 THEN 'No effective route' WHEN route_count>1 THEN 'Ambiguous effective routes' ELSE 'One effective route' END FROM evidence
UNION ALL
SELECT *, 4, 'Partner enabled', 'current', CASE WHEN configured_count=0 THEN 'unknown' WHEN configured_count=1 AND enabled_count=1 THEN 'pass' ELSE 'fail' END, CASE WHEN configured_count=0 THEN 'No configured partner' WHEN configured_count>1 THEN 'Ambiguous configured partners' WHEN enabled_count=0 THEN 'Partner disabled' ELSE 'Configured partner enabled' END FROM evidence
UNION ALL
SELECT *, 5, 'Accepted assignment', 'current', CASE WHEN route_count=1 AND accepted_count=1 THEN 'pass' ELSE 'fail' END, CASE WHEN route_count=1 AND accepted_count=1 THEN 'Latest assignment matches current route' ELSE 'No accepted latest assignment for current route; replay may be required' END FROM evidence
)
SELECT order_id,request_id,expectation,status,explanation,current_config,business_clock,basis,attempt_id,CASE WHEN basis='attempt' THEN attempt_config ELSE current_config END AS evaluated_config,CASE WHEN basis='attempt' THEN attempt_started_at ELSE business_clock END AS evaluated_at,request_id || ':' || expectation AS row_key,NULL AS evidence_ref,generation AS source_generation,'requests' AS source_collection,request_id AS source_record_key FROM cells ORDER BY order_id,request_id,ordinal
