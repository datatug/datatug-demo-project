
PRAGMA foreign_keys=ON;
CREATE TABLE workspace_state(generation TEXT PRIMARY KEY,current_config INTEGER NOT NULL,business_clock TEXT NOT NULL);
CREATE TABLE requests(request_id TEXT PRIMARY KEY,order_id INTEGER UNIQUE NOT NULL,shipper_id INTEGER NOT NULL,message_id TEXT UNIQUE NOT NULL,correlation_id TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE publications(publication_id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES requests,message_id TEXT NOT NULL,acknowledged_at TEXT NOT NULL);
CREATE TABLE receipts(receipt_id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES requests,message_id TEXT NOT NULL,received_at TEXT NOT NULL);
CREATE TABLE configurations(revision INTEGER PRIMARY KEY,published_at TEXT NOT NULL);
CREATE TABLE partners(partner_id TEXT PRIMARY KEY,enabled INTEGER NOT NULL CHECK(enabled IN(0,1)));
CREATE TABLE routes(route_id TEXT PRIMARY KEY,revision INTEGER NOT NULL REFERENCES configurations,shipper_id INTEGER NOT NULL,partner_id TEXT NOT NULL REFERENCES partners,valid_from TEXT NOT NULL,valid_until TEXT);
CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES requests,attempt_no INTEGER NOT NULL,config_revision INTEGER NOT NULL REFERENCES configurations,started_at TEXT NOT NULL,state TEXT NOT NULL,UNIQUE(request_id,attempt_no));
CREATE TABLE events(event_id TEXT PRIMARY KEY,attempt_id TEXT NOT NULL REFERENCES attempts,sequence INTEGER NOT NULL,kind TEXT NOT NULL,occurred_at TEXT NOT NULL,clock_domain TEXT NOT NULL,precision_ms INTEGER NOT NULL,artifact TEXT NOT NULL,byte_start INTEGER NOT NULL,byte_end INTEGER NOT NULL,artifact_sha256 TEXT NOT NULL,UNIQUE(attempt_id,sequence));
CREATE TABLE assignments(assignment_id TEXT PRIMARY KEY,attempt_id TEXT NOT NULL REFERENCES attempts,partner_id TEXT NOT NULL REFERENCES partners,accepted_at TEXT NOT NULL,deduplication_key TEXT UNIQUE NOT NULL);
CREATE VIEW latest_attempts AS SELECT a.* FROM attempts a WHERE NOT EXISTS(SELECT 1 FROM attempts newer WHERE newer.request_id=a.request_id AND newer.attempt_no>a.attempt_no);
CREATE VIEW current_routes AS SELECT r.request_id,r.order_id,p.route_id,p.partner_id,p.valid_from,p.valid_until,w.current_config,w.business_clock FROM requests r CROSS JOIN workspace_state w LEFT JOIN routes p ON p.shipper_id=r.shipper_id AND p.revision=w.current_config AND p.valid_from<=w.business_clock AND (p.valid_until IS NULL OR w.business_clock<p.valid_until);
