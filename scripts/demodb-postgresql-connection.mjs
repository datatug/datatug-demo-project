// Keep the published catalogue pending until the public HTTP and browser query
// proofs cover every registered dataset. Verified editions are hosted on Neon
// and served read-only by the public OpenVaultDB server
// (demo-db/websites config/postgresql-api.json, publicApiVerified). DataTug
// opens them at /demo/ovdb/<id>-postgresql through that endpoint, never Neon
// directly. Northwind is also listed on Dev once the public API is verified.
export function demoPostgresqlConnection(id, publicApiVerified = false) {
  return {
    id: `${id}-postgresql`, dataset: id, storage: 'postgresql', tags: [id, 'postgresql'],
    environments: publicApiVerified && id === 'northwind' ? ['dev', 'QA', 'UAT'] : ['QA', 'UAT'],
    readiness: publicApiVerified ? 'public-api' : 'hosted-api-pending',
    source: publicApiVerified
      ? `https://cloud.openvaultdb.com/v1/databases/${id}-postgresql`
      : `https://demodb.dev/${id}/`,
    query: publicApiVerified ? 'ovdb-read' : 'setup-required', copy: 'unavailable',
  };
}
