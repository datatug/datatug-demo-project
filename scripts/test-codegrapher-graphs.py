#!/usr/bin/env python3
"""Validate immutable graph assets without database access."""
import hashlib
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class GraphSnapshots(unittest.TestCase):
    def test_manifest_and_graph_integrity(self):
        manifest = json.loads((ROOT / 'demo-project-1/graphs/manifest.json').read_text())
        self.assertEqual({s['kind'] for s in manifest['snapshots']}, {'project', 'database'})
        for snapshot in manifest['snapshots']:
            text = (ROOT / snapshot['path']).read_bytes()
            self.assertEqual(hashlib.sha256(text).hexdigest(), snapshot['sha256'])
            self.assertLessEqual(len(text), 4 * 1024 * 1024)
            graph = json.loads(text)
            self.assertEqual(graph['format'], 'codegrapher-data-graph/v1')
            ids = {n['id'] for n in graph['nodes']}
            self.assertEqual(len(ids), len(graph['nodes']))
            self.assertEqual(len({e['id'] for e in graph['edges']}), len(graph['edges']))
            for edge in graph['edges']:
                self.assertIn(edge['source'], ids)
                self.assertIn(edge['target'], ids)
            for node in graph['nodes']:
                self.assertTrue(set(node) <= {'id', 'kind', 'label', 'href', 'columns', 'primaryKey', 'definition'})
                if 'href' in node:
                    self.assertTrue(node['href'].startswith('https://datatug.app/'))
                    self.assertIn('ref=' + graph['project']['revision'], node['href'])
            if graph['kind'] == 'database':
                self.assertEqual(len([n for n in graph['nodes'] if n['kind'] == 'table']), 11)
                self.assertTrue(any(e['kind'] == 'binding' for e in graph['edges']))
                self.assertTrue(any(e['kind'] == 'foreign key' for e in graph['edges']))
                self.assertNotIn('observedAt', graph)

if __name__ == '__main__':
    unittest.main()
