SELECT r.order_id,a.attempt_id,a.attempt_no,a.config_revision,e.event_id,e.sequence,e.kind,e.occurred_at,e.clock_domain,e.precision_ms,
CAST((julianday(e.occurred_at)-julianday(a.started_at))*86400000+0.5 AS INTEGER) AS elapsed_ms,
e.artifact,e.artifact_sha256,e.byte_start,e.byte_end,
CASE WHEN e.kind='routing-blocked' THEN 'fail' ELSE 'pass' END AS status,
e.event_id AS row_key,NULL AS evidence_ref,w.generation AS source_generation,'events' AS source_collection,e.event_id AS source_record_key
FROM requests r JOIN attempts a ON a.request_id=r.request_id JOIN events e ON e.attempt_id=a.attempt_id CROSS JOIN workspace_state w
WHERE r.order_id=@order_id ORDER BY a.attempt_no,e.sequence
