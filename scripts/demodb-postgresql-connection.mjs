// Keep the published catalogue pending until the public PostgreSQL endpoint
// and its browser read path have been verified for every registered dataset.
export function demoPostgresqlConnection(id, publicApiVerified = false) {
  return {
    id: `${id}-postgresql`, dataset: id, storage: 'postgresql', tags: [id, 'postgresql'],
    environments: ['QA', 'UAT'], readiness: publicApiVerified ? 'public-api' : 'hosted-api-pending',
    source: publicApiVerified
      ? `https://cloud.openvaultdb.com/v1/databases/${id}-postgresql`
      : `https://demodb.dev/${id}/`,
    query: publicApiVerified ? 'ovdb-read' : 'setup-required', copy: 'unavailable',
  };
}
