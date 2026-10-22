"""Real SQLite evidence assertions; never imports logs into a database."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('shipping',ROOT/'scripts/build-shipping-fixture.py')
shipping=importlib.util.module_from_spec(spec); spec.loader.exec_module(shipping)

class ShippingFixtureTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name); self.base,self.recovery=shipping.build(self.path)
  self.db=sqlite3.connect(self.path/'base.sqlite'); self.addCleanup(self.db.close)
 def query(self,name,order):
  return self.db.execute((ROOT/f'demo-project-1/queries/shipping/{name}.query.sql').read_text(),{'order_id':order}).fetchall()
 def test_deterministic_rebuild_and_pinned_committed_artifacts(self):
  other=self.path/'again'; shipping.build(other)
  for relative in ['base.sqlite','schema.sql','manifest.json','logs/base.jsonl','logs/recovery-11045.jsonl','logs/recovery-11062.jsonl','logs/carrier-gateway.jsonl','logs/carrier-gateway-recovery-11045.jsonl','logs/carrier-gateway-recovery-11062.jsonl']:
   self.assertEqual((self.path/relative).read_bytes(),(other/relative).read_bytes(),relative)
   self.assertEqual((self.path/relative).read_bytes(),(shipping.FIXTURE/relative).read_bytes(),relative)
 def test_baseline_controls_and_readonly_queries(self):
  for order in [11038,11045,11062,90001,90002,90003]: self.assertEqual(1,len(self.query('request-receipt',order)))
  for order in [90004,90005,99999]: self.assertEqual([],self.query('request-receipt',order))
  self.assertEqual('expired',self.query('historical-route',11045)[0][-1])
  self.assertEqual('effective',self.query('historical-route',11038)[0][-1])
  self.assertEqual('missing',self.query('historical-route',90001)[0][-1])
  self.assertEqual({'ambiguous'},set(row[-1] for row in self.query('historical-route',90002)))
  self.assertEqual('disabled',self.query('historical-route',90003)[0][-1])
  self.assertEqual([],self.query('assignment-outcome',11045))
  self.assertEqual([],self.query('assignment-outcome',11038)) # historical control's route has since expired
  self.assertEqual(1,self.db.execute("SELECT COUNT(*) FROM assignments WHERE assignment_id='assignment-11038'").fetchone()[0])
  self.assertEqual([],self.query('current-route',90002))
  self.assertEqual([],self.query('partner-enabled',90003))
 def test_correction_replay_history_idempotency_and_reuse(self):
  generation=self.db.execute('SELECT generation FROM workspace_state').fetchone()
  old_events=self.db.execute('SELECT * FROM events').fetchall()
  shipping.correct(self.db); shipping.correct(self.db)
  self.assertEqual(1,len(self.query('current-route',11045)))
  self.assertEqual([],self.query('assignment-outcome',11045))
  self.assertEqual([],self.query('assignment-outcome',11062))
  first=shipping.replay(self.db,11045,self.recovery)
  self.assertEqual(first,shipping.replay(self.db,11045,self.recovery))
  self.assertEqual(1,len(self.query('assignment-outcome',11045)))
  self.assertEqual([],self.query('assignment-outcome',11062))
  self.assertEqual(generation,self.db.execute('SELECT generation FROM workspace_state').fetchone())
  self.assertEqual(2,self.db.execute("SELECT COUNT(*) FROM attempts WHERE request_id='request-11045'").fetchone()[0])
  self.assertEqual(1,self.db.execute("SELECT COUNT(*) FROM assignments WHERE deduplication_key='request-11045:assignment'").fetchone()[0])
  for event in old_events: self.assertEqual(event,self.db.execute('SELECT * FROM events WHERE event_id=?',(event[0],)).fetchone())
  for order in [90001,90002,90003,90004,90005]:
   with self.assertRaises(ValueError): shipping.replay(self.db,order,self.recovery)
  shipping.replay(self.db,11062,self.recovery)
  self.assertEqual(1,len(self.query('assignment-outcome',11062)))
 def test_log_provenance_and_real_timing(self):
  manifest=json.loads((self.path/'manifest.json').read_text())
  for artifact in manifest['logs']+manifest['carrierGatewayLogs']:
   data=(self.path/artifact['path']).read_bytes(); self.assertEqual(artifact['sha256'],shipping.digest(data))
   for event_id,ref in artifact['entries'].items():
    entry=data[ref['byte_start']:ref['byte_end']]
    self.assertEqual(ref['entry_sha256'],shipping.digest(entry)); self.assertEqual(event_id,json.loads(entry)['event_id'])
  rows=self.query('events',11045); self.assertEqual([0,1000,2000,3000],[r[10] for r in rows])
  self.assertEqual([1000]*3,[r[9] for r in self.query('timings',11045)])
  self.assertFalse(any('partner-call' in str(r) for r in rows))
  self.assertFalse(self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%log%'").fetchall())
 def test_carrier_gateway_stream_is_additive_synthetic_and_recovery_isolated(self):
  manifest=json.loads((self.path/'manifest.json').read_text())
  # Existing artifacts keep their pinned bytes; the carrier stream is additive.
  self.assertEqual(['logs/base.jsonl','logs/recovery-11045.jsonl','logs/recovery-11062.jsonl'],[a['path'] for a in manifest['logs']])
  self.assertEqual({'logs/base.jsonl':'5814c09c2821dcf5fb7c313d4416fadd71f62519ab8aafe01de0ac6e6a4db65e','logs/recovery-11045.jsonl':'a03031230dfad126783e557b61631f1173dd6c5867f19e2758e971ffea716379','logs/recovery-11062.jsonl':'ab668b7a26e034d80486f6ea1d17f89c9b226f3a98e297bb3b80186cc65936a5'},{a['path']:a['sha256'] for a in manifest['logs']})
  self.assertEqual('73f0d871607ee5b24de68b5398c25806f556a3126a31e1865fee79b2881977e0',manifest['database']['sha256'])
  carrier={a['path']:a for a in manifest['carrierGatewayLogs']}
  self.assertEqual(['logs/carrier-gateway.jsonl','logs/carrier-gateway-recovery-11045.jsonl','logs/carrier-gateway-recovery-11062.jsonl'],list(carrier))
  def lines(path): return [json.loads(line) for line in (self.path/path).read_text().splitlines()]
  baseline=lines('logs/carrier-gateway.jsonl')
  self.assertEqual('baseline',carrier['logs/carrier-gateway.jsonl']['classification'])
  self.assertEqual({11038},{e['order_id'] for e in baseline}, 'blocked requests have no carrier call before replay')
  for order in [11045,11062]:
   artifact=carrier[f'logs/carrier-gateway-recovery-{order}.jsonl']
   self.assertEqual('recovery-example',artifact['classification']); self.assertEqual(f'logs/recovery-{order}.jsonl',artifact['eligibleWith'])
   self.assertEqual({order},{e['order_id'] for e in lines(artifact['path'])})
  all_lines=[e for path in carrier for e in lines(path)]
  for e in all_lines:
   self.assertIs(True,e['synthetic']); self.assertIn('Synthetic',e['note']); self.assertEqual('carrier-gateway',e['stream'])
   request=self.db.execute('SELECT request_id,correlation_id FROM requests WHERE order_id=?',(e['order_id'],)).fetchone()
   self.assertEqual((e['request_id'],e['correlation_id']),request)
   self.assertEqual(e['request_id']+':assignment',e['deduplication_key'])
   self.assertEqual('synthetic-shipping-utc',e['clock_domain']); self.assertEqual(1000,e['precision_ms'])
   self.assertNotIn('pick',json.dumps(e).lower(),'a booking never implies package movement')
  self.assertEqual(['booking-requested','booking-confirmed'],[e['kind'] for e in baseline])
  self.assertEqual('booked',baseline[1]['booking_status'])
  # 11038: call after its route resolved, confirmation at the recorded assignment time.
  events=dict(self.db.execute("SELECT kind,occurred_at FROM events WHERE attempt_id='attempt-11038-1'").fetchall())
  self.assertEqual(events['route-resolved'],baseline[0]['occurred_at'])
  self.assertEqual(self.db.execute("SELECT accepted_at FROM assignments WHERE deduplication_key='request-11038:assignment'").fetchone()[0],baseline[1]['occurred_at'])
  # 11045: the replay's call matches the replayed attempt and its accepted assignment.
  shipping.correct(self.db); shipping.replay(self.db,11045,self.recovery)
  replayed=lines('logs/carrier-gateway-recovery-11045.jsonl')
  self.assertEqual({'attempt-11045-2'},{e['attempt_id'] for e in replayed})
  self.assertEqual(self.db.execute("SELECT occurred_at FROM events WHERE event_id='attempt-11045-2-e2'").fetchone()[0],replayed[0]['occurred_at'])
  self.assertEqual(self.db.execute("SELECT accepted_at FROM assignments WHERE deduplication_key='request-11045:assignment'").fetchone()[0],replayed[1]['occurred_at'])
  self.assertFalse(self.db.execute("SELECT name FROM sqlite_master WHERE name LIKE '%carrier%'").fetchall(),'logs are never imported into SQLite')
 def test_chart_projection_and_current_configuration_consistency(self):
  def records(name,order):
   cursor=self.db.execute((ROOT/f'demo-project-1/queries/shipping/{name}.query.sql').read_text(),{'order_id':order})
   names=[c[0] for c in cursor.description]
   return [dict(zip(names,row)) for row in cursor]
  def heatmap(order):
   rows=records('readiness',order)
   self.assertEqual(5,len(rows)); self.assertEqual(5,len({(r['request_id'],r['expectation']) for r in rows}))
   for row in rows:
    self.assertIn(row['status'],['pass','fail','unknown'])
    self.assertEqual('shipping-base-v1',row['source_generation'])
    self.assertEqual('requests',row['source_collection'])
    self.assertEqual(row['request_id'],row['source_record_key'])
    self.assertEqual(row['request_id']+':'+row['expectation'],row['row_key'])
    self.assertIsNone(row['evidence_ref']) # Only runtime can name its actual execution.
    attempt=self.db.execute('SELECT attempt_id,config_revision,started_at FROM latest_attempts WHERE request_id=?',(row['request_id'],)).fetchone()
    self.assertEqual(attempt[0],row['attempt_id'])
    if row['basis']=='attempt': self.assertEqual(attempt[1:],(row['evaluated_config'],row['evaluated_at']))
    else: self.assertEqual('current',row['basis']); self.assertEqual((row['current_config'],row['business_clock']),(row['evaluated_config'],row['evaluated_at']))
   return {r['expectation']:r['status'] for r in rows}
  admission=json.loads((self.path/'manifest.json').read_text())['chartAdmission']
  self.assertFalse(admission['rawRowsAdmitted']); self.assertTrue(admission['requiresActualScopedExecutionRef']); self.assertTrue(admission['requiresExactHeldRowKey'])
  for chart,query_name in [('timeline','events'),('heatmap','readiness')]:
   mapping=admission['queryMappings'][chart]
   self.assertEqual(len(mapping),len(set(mapping.values())))
   for row in records(query_name,11045):
    for column in mapping.values(): self.assertIn(column,row)
    self.assertTrue(row['row_key'])
  self.assertEqual({'Route at attempt':'fail','Assignment at attempt':'fail','Effective route':'fail','Partner enabled':'pass','Accepted assignment':'fail'},heatmap(11045))
  # The healthy historical control passes for its own attempt; its current-configuration cells stay honest.
  self.assertEqual({'Route at attempt':'pass','Assignment at attempt':'pass','Effective route':'fail','Partner enabled':'pass','Accepted assignment':'fail'},heatmap(11038))
  comparison=self.db.execute((ROOT/'demo-project-1/queries/shipping/readiness-comparison.query.sql').read_text(),{'order_id':11045,'comparison_order_id':11038})
  names=[c[0] for c in comparison.description]; comparison=[dict(zip(names,row)) for row in comparison]
  self.assertEqual(records('readiness',11038)+records('readiness',11045),comparison)
  single=(ROOT/'demo-project-1/queries/shipping/readiness.query.sql').read_text()
  self.assertEqual(single.replace('WHERE r.order_id=@order_id','WHERE r.order_id IN (@order_id,@comparison_order_id)'),(ROOT/'demo-project-1/queries/shipping/readiness-comparison.query.sql').read_text())
  for row in records('events',11045):
   self.assertIn(row['status'],['pass','fail','unknown'])
   self.assertEqual('events',row['source_collection']); self.assertEqual(row['event_id'],row['source_record_key']); self.assertEqual(row['event_id'],row['row_key'])
   self.assertIsNone(row['evidence_ref'])
  for row in records('timings',11045):
   for end in ['start','end']:
    self.assertTrue(row[end+'_event_id'])
    data=(self.path/'logs'/row[end+'_artifact']).read_bytes()
    self.assertEqual(row[end+'_artifact_sha256'],shipping.digest(data))
    entry=json.loads(data[row[end+'_byte_start']:row[end+'_byte_end']])
    self.assertEqual(row[end+'_event_id'],entry['event_id'])
  shipping.correct(self.db)
  self.assertEqual('pass',heatmap(11045)['Effective route'])
  self.assertEqual('fail',heatmap(11045)['Accepted assignment'])
  self.assertEqual('fail',heatmap(11045)['Route at attempt'],'correction does not rewrite the failed attempt')
  # 11062 after correction: corrected route, awaiting replay.
  self.assertEqual({'Route at attempt':'fail','Assignment at attempt':'fail','Effective route':'pass','Partner enabled':'pass','Accepted assignment':'fail'},heatmap(11062))
  shipping.replay(self.db,11045,self.recovery)
  self.assertEqual({'Route at attempt':'pass','Assignment at attempt':'pass','Effective route':'pass','Partner enabled':'pass','Accepted assignment':'pass'},heatmap(11045))
  self.db.executescript("INSERT INTO configurations VALUES(19,'2018-05-20T10:06:00Z'); INSERT INTO partners VALUES('new-partner',1); INSERT INTO routes VALUES('route-19-2',19,2,'new-partner','2018-05-20T10:06:00Z',NULL); UPDATE workspace_state SET current_config=19,business_clock='2018-05-20T10:06:00Z';")
  self.assertEqual([],self.query('assignment-outcome',11045))
  self.assertEqual('fail',heatmap(11045)['Accepted assignment'])
  self.assertEqual('pass',heatmap(11045)['Assignment at attempt'],'a later configuration does not rewrite the replayed attempt')
  self.assertEqual('expired',self.query('historical-route',11045)[0][-1])
 def test_northwind_pin_when_available(self):
  source=Path('/Users/alex/projects/demo-db/northwind/data-source/source.sqlite')
  if not source.exists(): self.skipTest('external Northwind source not in this checkout')
  manifest=json.loads((self.path/'manifest.json').read_text())
  self.assertEqual(manifest['northwind']['sha256'],shipping.digest(source.read_bytes()))
  with sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True) as db:
   self.assertEqual([(11038,'SUPRD','2018-04-21','2018-05-19',2,'2018-04-30'),(11045,'BOTTM','2018-04-23','2018-05-21',2,None),(11062,'REGGC','2018-04-30','2018-05-28',2,None)],db.execute('SELECT OrderID,CustomerID,OrderDate,RequiredDate,ShipVia,ShippedDate FROM Orders WHERE OrderID IN(11038,11045,11062) ORDER BY OrderID').fetchall())
if __name__=='__main__': unittest.main()
