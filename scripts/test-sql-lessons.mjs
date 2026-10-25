import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
const project = new URL('../sql-lessons/', import.meta.url);
const read = file => JSON.parse(readFileSync(new URL(file, project), 'utf8'));
const contract = read('fixtures/chinook-teaching-contract.json');
const catalog = read('connections/demo-db.json');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
test('SQL lessons declares only pinned teaching/full public read-only connections and no saved queries', () => {
  assert.equal(read('datatug-project.json').access, 'public');
  assert.equal(read('datatug-project.json').connectionCatalog, 'connections/demo-db.json');
  assert.deepEqual(catalog.connections.map(item => item.id), ['chinook-teaching-sqlite', 'chinook-sqlite']);
  const full = JSON.parse(readFileSync(new URL('../demo-project-1/connections/demo-db.json', import.meta.url))).connections.find(item => item.id === 'chinook-sqlite');
  assert.deepEqual(catalog.connections[1], full);
  const teaching = catalog.connections[0];
  assert.equal(teaching.fixtureSha256, contract.fixture.sha256);
  assert.equal(teaching.browserFixture.url, contract.fixture.url);
  assert.equal(teaching.browserFixture.bytes, contract.fixture.bytes);
  assert.deepEqual(teaching.browserFixture.sourceRights, contract.sourceRights);
  assert.ok(!readdirSync(project).includes('queries'), 'Lesson links create unsaved editors; no queries are stored in this project.');
});
test('SQL lessons derivative bytes and upstream/input rights pins match the committed contract', () => {
  for (const [file, pin] of [['chinook-teaching.sqlite', contract.fixture], ['chinook-teaching-source-rights.json', contract.sourceRights], ['chinook-teaching.sql', contract.inputSql]]) {
    const bytes = readFileSync(new URL('fixtures/' + file, project));
    assert.equal(bytes.length, pin.bytes); assert.equal(hash(bytes), pin.sha256);
  }
  const right = read('fixtures/chinook-teaching-source-rights.json').sourceRights[0];
  assert.deepEqual(right.pins.find(pin => pin.role === 'provider'), contract.upstreamProvider);
  assert.deepEqual(right.pins.find(pin => pin.role === 'input'), contract.inputSql);
  assert.equal(right.source.databaseId, 'chinook-teaching');
  assert.equal(right.declaration.spdx, 'MIT');
  assert.equal(right.transformations.length, 3);
});
test('committed teaching database exactly matches its SQL source and 4/21 population', () => {
  execFileSync('python3', ['-c', `
from pathlib import Path
import sqlite3
p=Path(${JSON.stringify(new URL('../sql-lessons/fixtures/', import.meta.url).pathname)})
actual=sqlite3.connect('file:'+str(p/'chinook-teaching.sqlite')+'?mode=ro', uri=True)
expected=sqlite3.connect(':memory:'); expected.executescript((p/'chinook-teaching.sql').read_text())
for table, count in [('Customer',4),('Invoice',21)]:
 assert actual.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] == count
 assert actual.execute('SELECT * FROM '+table+' ORDER BY '+table+'Id').fetchall() == expected.execute('SELECT * FROM '+table+' ORDER BY '+table+'Id').fetchall()
assert actual.execute('SELECT COUNT(*) FROM Invoice WHERE CustomerId=4').fetchone()[0] == 0
`]);
});
