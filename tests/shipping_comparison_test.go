package tests

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"path/filepath"
	"testing"
	"time"

	"github.com/datatug/datatug-core/pkg/datatug"
	"github.com/datatug/datatug-core/pkg/storage/filestore"
	"github.com/stretchr/testify/require"
)

// Definition and readonly source compatibility, not provider admission or execution proof.
func TestShippingComparisonActualSource(t *testing.T) {
	ctx := context.Background()
	q, err := newStore(t).LoadQuery(ctx, "shipping/events-comparison")
	require.NoError(t, err)
	require.NoError(t, q.Validate())
	require.Equal(t, datatug.Parameters{{ID: "order_id", Type: "integer", IsRequired: true, Meta: &datatug.EntityFieldRef{Entity: "Order", Field: "id"}}, {ID: "comparison_order_id", Type: "integer", IsRequired: true}}, q.Parameters)
	raw, err := json.Marshal(q.Comparison)
	require.NoError(t, err)
	require.JSONEq(t, `{"kind":"pair","primaryInput":"order_id","controlInput":"comparison_order_id","projection":{"memberColumn":"order_id","observationColumn":"event_id","laneColumn":"attempt_id","eventColumn":"kind","sequenceColumn":"sequence","timeColumn":"occurred_at","clockDomainColumn":"clock_domain","precisionColumn":"precision_ms","statusColumn":"status","anchorColumn":"elapsed_anchor"}}`, string(raw))
	roundtrip := filestore.NewProjectStore("comparison-roundtrip", t.TempDir())
	require.NoError(t, roundtrip.SaveQuery(ctx, &datatug.QueryDefWithFolderPath{QueryDef: *q}))
	loaded, err := roundtrip.LoadQuery(ctx, q.ID)
	require.NoError(t, err)
	require.Equal(t, q.Comparison, loaded.Comparison)
	require.Equal(t, q.Text, loaded.Text)
	path, err := filepath.Abs(filepath.Join(projectDir, "fixtures/shipping/base.sqlite"))
	require.NoError(t, err)
	db, err := sql.Open("sqlite", "file:"+path+"?mode=ro&immutable=1")
	require.NoError(t, err)
	defer db.Close()
	rows, err := db.QueryContext(ctx, q.Text, sql.Named("order_id", int64(11045)), sql.Named("comparison_order_id", int64(11038)))
	require.NoError(t, err)
	defer rows.Close()
	names, err := rows.Columns()
	require.NoError(t, err)
	var declared []string
	for _, col := range q.Recordsets[0].Columns {
		declared = append(declared, col.Name)
	}
	require.Equal(t, declared, names)
	require.NotContains(t, names, "row_key", "declared event observation supplies row identity")
	var ids []string
	for rows.Next() {
		values := make([]any, len(names))
		dest := make([]any, len(names))
		for i := range values {
			dest[i] = &values[i]
		}
		require.NoError(t, rows.Scan(dest...))
		v := map[string]any{}
		for i, name := range names {
			v[name] = values[i]
		}
		id := v["event_id"].(string)
		ids = append(ids, id)
		require.Equal(t, "events", v["source_collection"], "original opener requires the actual admitted collection")
		require.Equal(t, id, v["source_record_key"], "original opener uses this same selected observation identity")
		var order, sequence, precision int64
		var attempt, kind, observed, clock, start, artifact, hash string
		var byteStart, byteEnd int64
		require.NoError(t, db.QueryRowContext(ctx, `SELECT r.order_id,a.attempt_id,e.sequence,e.kind,e.occurred_at,e.clock_domain,e.precision_ms,a.started_at,e.artifact,e.artifact_sha256,e.byte_start,e.byte_end FROM events e JOIN attempts a ON a.attempt_id=e.attempt_id JOIN requests r ON r.request_id=a.request_id WHERE e.event_id=?`, id).Scan(&order, &attempt, &sequence, &kind, &observed, &clock, &precision, &start, &artifact, &hash, &byteStart, &byteEnd))
		require.Equal(t, order, v["order_id"])
		require.Equal(t, attempt, v["attempt_id"])
		require.Equal(t, sequence, v["sequence"])
		require.Equal(t, kind, v["kind"])
		require.Equal(t, observed, v["occurred_at"])
		require.Equal(t, clock, v["clock_domain"])
		require.Equal(t, precision, v["precision_ms"])
		require.Equal(t, artifact, v["artifact"])
		require.Equal(t, hash, v["artifact_sha256"])
		require.Equal(t, byteStart, v["byte_start"])
		require.Equal(t, byteEnd, v["byte_end"])
		require.Equal(t, "synthetic-shipping-utc", clock)
		require.Equal(t, int64(1000), precision)
		anchor := int64(0)
		if sequence == 1 && observed == start && (kind == "request-created" || kind == "replay-started") {
			anchor = 1
		}
		require.Equal(t, anchor, v["elapsed_anchor"])
		require.Contains(t, []string{"request-created", "publication-acknowledged", "receiver-received", "route-resolved", "assignment-accepted", "routing-blocked"}, kind)
		status := "pass"
		if kind == "routing-blocked" {
			status = "fail"
		}
		require.Equal(t, status, v["status"])
		instant, err := time.Parse(time.RFC3339, observed)
		require.NoError(t, err)
		origin, err := time.Parse(time.RFC3339, start)
		require.NoError(t, err)
		require.Equal(t, (sequence-1)*1000, instant.Sub(origin).Milliseconds())
		date := "2018-04-30"
		if order == 11045 {
			date = "2018-05-20"
		}
		require.Equal(t, date, observed[:10])
		require.Equal(t, fmt.Sprintf("attempt-%d-1", order), attempt)
		require.Nil(t, v["evidence_ref"])
		require.NotEmpty(t, v["source_generation"])
	}
	require.NoError(t, rows.Err())
	require.Equal(t, []string{"attempt-11038-1-e1", "attempt-11038-1-e2", "attempt-11038-1-e3", "attempt-11038-1-e4", "attempt-11038-1-e5", "attempt-11045-1-e1", "attempt-11045-1-e2", "attempt-11045-1-e3", "attempt-11045-1-e4"}, ids)
}
