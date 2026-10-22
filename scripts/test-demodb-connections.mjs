import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import test from 'node:test';

const root = resolve(import.meta.dirname, '..');
const project = resolve(root, 'demo-project-1');
const read = (path) => JSON.parse(readFileSync(resolve(project, path), 'utf8'));
const catalog = read('connections/demo-db.json');
const projectFile = read('datatug-project.json');
const datasets = ['chinook', 'northwind', 'pubs', 'sakila', 'adventureworks', 'employees'];
const sourceRightsPins = {
  chinook: { url: '/assets/showcase/chinook-source-rights.json', bytes: 1348,
    sha256: '41cc624d2cfc9396dbaad7eef3f7d0d187de8e1949e17e25830abe7072a46ea0' },
  northwind: { url: '/assets/showcase/northwind-source-rights.json', bytes: 1405,
    sha256: '523f610b513473d166f4afe0c5c0c77e10e291f1baebcc3cadf556b5a8ac7a82' },
};

test('one canonical project exposes every DemoDB storage edition with truthful readiness', () => {
  assert.equal(projectFile.id, 'datatug-demo-project');
  assert.equal(projectFile.connectionCatalog, 'connections/demo-db.json');
  assert.deepEqual(projectFile.environments.map((environment) => environment.id).sort(), ['QA', 'UAT', 'dev', 'local', 'prod']);
  assert.equal(catalog.format, 'datatug-demo-connections/v1');
  assert.equal(catalog.source.discovery, 'https://demodb.dev/.well-known/openvaultdb');
  assert.equal(catalog.connections.length, 18);
  assert.deepEqual(new Set(catalog.connections.map((connection) => connection.dataset)), new Set(datasets));
  for (const dataset of datasets) {
    for (const storage of ['sqlite', 'postgresql', 'ingitdb']) {
      const entry = catalog.connections.find((connection) => connection.id === `${dataset}-${storage}`);
      assert.ok(entry, `${dataset}/${storage}`);
      assert.deepEqual(entry.tags.slice(0, 2), [dataset, storage]);
      assert.equal(entry.dataset, dataset);
      assert.equal(entry.storage, storage);
      assert.match(entry.source, /^https:\/\//);
      if (storage === 'sqlite') {
        assert.equal(entry.readiness, 'public-api');
        assert.equal(entry.query, 'ovdb-read');
        assert.equal(entry.copy, 'explicit-browser-import');
        assert.deepEqual(entry.environments, ['dev']);
        if (['chinook', 'northwind'].includes(dataset)) {
          assert.deepEqual(entry.browserFixture, {
            url: `/assets/showcase/${dataset}.sqlite`,
            bytes: dataset === 'chinook' ? 1007616 : 602112,
            sourceRights: sourceRightsPins[dataset],
          });
        }
        else assert.equal(entry.browserFixture, undefined);
      } else if (storage === 'postgresql') {
        // Hosted on Neon, served read-only by the public OpenVaultDB server; DataTug opens it through OVDB only.
        assert.equal(entry.readiness, 'public-api');
        assert.equal(entry.query, 'ovdb-read');
        assert.equal(entry.copy, 'unavailable');
        assert.equal(entry.source, `https://cloud.openvaultdb.com/v1/databases/${dataset}-postgresql`);
        assert.doesNotMatch(JSON.stringify(entry), /neon|postgres(ql)?:\/\//i);
        assert.deepEqual(entry.environments, dataset === 'northwind' ? ['dev', 'QA', 'UAT'] : ['QA', 'UAT']);
      } else {
        assert.equal(entry.readiness, 'hosted-repository');
        assert.equal(entry.query, 'local-checkout-required');
        assert.equal(entry.copy, 'unavailable');
        assert.match(entry.source, /\/tree\/[a-f0-9]{40}\/ingitdb$/);
      }
    }
  }
});

test('environment memberships point to exact catalogue entries without adding database servers', () => {
  const ids = new Set(catalog.connections.map((connection) => connection.id));
  for (const env of ['dev', 'QA', 'UAT']) {
    const file = read(`environments/${env}/${env}.env.json`);
    assert.equal(file.id, env);
    assert.equal(new Set(file.editionConnections).size, file.editionConnections.length);
    for (const id of file.editionConnections) {
      assert.ok(ids.has(id), `${env}/${id}`);
      assert.ok(catalog.connections.find((connection) => connection.id === id).environments.includes(env));
    }
    if (env === 'QA' || env === 'UAT') {
      assert.equal(file.dbServers.length, 0);
      assert.equal(file.editionConnections.length, 6);
    } else assert.equal(file.editionConnections.length, 13);
  }
  const dev = read('environments/dev/dev.env.json');
  for (const id of ['northwind-sqlite', 'northwind-postgresql']) {
    assert.ok(dev.editionConnections.includes(id), `dev must admit ${id}`);
    assert.ok(catalog.connections.find((connection) => connection.id === id).environments.includes('dev'));
  }
});

test('environment presentation uses distinct labels and supported icons and tones', () => {
  const icons = new Set(['globe-outline', 'desktop-outline', 'flask-outline', 'cloud-outline', 'shield-checkmark-outline', 'warning-outline']);
  const tones = new Set(['neutral', 'primary', 'success', 'warning', 'danger']);
  const ids = projectFile.environments.map(({ id }) => id);
  const labels = new Set();
  for (const id of ids) {
    const file = read(`environments/${id}/${id}.env.json`);
    assert.equal(file.id, id);
    assert.ok(file.presentation?.label?.trim(), `${id} needs a display label`);
    assert.ok(icons.has(file.presentation.icon), `${id} uses an unsupported icon`);
    assert.ok(tones.has(file.presentation.tone), `${id} uses an unsupported tone`);
    assert.ok(!labels.has(file.presentation.label), `${id} repeats a display label`);
    labels.add(file.presentation.label);
  }
  assert.equal(read('environments/prod/prod.env.json').presentation.tone, 'danger');
});

test('comparison fixtures are separate, pinned Chinook artifacts with source provenance', () => {
  assert.equal(catalog.connections.length, 18);
  assert.deepEqual(catalog.comparisonFixtures.map(({ id, role }) => [id, role]), [
    ['chinook-baseline', 'baseline'], ['chinook-candidate', 'candidate'],
  ]);
  const [baseline, candidate] = catalog.comparisonFixtures;
  const provenance = {
    providerRepository: 'https://github.com/demo-db/chinook',
    providerCommit: '95d14a11256f8db512d5ecd7ea5be56e01d51781',
    manifestPath: 'fixtures/compare/manifest.json',
    manifestSha256: 'aa80280419d5e0e8bd99ae97574b5d91cbf4df6e560e536f8699f42ec175c887',
    hostMergeCommit: '44d9f354ed5b7bf8aaf496dfde15e81d4307730c',
  };
  assert.deepEqual(baseline, {
    id: 'chinook-baseline', role: 'baseline', displayLabel: 'Pinned upstream baseline',
    environmentLabel: 'Public baseline endpoint',
    url: 'https://chinook.demodb.dev/data/chinook.sqlite',
    sha256: '7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15',
    bytes: 1007616,
    schemaSha256: '8392c76c7fd8da3bce20d1cec2c60223692a08915787f5c7393cec1c0b6acb94',
    provenance,
  });
  assert.deepEqual(candidate, {
    id: 'chinook-candidate', role: 'candidate', displayLabel: 'Synthetic comparison fixture (not production data)',
    environmentLabel: 'Publicly hosted comparison fixture',
    url: 'https://chinook.demodb.dev/data/compare/3369d25729dea9e21facc7226aee3d5247fa0f3d8d4be4678aa9247fd064845f.sqlite',
    sha256: '3369d25729dea9e21facc7226aee3d5247fa0f3d8d4be4678aa9247fd064845f',
    bytes: 1007616,
    schemaSha256: '8392c76c7fd8da3bce20d1cec2c60223692a08915787f5c7393cec1c0b6acb94',
    provenance,
  });
  for (const entry of catalog.connections.filter((connection) => connection.storage === 'postgresql')) {
    assert.deepEqual(entry.environments, entry.dataset === 'northwind' ? ['dev', 'QA', 'UAT'] : ['QA', 'UAT']);
    assert.equal(entry.readiness, 'public-api');
    assert.equal(entry.query, 'ovdb-read');
  }
  assert.equal(catalog.bigQueryEditions.length, datasets.length);
  assert.equal(catalog.bigQueryPlans.length, 2);
  assert.ok(catalog.bigQueryEditions.every((edition) => edition.query === 'not-enabled-in-browser'
    && edition.copy === 'not-enabled' && edition.executionProjectId === 'user-selected'));
});

test('BigQuery plans link to blocked Directory discoveries and cannot run or copy', () => {
  assert.equal(catalog.bigQueryPlans.length, 2);
  for (const plan of catalog.bigQueryPlans) {
    assert.equal(plan.query, 'plan-only');
    assert.equal(plan.copy, 'unavailable');
    assert.equal(plan.readiness, 'setup-required');
    assert.equal(plan.authentication, 'user-google-account');
    assert.equal(plan.executionProject, 'user-selected');
    assert.match(plan.directory, /\/openvaultdb\/directory\/blob\/[a-f0-9]{40}\/index\.json$/);
  }
});

test('hosted BigQuery editions are verified and require a user-owned execution project', () => {
  assert.equal(catalog.bigQueryEditions.length, datasets.length);
  assert.equal(catalog.source.bigQueryImportTool.version, 'v0.62.0');
  assert.match(catalog.source.bigQueryHosting, /^https:\/\/github\.com\/demo-db\/websites\/blob\/main\/config\/bigquery-hosting\.json$/);
  assert.match(catalog.source.bigQueryHostingSha256, /^[a-f0-9]{64}$/);
  const expected = new Map([
    ['chinook', [11, 15607]], ['northwind', [13, 3310]], ['pubs', [11, 255]],
    ['sakila', [16, 47268]], ['adventureworks', [71, 759240]], ['employees', [6, 13584]],
  ]);
  for (const edition of catalog.bigQueryEditions) {
    assert.equal(edition.storage, 'bigquery');
    assert.equal(edition.sourceProjectId, 'demodb-dev');
    assert.equal(edition.datasetId, edition.dataset);
    assert.equal(edition.location, 'US');
    assert.equal(edition.authentication, 'google-account-required');
    assert.equal(edition.publicReadRole, 'READER');
    assert.equal(edition.publicReadPrincipal, 'allAuthenticatedUsers');
    assert.equal(edition.executionProjectId, 'user-selected');
    assert.equal(edition.query, 'not-enabled-in-browser');
    assert.equal(edition.copy, 'not-enabled');
    assert.deepEqual([edition.tableCount, edition.rowCount], expected.get(edition.dataset));
    assert.match(edition.sourceSqliteSha256, /^[a-f0-9]{64}$/);
    assert.match(edition.sourceRevision, /^[a-f0-9]{40}$/);
  }
  assert.equal(catalog.connections.length, 18);
  assert.equal(catalog.bigQueryPlans.length, 2);
});


test('showcase charts use exact admitted server DTQL and inspector uses explicit server definitions', () => {
  const board = read('boards/showcase/board.json');
  const race = board.rows[0].cards[0].widget;
  const bars = board.rows[1].cards[0].widget;
  const inspectorRow = board.rows.find((row) => row.cards.some((card) => card.id === 'source-inspector'));
  assert.ok(inspectorRow, 'source inspector is present');
  assert.equal(inspectorRow.cards.length, 1, 'inspector owns its row');
  const inspector = inspectorRow.cards.find((card) => card.id === 'source-inspector');
  assert.equal(inspector.cols, 12, 'inspector uses the full row');
  const tabs = inspector.widget.data.tabs;
  const paired = board.rows.flatMap((row) => row.cards).find((card) => card.id === 'shared-customer-countries');
  assert.equal(paired.cols, 6);
  assert.deepEqual(paired.widget.data.sources, [{ id: 'shared-country-counts', queryId: 'demodb/customer-country-comparison-server' }]);
  assert.deepEqual(paired.widget.data.chart, {
    type: 'bar', categoryColumn: 'country', unit: 'customer records', selectionId: 'customer-country',
    series: [{ id: 'northwind', title: 'Northwind', valueColumn: 'northwindCustomers' }, { id: 'chinook', title: 'Chinook', valueColumn: 'chinookCustomers' }],
  });
  assert.deepEqual(tabs[0].widget.data.sql.presentationFilter, { selectionId: 'customer-country', column: 'ShipCountry' });
  assert.equal(race.data.sources[0].queryId, 'demodb/northwind-orders-full-sqlite');
  assert.equal(bars.data.sources[0].queryId, 'demodb/northwind-shipping-country-count-sqlite');
  assert.deepEqual(tabs.map((tab) => tab.widget.data.sql.queryId), [
    'demodb/northwind-orders-full-sqlite', 'demodb/northwind-country-counts-server',
    'demodb/customer-country-comparison-server', 'demodb/chinook-billing-server',
  ]);
  assert.deepEqual(tabs.map((tab) => tab.title), [
    'Northwind · server orders', 'Northwind · server countries',
    'Northwind + Chinook · shared countries', 'Chinook · customer billing',
  ]);
  for (const [id, columns, sha256] of [
    ['northwind-orders-full-sqlite', 14, 'ba8e43a239489bfb17761990658909b969c9d4939dd8aa008615c867671b2c52'],
    ['northwind-shipping-country-count-sqlite', 2, '2e320d487d7bbe7dbfc53abc55c08d12eb80a2e79b34cfe15a2148fa362acc9a'],
  ]) {
    const query = read(`queries/demodb/${id}.query.json`);
    assert.equal(query.id, id);
    assert.equal(query.type, 'DTQL');
    assert.equal(query.recordsets[0].columns.length, columns);
    assert.equal(createHash('sha256').update(readFileSync(resolve(project, `queries/demodb/${id}.query.dtql`))).digest('hex'), sha256);
  }
  for (const [id, database, tables, columns] of [
    ['northwind-orders-server', 'northwind', ['Orders'], 14],
    ['northwind-country-counts-server', 'northwind', ['Orders'], 2],
    ['chinook-billing-server', 'chinook', ['Customer', 'Invoice'], 6],
  ]) {
    const query = read(`queries/demodb/${id}.query.json`);
    assert.equal(query.id, id);
    assert.equal(query.type, 'DTQL');
    assert.equal(query.connectionId, undefined, 'server queries cannot fall back to a browser fixture connection');
    assert.equal(query.federation.ovdbBaseUrl, 'https://ovdb.demodb.dev');
    if (id === 'chinook-billing-server') {
      assert.deepEqual(query.federation.expectedServerIdentity, {
        baseUrl: query.federation.ovdbBaseUrl, serverId: 'https://demodb.dev/ovdb',
      });
    } else {
      assert.equal(query.federation.expectedServerIdentity, undefined, 'Orders queries retain their existing legacy binding');
    }
    assert.deepEqual(query.federation.tables.map((table) => table.database), tables.map(() => database));
    assert.deepEqual(query.federation.tables.map((table) => table.name), tables);
    assert.equal(query.recordsets[0].columns.length, columns);
    const dtql = readFileSync(resolve(project, `queries/demodb/${id}.query.dtql`), 'utf8');
    assert.match(dtql, new RegExp(`database: ${database}`));
    assert.match(dtql, /alias:/);
    assert.doesNotMatch(dtql, /\b(?:INSERT|UPDATE|DELETE|ATTACH|PRAGMA)\b/i);
  }
});

test('customer queries bind the provider identity to their selected base without changing Orders admission', () => {
  const bindings = [
    ['demodb/northwind-customer-country-counts-server', 'https://cloud.openvaultdb.com'],
    ['demodb/chinook-customer-country-counts-server', 'https://cloud.openvaultdb.com'],
    ['demodb/customer-country-comparison-server', 'https://cloud.openvaultdb.com'],
    ['demodb/chinook-billing-server', 'https://ovdb.demodb.dev'],
    ['hosted/chinook-customer-preview', 'https://demodb.dev/ovdb'],
  ];
  for (const [id, baseUrl] of bindings) {
    const query = read(`queries/${id}.query.json`);
    assert.equal(query.type, 'DTQL', id);
    assert.equal(query.federation.ovdbBaseUrl, baseUrl, id);
    assert.deepEqual(query.federation.expectedServerIdentity, {
      baseUrl, serverId: 'https://demodb.dev/ovdb',
    }, id);
    assert.ok(query.federation.tables.some((table) =>
      (table.database === 'northwind' && table.name === 'Customers') ||
      (table.database === 'chinook' && table.name === 'Customer')), id);
    assert.equal(query.federation.expectedSourceRights, undefined, 'live server terms are not replaced by copied publisher assertions');
  }
});

test('shared-country comparison executes one qualified server plan with distinct customer-record counts', () => {
  const query = read('queries/demodb/customer-country-comparison-server.query.json');
  assert.equal(query.id, 'customer-country-comparison-server');
  assert.equal(query.type, 'DTQL');
  assert.equal(query.connectionId, undefined, 'comparison cannot fall back to a browser fixture');
  assert.equal(query.federation.ovdbBaseUrl, 'https://cloud.openvaultdb.com');
  assert.equal(query.federation.bounds, undefined, 'comparison is a whole server query, not bounded client scans');
  assert.equal(query.federation.lookups, undefined);
  assert.deepEqual(query.federation.tables, [
    { database: 'northwind', name: 'Customers', fields: ['CustomerID', 'Country'] },
    { database: 'chinook', name: 'Customer', fields: ['CustomerId', 'Country'] },
  ]);
  assert.deepEqual(query.recordsets[0].columns, [
    { name: 'country', type: 'string' },
    { name: 'northwindCustomers', type: 'integer' },
    { name: 'chinookCustomers', type: 'integer' },
  ]);
  assert.match(query.purpose, /customer-record counts/i);
  assert.match(query.purpose, /UK\/United Kingdom/);
  assert.match(query.purpose, /null countries/);
  assert.match(query.purpose, /only one sample/);
  const dtql = readFileSync(resolve(project, 'queries/demodb/customer-country-comparison-server.query.dtql'), 'utf8');
  assert.match(dtql, /database: northwind/);
  assert.match(dtql, /database: chinook/);
  assert.match(dtql, /field: Country, source: n.*op: '=='.*field: Country, source: c/);
  assert.match(dtql, /groupBy: \[\{field: Country, source: n\}\]/);
  assert.match(dtql, /function: count, distinct: true, args: \[\{field: CustomerID, source: n\}\]/);
  assert.match(dtql, /function: count, distinct: true, args: \[\{field: CustomerId, source: c\}\]/);
  assert.match(dtql, /limit: 100\s*$/);
  assert.doesNotMatch(dtql, /\b(?:INSERT|UPDATE|DELETE|ATTACH|PRAGMA)\b/i);
});

test('explicit optional browser SQL definitions retain their pinned fixtures', () => {
  const definitions = [
    ['northwind-orders-browser-sqlite', 'northwind-sqlite', 14, 'a1b3d75996c5ffa611ee2f7e9c49234a142cdd1595e7249056621b010d1daab5'],
    ['northwind-country-counts-browser-sqlite', 'northwind-sqlite', 2, '4ad98f415bb0f2a87efc481703418c93ae5bebff4903e6dc83c631f8edf28d26'],
    ['chinook-billing-browser-sqlite', 'chinook-sqlite', 5, 'fdf80f3949f4a1c31e2e317e5356455ce97e769484a197b5736eb0463baf93a1'],
  ];
  for (const [id, connectionId, columns, sha256] of definitions) {
    const query = read(`queries/demodb/${id}.query.json`);
    assert.equal(query.id, id);
    assert.equal(query.type, 'SQL');
    assert.equal(query.connectionId, connectionId);
    assert.equal(query.recordsets[0].columns.length, columns);
    const sql = readFileSync(resolve(project, `queries/demodb/${id}.query.sql`));
    assert.equal(createHash('sha256').update(sql).digest('hex'), sha256);
    assert.match(sql.toString(), /^SELECT\b/);
    const connection = catalog.connections.find((entry) => entry.id === connectionId);
    assert.match(connection.fixtureSha256, /^[a-f0-9]{64}$/);
    assert.equal(connection.browserFixture.url, `/assets/showcase/${connection.dataset}.sqlite`);
  }
});


test('direct log inputs retain their mount and relocated documentation stays linked and reproducible offline', () => {
  const config = read('fixtures/logs/ovdb-direct.json');
  assert.equal(config.sources.files[0].Root, 'demo-project-1/fixtures/logs');
  for (const source of config.sources.files[0].Sources) {
    assert.ok(existsSync(resolve(root, config.sources.files[0].Root, source.Path)));
  }
  const documents = ['README.md', 'demo-project-1/README.md', 'demo-project-1/fixtures/logs/README.md',
    'docs/logs/README.md', 'docs/logs/guide.md', 'docs/logs/walkthrough.html', 'docs/logs/walkthrough.template.html'];
  const publicPrefix = 'https://github.com/datatug/datatug-demo-project/blob/main/';
  for (const document of documents) {
    const text = readFileSync(resolve(root, document), 'utf8');
    assert.doesNotMatch(text, /(?:demo-project-1\/)?fixtures\/logs\/(?:guide\.md|walkthrough(?:\.template)?\.html|screenshot-[^ )"']+)/);
    for (const match of text.matchAll(/(?:\]\(([^)]+)\)|href="([^"]+)"|src="([^"]+)")/g)) {
      const link = (match[1] || match[2] || match[3]).split('#')[0];
      if (!link || (/^https?:/.test(link) && !link.startsWith(publicPrefix))) continue;
      if (!document.startsWith('docs/') && !link.includes('docs/logs')) continue;
      const target = link.startsWith(publicPrefix) ? resolve(root, link.slice(publicPrefix.length)) : resolve(root, dirname(document), link);
      assert.ok(existsSync(target), `${document}: missing ${link}`);
    }
  }
  execFileSync('python3', ['-c', `
import json, pathlib, re, runpy, tempfile
root = pathlib.Path.cwd()
docs = root / 'docs/logs'
html = (docs / 'walkthrough.html').read_text()
data = json.loads(re.search(r'<script id="evidence-data" type="application/json">(.*?)</script>', html, re.S).group(1))
module = runpy.run_path(str(root / 'scripts/build-logs-walkthrough.py'))
assert module['TARGET'] == docs / 'walkthrough.html'
assert module['TEMPLATE'] == docs / 'walkthrough.template.html'
calls = []
def query(collection):
    calls.append(collection)
    return data[{'fulfillment_events': 'fulfillment', 'carrier_events': 'carrier'}[collection]]
with tempfile.TemporaryDirectory() as directory:
    target = pathlib.Path(directory) / 'walkthrough.html'
    module['main'].__globals__.update(query=query, TARGET=target)
    module['main']()
    assert target.read_text() == html, 'committed HTML differs from offline builder output'
assert calls == ['fulfillment_events', 'carrier_events']
`], { cwd: root });
});
