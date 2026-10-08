import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const output = resolve(root, 'demo-project-1/connections/demo-db.json');
const registryPath = process.argv[2];
const directoryPath = process.argv[3];
const hostingPath = process.argv[4];
const check = process.argv[5] === '--check';
if (!registryPath || !directoryPath || !hostingPath || (process.argv.length !== 5 && !(process.argv.length === 6 && check))) {
  throw new Error('usage: node scripts/build-demodb-connections.mjs /path/to/websites/config/databases.json /path/to/directory/index.json /path/to/websites/config/bigquery-hosting.json [--check]');
}
const registryBytes = await readFile(registryPath);
const directoryBytes = await readFile(directoryPath);
const hostingBytes = await readFile(hostingPath);
const registry = JSON.parse(registryBytes.toString('utf8'));
const directory = JSON.parse(directoryBytes.toString('utf8'));
const hosting = JSON.parse(hostingBytes.toString('utf8'));
if (registry.version !== 1 || !Array.isArray(registry.databases) || !registry.databases.length) {
  throw new Error('invalid DemoDB registry');
}
const sourceRevision = '8db734caddc1ead40c1237a9d124b74bf0228efb';
const directoryRevision = '253e419214da22a1bcc2b5e78577bb2d46323074';
// SHA-256 of each provider's pinned source.sqlite, from its manifest.json at
// registry.databases[].commit. A browser copy must reject a different build.
const fixtureSha256 = {
  chinook: '7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15',
  northwind: '279b34136771aee75d802094b3329515a2b01da65d2a20a4a9e3b58c29b4fd20',
  pubs: 'b45b08b7c06441cc0b138b031ea5bd32bd5866aebf874c89d2ebf7fc6abb3691',
  sakila: '9bebeee50fecb1fee115c206a4f380f2f6d1f009e7796b18b8a8cfba7c810454',
  adventureworks: '6a105e1982becfe003fc7a307d7cad9d738390cedd79d166c2167fd817168109',
  employees: '46b49dd0e141cd8db66d57680a10febfccc15e6f54dc7b8f3c2316b55e11c5f0',
};
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const entries = [];
const seen = new Set();
for (const database of registry.databases) {
  const id = database.id;
  if (!/^[a-z][a-z0-9]*$/.test(id) || seen.has(id) || !/^[a-f0-9]{40}$/.test(database.commit)) {
    throw new Error(`invalid or duplicate DemoDB database: ${id}`);
  }
  seen.add(id);
  const ingitdbRevision = registry.ingitdbRevisions?.[id];
  if (!/^[a-f0-9]{40}$/.test(ingitdbRevision)) throw new Error(`missing inGitDB pin: ${id}`);
  if (!/^[a-f0-9]{64}$/.test(fixtureSha256[id])) throw new Error(`missing source fixture pin: ${id}`);
  entries.push({
    id: `${id}-sqlite`, dataset: id, storage: 'sqlite', tags: [id, 'sqlite'],
    environments: ['dev'], readiness: 'public-api',
    source: `https://demodb.dev/ovdb/v1/databases/${id}`,
    descriptor: `https://demodb.dev/ovdb/db/${id}/ovdb-database.json`,
    fixtureSha256: fixtureSha256[id],
    ...(id === 'chinook' ? { browserFixture: {
      url: 'https://chinook.demodb.dev/data/chinook.sqlite',
      bytes: 1007616,
    } } : {}),
    query: 'ovdb-read', copy: 'explicit-browser-import',
  });
  entries.push({
    id: `${id}-postgresql`, dataset: id, storage: 'postgresql', tags: [id, 'postgresql'],
    environments: ['QA', 'UAT'], readiness: 'hosted-api-pending',
    source: `https://demodb.dev/${id}/`, query: 'setup-required', copy: 'unavailable',
  });
  entries.push({
    id: `${id}-ingitdb`, dataset: id, storage: 'ingitdb', tags: [id, 'ingitdb'],
    environments: ['dev'], readiness: 'hosted-repository',
    source: `https://github.com/demo-db/${id}/tree/${ingitdbRevision}/ingitdb`,
    manifest: `https://github.com/demo-db/${id}/blob/${ingitdbRevision}/ingitdb/export-manifest.json`,
    query: 'local-checkout-required', copy: 'unavailable',
  });
}
if (Object.keys(registry.ingitdbRevisions).length !== seen.size) throw new Error('inGitDB pin set differs from datasets');
if (hosting.format !== 'demodb-bigquery-hosting/v1' || hosting.projectId !== 'demodb-dev'
  || hosting.location !== 'US' || hosting.queryAccess?.permissionPrincipal !== 'allAuthenticatedUsers'
  || hosting.queryAccess?.permissionRole !== 'READER' || hosting.queryAccess?.googleAuthenticationRequired !== true
  || hosting.queryAccess?.executionProject !== 'user-selected' || hosting.queryAccess?.browserQueryInDataTug !== 'not-enabled'
  || !Array.isArray(hosting.datasets) || hosting.datasets.length !== seen.size) {
  throw new Error('invalid verified DemoDB BigQuery hosting manifest');
}
const hostedById = new Map(hosting.datasets.map((edition) => [edition.id, edition]));
if (hostedById.size !== seen.size || [...seen].some((id) => {
  const edition = hostedById.get(id);
  const source = registry.databases.find((database) => database.id === id);
  return !edition || !source || edition.datasetId !== id || edition.verified !== true
    || edition.sourceSqliteSha256 !== fixtureSha256[id]
    || edition.sourceRepository !== source.repository || edition.sourceRevision !== source.commit
    || !Number.isSafeInteger(edition.tableCount) || !Number.isSafeInteger(edition.rowCount);
})) throw new Error('BigQuery hosting manifest does not match the pinned DemoDB fixtures');
const bigQueryEditions = [...seen].map((id) => {
  const edition = hostedById.get(id);
  return {
    id: `${id}-bigquery`, dataset: id, storage: 'bigquery', tags: [id, 'bigquery'],
    sourceProjectId: hosting.projectId, datasetId: edition.datasetId, location: hosting.location,
    authentication: 'google-account-required', executionProjectId: 'user-selected',
    publicReadRole: 'READER', publicReadPrincipal: 'allAuthenticatedUsers',
    readiness: 'public-read-user-project-required', query: 'not-enabled-in-browser', copy: 'not-enabled',
    tableCount: edition.tableCount, rowCount: edition.rowCount,
    sourceRepository: edition.sourceRepository, sourceRevision: edition.sourceRevision,
    sourceSqliteSha256: edition.sourceSqliteSha256,
    importToolVersion: hosting.sourceTool.version, importToolCommit: hosting.sourceTool.sourceCommit,
    schemaNotes: hosting.schemaNotes,
    verification: 'https://github.com/demo-db/websites/blob/main/config/bigquery-hosting.json',
  };
});
const plans = ['bigquery-world-bank-wdi', 'bigquery-new-york-citibike'].map((id) => {
  const entry = directory.sources?.find((source) => source.id === id);
  if (!entry || entry.access_mode !== 'bigquery-native' || entry.query_activation !== 'blocked' || entry.status !== 'inactive') {
    throw new Error(`BigQuery directory entry is not a blocked discovery: ${id}`);
  }
  return { id, title: entry.title, tags: [id, 'bigquery'], readiness: 'setup-required',
    directory: `https://github.com/openvaultdb/directory/blob/${directoryRevision}/index.json`,
    query: 'plan-only', copy: 'unavailable', authentication: 'user-google-account', executionProject: 'user-selected' };
});
const result = {
  format: 'datatug-demo-connections/v1',
  source: {
    registry: `https://github.com/demo-db/websites/blob/${sourceRevision}/config/databases.json`,
    registrySha256: sha256(registryBytes),
    discovery: 'https://demodb.dev/.well-known/openvaultdb',
    directory: `https://github.com/openvaultdb/directory/blob/${directoryRevision}/index.json`,
    directorySha256: sha256(directoryBytes),
    bigQueryHosting: 'https://github.com/demo-db/websites/blob/main/config/bigquery-hosting.json',
    bigQueryHostingSha256: sha256(hostingBytes),
    bigQueryImportTool: hosting.sourceTool,
  },
  connections: entries,
  bigQueryEditions,
  bigQueryPlans: plans,
};
const rendered = `${JSON.stringify(result, null, 2)}\n`;
if (check) {
  if ((await readFile(output, 'utf8')) !== rendered) throw new Error('DemoDB connection catalogue is out of date');
} else {
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, rendered);
}
