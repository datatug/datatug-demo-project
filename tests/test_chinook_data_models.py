"""Offline checks against original logical source bytes and scanned physical metadata."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'demo-project-1'
EVIDENCE = ROOT / 'tests/fixtures/chinook-logical'


def read(path):
    return json.loads(path.read_text())


class ChinookDataModels(unittest.TestCase):
    def test_pinned_reference_and_catalog_folder_selectors(self):
        metadata = read(PROJECT / 'datatug-project.json')['dataModels']
        provenance = read(EVIDENCE / 'provenance.json')['logical']
        self.assertEqual(metadata['version'], 1)
        self.assertEqual(metadata['references'], [{
            'id': 'chinook-v1', 'address': provenance['address'], 'commit': provenance['commit']}])
        self.assertEqual(metadata['catalogBindings'], [
            {'environment': 'local', 'catalog': 'chinook-local', 'reference': 'chinook-v1'},
            {'environment': 'prod', 'catalog': 'chinook-prod', 'reference': 'chinook-v1'}])
        for binding in metadata['catalogBindings']:
            catalog = PROJECT / 'environments' / binding['environment'] / 'catalogs' / binding['catalog']
            config = read(catalog / (binding['catalog'] + '.db.json'))
            self.assertEqual(config['dbModel'], 'chinook')
            self.assertEqual(config['driver'], 'sqlite3')
            self.assertNotEqual(binding['catalog'], Path(config['path']).name)

    def test_exact_original_source_and_license_bytes(self):
        provenance = read(EVIDENCE / 'provenance.json')['logical']
        for filename, key in [('chinook.modelspec.json', 'sha256'), ('LICENSE', 'licenseSHA256')]:
            self.assertEqual(hashlib.sha256((EVIDENCE / filename).read_bytes()).hexdigest(), provenance[key])
        self.assertEqual(provenance['commit'], '3e7bb316d8a438eb7e5930067997a4e4543a275c')
        self.assertEqual(provenance['sha256'], '19be3e0f575e14aa999769da79ba3ecb7fe3cb7e6a7dee151399dcbebfc56a7b')

    def test_all_eleven_records_fields_and_keys_match_scanned_metadata(self):
        records = read(EVIDENCE / 'chinook.modelspec.json')['records']
        bridge = read(EVIDENCE / 'provenance.json')['tables']
        self.assertEqual(len(records), 11)
        self.assertEqual({t['record'] for t in bridge}, set(records))
        scanned = list((PROJECT / 'dbmodels/chinook/main/tables').glob('*/*.columns.json'))
        self.assertEqual(len(scanned), 11)
        for table in bridge:
            with self.subTest(record=table['record']):
                name = table['record']
                self.assertEqual((table['dbModel'], table['schema'], table['table']), ('chinook', 'main', name))
                path = ROOT / table['columnsPath']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), table['columnsSHA256'])
                columns = read(path)['columns']
                self.assertEqual(table['fields'], sorted(records[name]['fields']))
                self.assertEqual(set(table['fields']), {c['name'] for c in columns})
                key = [c['name'] for c in sorted(columns, key=lambda c: c.get('pkPosition', 0)) if c.get('pkPosition', 0)]
                self.assertEqual(records[name]['key'], key)
                self.assertNotIn('id', records[name]['fields'])

    def test_physical_pin_remains_distinct(self):
        provenance = read(EVIDENCE / 'provenance.json')
        physical = read(PROJECT / 'fixtures/chinook/phase1-acceptance.json')['database']
        self.assertEqual(provenance['physical'], physical)
        self.assertEqual(physical['repository'], 'https://github.com/datatug/chinook-database')
        self.assertEqual(physical['revision'], '6334395117e2478a2712e083be614721341c26c9')
        self.assertEqual(physical['sha256'], 'f82efedb6c5c40734609e168bc5be5616a2eca6b90ed0048451a8674625e03a3')
        self.assertNotEqual(physical['repository'], provenance['logical']['repository'])
        self.assertNotEqual(physical['revision'], provenance['logical']['commit'])


if __name__ == '__main__':
    unittest.main()
