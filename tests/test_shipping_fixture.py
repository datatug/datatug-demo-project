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
  for relative in ['base.sqlite','schema.sql','manifest.json','logs/base.jsonl','logs/recovery-11045.jsonl','logs/recovery-11062.jsonl']:
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
  self.assertEqual(1,len(self.query('assignment-outcome',11038)))
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
  for artifact in json.loads((self.path/'manifest.json').read_text())['logs']:
   data=(self.path/artifact['path']).read_bytes(); self.assertEqual(artifact['sha256'],shipping.digest(data))
   for event_id,ref in artifact['entries'].items():
    entry=data[ref['byte_start']:ref['byte_end']]
    self.assertEqual(ref['entry_sha256'],shipping.digest(entry)); self.assertEqual(event_id,json.loads(entry)['event_id'])
  rows=self.query('events',11045); self.assertEqual([0,1000,2000,3000],[r[10] for r in rows])
  self.assertEqual([1000]*3,[r[9] for r in self.query('timings',11045)])
  self.assertFalse(any('partner-call' in str(r) for r in rows))
  self.assertFalse(self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%log%'").fetchall())
 def test_northwind_pin_when_available(self):
  source=Path('/Users/alex/projects/demo-db/northwind/data-source/source.sqlite')
  if not source.exists(): self.skipTest('external Northwind source not in this checkout')
  manifest=json.loads((self.path/'manifest.json').read_text())
  self.assertEqual(manifest['northwind']['sha256'],shipping.digest(source.read_bytes()))
  with sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True) as db:
   self.assertEqual([(11038,'SUPRD','2018-04-21','2018-05-19',2,'2018-04-30'),(11045,'BOTTM','2018-04-23','2018-05-21',2,None),(11062,'REGGC','2018-04-30','2018-05-28',2,None)],db.execute('SELECT OrderID,CustomerID,OrderDate,RequiredDate,ShipVia,ShippedDate FROM Orders WHERE OrderID IN(11038,11045,11062) ORDER BY OrderID').fetchall())
if __name__=='__main__': unittest.main()
