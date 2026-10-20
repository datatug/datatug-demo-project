#!/usr/bin/env python3
"""Deterministic synthetic application fixture. Logs are independent direct files."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'demo-project-1/fixtures/shipping'
SCHEMA = '''
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
'''

def digest(b): return hashlib.sha256(b).hexdigest()
def write_json(path,obj): path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')

def log_artifact(path, entries):
    data=b''; refs={}
    for entry in entries:
        raw=(json.dumps(entry,sort_keys=True,separators=(',',':'))+'\n').encode()
        refs[entry['event_id']]={'artifact':path.name,'byte_start':len(data),'byte_end':len(data)+len(raw),'entry_sha256':digest(raw),'parse_state':'parsed'}
        data+=raw
    path.write_bytes(data)
    for ref in refs.values(): ref['artifact_sha256']=digest(data)
    return {'path':'logs/'+path.name,'sha256':digest(data),'bytes':len(data),'entries':refs}

def event_entries(order, attempt, start, kinds):
    return [dict(event_id=f'{attempt}-e{i}',attempt_id=attempt,order_id=order,sequence=i,kind=kind,occurred_at=f'{start}{i-1:02d}Z',clock_domain='synthetic-shipping-utc',precision_ms=1000,synthetic=True) for i,kind in enumerate(kinds,1)]

def insert_events(db, entries, artifact):
    for e in entries:
        ref=artifact['entries'][e['event_id']]
        db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?)',(e['event_id'],e['attempt_id'],e['sequence'],e['kind'],e['occurred_at'],e['clock_domain'],e['precision_ms'],ref['artifact'],ref['byte_start'],ref['byte_end'],ref['artifact_sha256']))

def correct(db):
    """Acceptance helper only. Hosted writes require backend admission, not this script."""
    db.execute("INSERT OR IGNORE INTO configurations VALUES(18,'2018-05-20T10:05:00Z')")
    db.execute("INSERT OR IGNORE INTO routes VALUES('route-18-2',18,2,'united-package','2018-05-20T10:05:00Z',NULL)")
    # Retain negative controls in the new revision.
    for row in db.execute('SELECT route_id,shipper_id,partner_id,valid_from,valid_until FROM routes WHERE revision=17 AND shipper_id<>2').fetchall():
        db.execute('INSERT OR IGNORE INTO routes VALUES(?,18,?,?,?,?)',(row[0]+'-18',*row[1:]))
    db.execute("UPDATE workspace_state SET current_config=18,business_clock='2018-05-20T10:05:00Z'")

def replay(db, order_id, recovery):
    request=db.execute('SELECT request_id FROM requests WHERE order_id=?',(order_id,)).fetchone()
    if request is None: raise ValueError('request not found')
    key=request[0]+':assignment'
    existing=db.execute('SELECT assignment_id FROM assignments WHERE deduplication_key=?',(key,)).fetchone()
    if existing: return existing[0]
    candidates=db.execute('SELECT route_id,partner_id FROM current_routes WHERE order_id=? AND route_id IS NOT NULL',(order_id,)).fetchall()
    if len(candidates)!=1 or db.execute('SELECT enabled FROM partners WHERE partner_id=?',(candidates[0][1],)).fetchone()[0]!=1: raise ValueError('route unavailable')
    if not db.execute('SELECT 1 FROM receipts x JOIN requests r ON r.request_id=x.request_id AND r.message_id=x.message_id WHERE r.order_id=?',(order_id,)).fetchone(): raise ValueError('receiver receipt missing')
    attempt=f'attempt-{order_id}-2'
    db.execute('INSERT INTO attempts VALUES(?,?,2,18,?,?)',(attempt,request[0],'2018-05-20T10:05:00Z','accepted'))
    entries=event_entries(order_id,attempt,'2018-05-20T10:05:', ['replay-started','route-resolved','assignment-accepted'])
    insert_events(db,entries,recovery)
    assignment=f'assignment-{order_id}'
    db.execute('INSERT INTO assignments VALUES(?,?,?,?,?)',(assignment,attempt,candidates[0][1],'2018-05-20T10:05:02Z',key))
    return assignment

def build(output):
    output.mkdir(parents=True,exist_ok=True); (output/'logs').mkdir(exist_ok=True)
    base=[]; recovery=[]
    for order in [11038,11045,11062,90001,90002,90003,90004,90005]:
        kinds=['request-created','publication-acknowledged','receiver-received','routing-blocked']
        if order==11038: kinds=['request-created','publication-acknowledged','receiver-received','route-resolved','assignment-accepted']
        if order in [90004,90005]: kinds=['request-created','publication-acknowledged']
        date='2018-04-30T09:00:' if order==11038 else '2018-05-20T09:00:'
        base+=event_entries(order,f'attempt-{order}-1',date,kinds)
    for order in [11045,11062]: recovery+=event_entries(order,f'attempt-{order}-2','2018-05-20T10:05:',['replay-started','route-resolved','assignment-accepted'])
    base_artifact=log_artifact(output/'logs/base.jsonl',base)
    recovery_artifacts=[log_artifact(output/f'logs/recovery-{order}.jsonl',[e for e in recovery if e['order_id']==order]) for order in [11045,11062]]
    (output/'logs/recovery.jsonl').unlink(missing_ok=True)
    recovery_artifact={'entries':{key:value for artifact in recovery_artifacts for key,value in artifact['entries'].items()}}
    path=output/'base.sqlite'; path.unlink(missing_ok=True)
    db=sqlite3.connect(path); db.executescript(SCHEMA)
    db.execute("INSERT INTO workspace_state VALUES('shipping-base-v1',17,'2018-05-20T10:00:00Z')")
    db.execute("INSERT INTO configurations VALUES(17,'2018-04-01T00:00:00Z')")
    db.executemany('INSERT INTO partners VALUES(?,?)',[('united-package',1),('disabled-partner',0)])
    db.executemany('INSERT INTO routes VALUES(?,?,?,?,?,?)',[
        ('route-17-2',17,2,'united-package','2018-04-01T00:00:00Z','2018-05-19T00:00:00Z'),
        ('ambiguous-a',17,92,'united-package','2018-04-01T00:00:00Z',None),('ambiguous-b',17,92,'united-package','2018-04-01T00:00:00Z',None),('disabled',17,93,'disabled-partner','2018-04-01T00:00:00Z',None)])
    for order in [11038,11045,11062,90001,90002,90003,90004,90005]:
        shipper={90001:91,90002:92,90003:93}.get(order,2)
        request=f'request-{order}'; msg=f'message-{order}'; at='2018-04-30T09:00:00Z' if order==11038 else '2018-05-20T09:00:00Z'
        db.execute('INSERT INTO requests VALUES(?,?,?,?,?,?)',(request,order,shipper,msg,f'correlation-{order}',at))
        db.execute('INSERT INTO publications VALUES(?,?,?,?)',(f'publication-{order}',request,msg,at.replace('00Z','01Z')))
        if order!=90005: db.execute('INSERT INTO receipts VALUES(?,?,?,?)',(f'receipt-{order}',request,'wrong-message' if order==90004 else msg,at.replace('00Z','02Z')))
        db.execute('INSERT INTO attempts VALUES(?,?,1,17,?,?)',(f'attempt-{order}-1',request,at,'accepted' if order==11038 else 'blocked'))
    insert_events(db,base,base_artifact)
    db.execute("INSERT INTO assignments VALUES('assignment-11038','attempt-11038-1','united-package','2018-04-30T09:00:04Z','request-11038:assignment')")
    db.commit(); db.execute('VACUUM'); db.close()
    (output/'schema.sql').write_text(SCHEMA)
    write_json(output/'manifest.json',{'format':'datatug-shipping-fixture/v1','synthetic':True,'publication':'not-published','generatorSha256':digest(Path(__file__).read_bytes()),'rightsSha256':digest((FIXTURE/'rights.json').read_bytes()),'connectionId':'shipping-working-copy','generation':'shipping-base-v1','businessClock':'2018-05-20T10:00:00Z','recoveryClock':'2018-05-20T10:05:00Z','clockDomain':'synthetic-shipping-utc','precisionMs':1000,'database':{'path':'base.sqlite','sha256':digest(path.read_bytes()),'bytes':path.stat().st_size,'schemaSha256':digest(SCHEMA.encode())},'logs':[base_artifact,*recovery_artifacts],'northwind':{'sha256':'279b34136771aee75d802094b3329515a2b01da65d2a20a4a9e3b58c29b4fd20','readOnly':True,'orders':[11038,11045,11062]},'recovery':{'configuration':18,'orders':[11045,11062],'deduplicationKey':'request_id + :assignment','changesGeneration':False},'reset':{'newGenerationRequired':True,'retainOldArtifactAndHistory':True}})
    return base_artifact,recovery_artifact

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,default=FIXTURE); args=parser.parse_args(); build(args.output)
