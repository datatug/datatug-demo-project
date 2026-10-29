#!/usr/bin/env python3
"""Export row-free, content-addressed CodeGrapher snapshots from one Git revision."""
import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess
import urllib.parse

try:
    import yaml
except ImportError as error:
    raise SystemExit("Install scripts/requirements-codegrapher.txt before exporting graphs") from error

ROOT = pathlib.Path(__file__).resolve().parents[1]
FOLDER = 'demo-project-1'
BASE = 'https://datatug.app/project/github.com/datatug/datatug-demo-project/' + FOLDER


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def identity(*parts):
    return json.dumps(parts, separators=(',', ':'), ensure_ascii=False)


def query_ids(value, depth=0):
    if depth > 12:
        raise ValueError('Declared references exceed the graph nesting limit')
    if isinstance(value, list):
        return {ref for item in value for ref in query_ids(item, depth + 1)}
    if not isinstance(value, dict):
        return set()
    refs = {value['queryId']} if isinstance(value.get('queryId'), str) else set()
    for key in ['rows', 'cards', 'widget', 'data', 'sql', 'sources', 'source', 'steps', 'validators', 'query']:
        if key in value:
            refs.update(query_ids(value[key], depth + 1))
    return refs


def export(revision, generated_at):
    revision = git('rev-parse', revision)
    paths = git('ls-tree', '-r', '--name-only', revision, FOLDER).splitlines()
    scope = hashlib.sha256(identity('github.com', 'datatug-demo-project@datatug@demo-project-1', None, None, None).encode()).hexdigest()
    def href(*parts, **query):
        path = BASE + ('/-/' + '/'.join(urllib.parse.quote(p, safe='') for p in parts) if parts else '')
        return path + '?' + urllib.parse.urlencode({'ref': revision, **query})
    def read(path):
        return json.loads(git('show', revision + ':' + path))
    summary = read(FOLDER + '/datatug-project.json')
    project = {'id': scope, 'provider': 'GitHub', 'href': href(), 'revision': revision}
    nodes = [{'id': identity(scope, 'project'), 'kind': 'project', 'label': summary['title'], 'href': href()}]
    edges, references, diagnostics = [], [], []
    queries = {}
    def asset(kind, key, label, page):
        node = {'id': identity(scope, kind, key), 'kind': kind, 'label': label}
        if page is not None:
            node['href'] = href(*page)
        if any(n['id'] == node['id'] for n in nodes):
            return node['id']
        nodes.append(node)
        edges.append({'id': 'contains:' + node['id'], 'source': nodes[0]['id'], 'target': node['id'], 'kind': 'contains', 'label': 'contains'})
        return node['id']
    connections = []
    for catalog_path in paths:
        if catalog_path.startswith(FOLDER + '/connections/') and catalog_path.endswith('.json'):
            catalog = read(catalog_path)
            if catalog.get('format') == 'datatug-demo-connections/v1':
                connections.extend(catalog.get('connections', []))
            elif catalog.get('format') == 'datatug-log-sources/v1':
                connections.extend({'id': source['id'], 'title': source.get('title', source['id']), 'storage': 'logs'} for source in catalog.get('sources', []))
    for connection in connections:
        page = ['graph-source', connection['id']] if connection.get('source', '').startswith('https://demodb.dev/ovdb/v1/databases/') else None
        asset('source', connection['id'], connection.get('title', connection['id']), page)
        for environment in connection.get('environments', []):
            references.append((identity(scope, 'source', connection['id']), 'environment', environment))
    for path in paths:
        rel = path[len(FOLDER) + 1:]
        if rel.startswith('environments/') and rel.endswith('.env.json'):
            value = read(path)
            key = rel.split('/')[1]
            asset('environment', key, value.get('title', key), ['env', key])
        elif rel.startswith('queries/') and rel.endswith('.query.json'):
            value = read(path)
            key = rel[len('queries/'):-len('.query.json')]
            source = asset('query', key, value.get('title', key), ['query', *key.split('/')])
            queries[key] = (value, path)
            if value.get('connectionId'):
                references.append((source, 'source', value['connectionId']))
        elif rel.startswith('boards/') and rel.endswith('/board.json'):
            value = read(path)
            key = rel.split('/')[1]
            source = asset('board', key, value.get('title', key), ['board', key])
            references.extend((source, 'query', q) for q in query_ids(value))
        elif rel.startswith('checks/') and rel.count('/') == 1 and rel.endswith('.json'):
            value = read(path)
            key = value['id']
            source = asset('check', key, value.get('title', key), ['checks', key])
            references.extend((source, 'query', q) for q in query_ids(value))
        elif rel.startswith('entities/') and rel.count('/') == 2 and rel.endswith('.entity.json'):
            value = read(path)
            key = rel.split('/')[1]
            asset('entity', key, value.get('title', key), ['meanings'])
    meaning_path = 'demo.meaning.yaml'
    try:
        meanings = yaml.safe_load(git('show', revision + ':' + meaning_path))
        for concept in meanings.get('concepts', []):
            key = concept['id']
            asset('meaning', key, concept.get('labels', {}).get('en', key), ['meanings'])
            nodes[-1]['definition'] = {'href': 'https://github.com/datatug/datatug-demo-project/blob/' + revision + '/' + meaning_path, 'revision': revision}
        uses_path = FOLDER + '/datatug-meaning-uses.json'
        uses = read(uses_path).get('bindings', []) if uses_path in paths else []
        seen_bindings = set()
        for binding in uses:
            query = queries.get(binding.get('query'))
            if not query:
                continue
            value, path = query
            request = value.get('request', {})
            text = request.get('text')
            if text is None:
                suffix = '.query.sql' if request.get('queryType') == 'SQL' else '.query.tugql'
                body_path = path[:-len('.query.json')] + suffix
                if body_path not in paths:
                    continue
                text = subprocess.check_output(['git', 'show', revision + ':' + body_path], cwd=ROOT, text=True)
            hashed = hashlib.sha256(json.dumps([request.get('queryType'), text, value.get('connectionId', ''), value.get('federation')], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            if hashed != binding.get('queryHash'):
                diagnostics.append('A stale meaning-use declaration was omitted.')
                continue
            source, target = identity(scope, 'query', binding['query']), identity(scope, 'meaning', binding['meaning'])
            if not any(n['id'] == target for n in nodes):
                continue
            edge_id = identity('binding', source, target)
            if edge_id not in seen_bindings:
                edges.append({'id': edge_id, 'source': source, 'target': target, 'kind': 'binding', 'label': 'declared meaning'})
                seen_bindings.add(edge_id)
    except (KeyError, json.JSONDecodeError, yaml.YAMLError):
        diagnostics.append('Project meaning metadata is unavailable.')
    known = {n['id'] for n in nodes}
    for source, kind, key in sorted(set(references)):
        target = identity(scope, kind, key)
        if target not in known:
            diagnostics.append('An unavailable declared ' + kind + ' reference was omitted.')
            continue
        edges.append({'id': identity(source, target, 'uses'), 'source': source, 'target': target, 'kind': 'uses', 'label': 'declared reference'})
    graph = {'format': 'codegrapher-data-graph/v1', 'kind': 'project', 'name': summary['title'], 'generatedAt': generated_at, 'project': project, 'nodes': nodes, 'edges': edges, 'diagnostics': sorted(set(diagnostics))}
    tables = []
    for path in paths:
        rel = path[len(FOLDER) + 1:]
        if rel.startswith('dbmodels/chinook/') and rel.endswith('.columns.json'):
            parts = rel.split('/')
            schema, kind, name = parts[2], parts[3], parts[4]
            columns = []
            for c in read(path).get('columns', []):
                column = {'name': c['name'], 'type': c.get('dbType', '')}
                if 'isNullable' in c:
                    column['nullable'] = c['isNullable']
                if 'pkPosition' in c:
                    column['pkPosition'] = c['pkPosition']
                columns.append(column)
            tables.append({'id': identity(scope, 'chinook-sqlite', 'dev', 'chinook', schema, 'view' if kind == 'views' else 'table', name), 'kind': 'view' if kind == 'views' else 'table', 'label': schema + '.' + name, 'href': href('graph-source', 'chinook-sqlite', 'table', name, schema=schema, env='dev'), 'columns': columns, 'primaryKey': [c['name'] for c in sorted(columns, key=lambda c: c.get('pkPosition', 0)) if c.get('pkPosition', 0) > 0]})
    storage_edges = []
    table_map = {(json.loads(n['id'])[-3], json.loads(n['id'])[-1]): n for n in tables}
    for fk in read(FOLDER + '/dbmodels/chinook/chinook.refs.json')['foreignKeys']:
        source, target = table_map.get((fk['table']['schema'], fk['table']['name'])), table_map.get((fk['refTable']['schema'], fk['refTable']['name']))
        if not source or not target:
            continue
        storage_edges.append({'id': identity('fk', source['id'], fk['name']), 'kind': 'foreign key', 'source': source['id'], 'target': target['id'], 'label': fk['name'], 'columns': fk['columns'], **({'referencedColumns': fk['refColumns']} if 'refColumns' in fk else {})})
    # Derived only from the separately pinned, authored ModelSpec bindings. No matching by concept label.
    meaning_doc = json.loads((ROOT / FOLDER / 'graphs/chinook-meanings.json').read_text())
    for concept in meaning_doc['meanings']:
        bindings = []
        for binding in concept['bindings']:
            table = table_map.get((binding['schema'], binding['table']))
            if table and (not binding.get('column') or any(c['name'] == binding['column'] for c in table['columns'])):
                bindings.append((table, binding))
        if not bindings:
            continue
        node = {'id': identity(scope, 'meaning', concept['id']), 'kind': 'meaning', 'label': concept['label'], 'definition': concept['definition']}
        tables.append(node)
        for table, binding in bindings:
            edge = {'id': identity('binding', table['id'], node['id'], binding.get('column', '')), 'kind': 'binding', 'source': table['id'], 'target': node['id'], 'label': binding.get('column', 'declared entity')}
            if not any(e['id'] == edge['id'] for e in storage_edges):
                storage_edges.append(edge)
    storage = {'format': graph['format'], 'kind': 'database', 'name': 'Chinook stored schema', 'generatedAt': generated_at, 'project': project, 'nodes': tables, 'edges': storage_edges, 'diagnostics': ['Schema comes from the stored project metadata at the displayed Git revision. It is not a live database observation.']}
    return graph, storage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', default='HEAD')
    parser.add_argument('--generated-at', default=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z'))
    args = parser.parse_args()
    folder = ROOT / FOLDER / 'graphs'
    folder.mkdir(exist_ok=True)
    manifest = []
    for graph in export(args.revision, args.generated_at):
        text = json.dumps(graph, separators=(',', ':'), ensure_ascii=False) + '\n'
        if len(text.encode()) > 4 * 1024 * 1024 or len(graph['nodes']) > 5000 or len(graph['edges']) > 20000:
            raise ValueError('Graph exceeds the declared transport limits')
        digest = hashlib.sha256(text.encode()).hexdigest()
        name = graph['kind'] + '-graph.' + digest + '.json'
        (folder / name).write_text(text)
        manifest.append({'kind': graph['kind'], 'path': FOLDER + '/graphs/' + name, 'sha256': digest})
    (folder / 'manifest.json').write_text(json.dumps({'version': 1, 'snapshots': manifest}, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
