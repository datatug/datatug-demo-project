import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("watch_demo", ROOT / "scripts/watch-shipping-demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class WatchShippingDemoTest(unittest.TestCase):
    def test_existing_fixture_is_extended_only_in_a_private_copy(self):
        original = ROOT / "demo-project-1/fixtures/shipping/base.sqlite"
        fingerprint = hashlib.sha256(original.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            copy = demo.prepare(Path(temporary) / "project", "http://127.0.0.1:8988", "northwind", local_owner_fixture=True)
            self.assertTrue((copy / ".watch-demo/archived-policies/customers.yaml").is_file())
            self.assertEqual((ROOT / "demo-project-1/policies/customers.yaml").read_bytes(), (copy / ".watch-demo/archived-policies/customers.yaml").read_bytes())
            self.assertEqual([], list((copy / "policies").iterdir()))
            self.assertTrue(json.loads((copy / ".watch-demo/owner.json").read_text())["localOwnerFixture"])
            manifest = json.loads((copy / "datatug-project.json").read_text())
            self.assertEqual("northwind", manifest["coordination"]["namespace"])
            with sqlite3.connect(copy / ".watch-demo/shipping.sqlite") as database:
                self.assertEqual(0, database.execute("SELECT count(*) FROM assignments WHERE deduplication_key='request-11045:assignment'").fetchone()[0])
            demo.mutate(copy, "correct")
            with sqlite3.connect(copy / ".watch-demo/shipping.sqlite") as database:
                self.assertEqual(0, database.execute("SELECT count(*) FROM assignments WHERE deduplication_key='request-11045:assignment'").fetchone()[0])
            demo.mutate(copy, "replay")
            with sqlite3.connect(copy / ".watch-demo/shipping.sqlite") as database:
                self.assertEqual(1, database.execute("SELECT count(*) FROM assignments WHERE deduplication_key='request-11045:assignment'").fetchone()[0])
            demo.mutate(copy, "fail-again")
            with sqlite3.connect(copy / ".watch-demo/shipping.sqlite") as database:
                self.assertEqual(0, database.execute("SELECT count(*) FROM assignments WHERE deduplication_key='request-11045:assignment'").fetchone()[0])
            self.assertEqual(fingerprint, hashlib.sha256(original.read_bytes()).hexdigest())
            self.assertEqual((copy / "fixtures/shipping/logs/base.jsonl").read_bytes(), (ROOT / "demo-project-1/fixtures/shipping/logs/base.jsonl").read_bytes())
            with self.assertRaises(ValueError):
                demo.prepare(copy, "http://127.0.0.1:8988", "northwind")


if __name__ == "__main__":
    unittest.main()
