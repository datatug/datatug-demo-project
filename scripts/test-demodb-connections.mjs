import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const root = resolve(import.meta.dirname, '..');
const project = resolve(root, 'demo-project-1');
const read = (path) => JSON.parse(readFileSync(resolve(project, path), 'utf8'));
const catalog = read('connections/demo-db.json');
const projectFile = read('datatug-project.json');
const datasets = ['chinook', 'northwind', 'pubs', 'sakila', 'adventureworks', 'employees'];

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
        if (dataset === 'chinook') assert.deepEqual(entry.browserFixture, {
          url: 'https://chinook.demodb.dev/data/chinook.sqlite', bytes: 1007616,
        });
        else assert.equal(entry.browserFixture, undefined);
      } else if (storage === 'postgresql') {
        assert.equal(entry.readiness, 'hosted-api-pending');
        assert.equal(entry.query, 'setup-required');
        assert.equal(entry.copy, 'unavailable');
        assert.deepEqual(entry.environments, ['QA', 'UAT']);
      } else {
        assert.equal(entry.readiness, 'hosted-repository');
        assert.equal(entry.query, 'local-checkout-required');
        assert.equal(entry.copy, 'unavailable');
        assert.match(entry.source, /\/tree\/[a-f0-9]{40}\/ingitdb$/);
      }
    }
  }
});

test('environment memberships point to exact catalogue entries without activating pending SQL sources', () => {
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
    } else assert.equal(file.editionConnections.length, 12);
  }
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
  assert.deepEqual(catalog.connections.find((connection) => connection.id === 'chinook-sqlite').browserFixture, {
    url: 'https://chinook.demodb.dev/data/chinook.sqlite', bytes: 1007616,
  });
  for (const entry of catalog.connections.filter((connection) => connection.storage === 'postgresql')) {
    assert.deepEqual(entry.environments, ['QA', 'UAT']);
    assert.equal(entry.readiness, 'hosted-api-pending');
    assert.equal(entry.query, 'setup-required');
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
