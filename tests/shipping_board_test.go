package tests

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/datatug/datatug-core/pkg/datatug"
	"github.com/datatug/datatug-core/pkg/storage/filestore"
	"github.com/stretchr/testify/require"
)

// Definition compatibility only; no source publication or execution evidence.
func TestShippingBoardActualStoreAndSQLiteMappings(t *testing.T) {
	ctx := context.Background()
	board, err := newStore(t).LoadBoard(ctx, "shipping")
	require.NoError(t, err)
	require.NoError(t, board.Validate())
	require.Equal(t, datatug.Parameters{{ID: "order_id", Title: "Order ID", Type: "integer", IsRequired: true}, {ID: "comparison_order_id", Title: "Compare order", Type: "integer", IsRequired: true}}, board.Parameters)
	require.Equal(t, [][]string{{"order_id", "comparison_order_id"}}, board.RequiredParams)
	store := filestore.NewProjectStore("roundtrip", t.TempDir())
	require.NoError(t, store.SaveBoard(ctx, board))
	loaded, err := store.LoadBoard(ctx, "shipping")
	require.NoError(t, err)
	before, err := json.Marshal(board)
	require.NoError(t, err)
	after, err := json.Marshal(loaded)
	require.NoError(t, err)
	require.JSONEq(t, string(before), string(after))
	path, err := filepath.Abs(filepath.Join(projectDir, "fixtures/shipping/base.sqlite"))
	require.NoError(t, err)
	db, err := sql.Open("sqlite", "file:"+path+"?mode=ro&immutable=1")
	require.NoError(t, err)
	t.Cleanup(func() { require.NoError(t, db.Close()) })
	selections, kinds := map[string]bool{}, map[string]bool{}
	keys := map[int64]map[string]bool{}
	for _, row := range loaded.Rows {
		for _, card := range row.Cards {
			require.NotNil(t, card.Widget)
			require.Equal(t, "chart", card.Widget.Name)
			var widget datatug.ChartWidgetDef
			encoded, err := json.Marshal(card.Widget.Data)
			require.NoError(t, err)
			require.NoError(t, json.Unmarshal(encoded, &widget))
			require.Len(t, widget.Sources, 1)
			source := widget.Sources[0]
			bindings := datatug.WidgetParameterBindings{{ID: "order_id", BoardParameterID: "order_id"}}
			switch widget.Chart.Type {
			case "timeline":
				bindings = append(bindings, datatug.WidgetParameterBinding{ID: "comparison_order_id", BoardParameterID: "comparison_order_id"})
				require.Equal(t, "shipping/events-comparison", source.QueryID)
				require.Equal(t, "elapsed", widget.Chart.Timeline.TimeMode)
				require.Equal(t, "elapsed_anchor", widget.Chart.Timeline.AnchorColumn)
			case "heatmap":
				// Hosted Incident/Case runs admit only {order_id} for a query without
				// an admitted comparison declaration; the two-order heatmap is a card.
				require.Equal(t, "shipping/readiness", source.QueryID)
			}
			compared := len(bindings) == 2
			require.Equal(t, bindings, source.Parameters)
			require.Nil(t, source.Transform)
			require.False(t, selections[widget.Chart.SelectionID])
			selections[widget.Chart.SelectionID] = true
			require.False(t, kinds[widget.Chart.Type])
			kinds[widget.Chart.Type] = true
			q, err := newStore(t).LoadQuery(ctx, source.QueryID)
			require.NoError(t, err)
			require.Equal(t, "shipping-working-copy", q.ConnectionID)
			require.NoError(t, q.Validate())
			mapping := map[string]string{}
			var spec any
			switch widget.Chart.Type {
			case "timeline":
				spec = widget.Chart.Timeline
			case "timing-bars":
				spec = widget.Chart.Timing
			case "heatmap":
				spec = widget.Chart.Heatmap
			default:
				t.Fatalf("unexpected kind %q", widget.Chart.Type)
			}
			raw, err := json.Marshal(spec)
			require.NoError(t, err)
			require.NoError(t, json.Unmarshal(raw, &mapping))
			for _, order := range []int64{11045, 11062} {
				args := []any{sql.Named("order_id", order)}
				if compared {
					args = append(args, sql.Named("comparison_order_id", int64(11038)))
				}
				rows, err := db.QueryContext(ctx, q.Text, args...)
				require.NoError(t, err)
				names, err := rows.Columns()
				require.NoError(t, err)
				columns := map[string]int{}
				for i, name := range names {
					columns[name] = i
				}
				for role, name := range mapping {
					if role == "timeMode" {
						continue
					}
					_, exists := columns[name]
					require.True(t, exists, "%s/%s maps missing %s", source.QueryID, role, name)
				}
				count := 0
				for rows.Next() {
					values := make([]any, len(names))
					targets := make([]any, len(names))
					for i := range values {
						targets[i] = &values[i]
					}
					require.NoError(t, rows.Scan(targets...))
					count++
					member := values[columns["order_id"]]
					if compared {
						require.Contains(t, []int64{order, 11038}, member)
					} else {
						require.Equal(t, order, member)
					}
					for _, name := range names {
						if strings.Contains(name, "evidence_ref") {
							require.Nil(t, values[columns[name]], "raw SQL cannot mint execution evidence")
						}
					}
					if widget.Chart.Type == "timing-bars" {
						require.NotNil(t, values[columns["start_at"]])
						require.NotNil(t, values[columns["end_at"]])
						require.NotEmpty(t, values[columns["start_event_id"]])
						require.NotEmpty(t, values[columns["end_event_id"]])
						require.NotEqual(t, values[columns["start_event_id"]], values[columns["end_event_id"]])
						require.NotContains(t, fmt.Sprint(values[columns["end_kind"]]), "partner", "blocked requests have no partner-call span")
					}
					if keys[order] == nil {
						keys[order] = map[string]bool{}
					}
					keyColumn := "row_key"
					if q.Comparison != nil {
						keyColumn = q.Comparison.Projection.ObservationColumn
					}
					if index, exists := columns[keyColumn]; exists && member == order {
						key := fmt.Sprint(values[index])
						require.NotEmpty(t, key)
						keys[order][key] = true
					}
				}
				require.NoError(t, rows.Err())
				require.NoError(t, rows.Close())
				require.Positive(t, count)
			}
		}
	}
	require.Len(t, kinds, 3)
	for key := range keys[11045] {
		require.False(t, keys[11062][key], "held row identities must differ")
	}
}

// The two-order readiness heatmap lives on its own project card, outside the
// shipping board, until the hosted backend can admit a readiness comparison.
func TestShippingReadinessComparisonCard(t *testing.T) {
	ctx := context.Background()
	raw, err := os.ReadFile(filepath.Join(projectDir, "cards/shipping-readiness-comparison/card.json"))
	require.NoError(t, err)
	var card struct {
		ID         string              `json:"id"`
		Parameters datatug.Parameters  `json:"parameters"`
		Widget     datatug.BoardWidget `json:"widget"`
	}
	require.NoError(t, json.Unmarshal(raw, &card))
	require.Equal(t, "shipping-readiness-comparison", card.ID)
	require.Equal(t, "chart", card.Widget.Name)
	var widget datatug.ChartWidgetDef
	encoded, err := json.Marshal(card.Widget.Data)
	require.NoError(t, err)
	require.NoError(t, json.Unmarshal(encoded, &widget))
	require.Len(t, widget.Sources, 1)
	source := widget.Sources[0]
	require.Equal(t, "shipping/readiness-comparison", source.QueryID)
	require.Equal(t, datatug.WidgetParameterBindings{{ID: "order_id", BoardParameterID: "order_id"}, {ID: "comparison_order_id", BoardParameterID: "comparison_order_id"}}, source.Parameters)
	require.Equal(t, "heatmap", widget.Chart.Type)
	require.Equal(t, "request_id", widget.Chart.Heatmap.RowColumn)
	require.Equal(t, "expectation", widget.Chart.Heatmap.ColumnColumn)
	require.Equal(t, "status", widget.Chart.Heatmap.StatusColumn)
	require.Equal(t, "evidence_ref", widget.Chart.Heatmap.EvidenceRefColumn)
	var ids []string
	for _, p := range card.Parameters {
		ids = append(ids, p.ID)
	}
	require.Equal(t, []string{"order_id", "comparison_order_id"}, ids)
	q, err := newStore(t).LoadQuery(ctx, source.QueryID)
	require.NoError(t, err)
	require.NoError(t, q.Validate())
	require.Nil(t, q.Comparison)
	path, err := filepath.Abs(filepath.Join(projectDir, "fixtures/shipping/base.sqlite"))
	require.NoError(t, err)
	db, err := sql.Open("sqlite", "file:"+path+"?mode=ro&immutable=1")
	require.NoError(t, err)
	t.Cleanup(func() { require.NoError(t, db.Close()) })
	rows, err := db.QueryContext(ctx, q.Text, sql.Named("order_id", int64(11045)), sql.Named("comparison_order_id", int64(11038)))
	require.NoError(t, err)
	defer func() { require.NoError(t, rows.Close()) }()
	status := map[string]string{}
	for rows.Next() {
		var order int64
		var request, expectation, value string
		var ignored []any
		names, err := rows.Columns()
		require.NoError(t, err)
		targets := make([]any, len(names))
		for i := range targets {
			targets[i] = new(any)
		}
		require.NoError(t, rows.Scan(targets...))
		for i, name := range names {
			v := *(targets[i].(*any))
			switch name {
			case "order_id":
				order = v.(int64)
			case "request_id":
				request = v.(string)
			case "expectation":
				expectation = v.(string)
			case "status":
				value = v.(string)
			default:
				ignored = append(ignored, v)
			}
		}
		require.Contains(t, []int64{11038, 11045}, order)
		status[request+"/"+expectation] = value
	}
	require.NoError(t, rows.Err())
	// AC healthy-comparison-reads-healthy: 11038 passes for its own attempt; 11045 fails.
	require.Equal(t, "pass", status["request-11038/Route at attempt"])
	require.Equal(t, "pass", status["request-11038/Assignment at attempt"])
	require.Equal(t, "fail", status["request-11045/Effective route"])
	require.Equal(t, "fail", status["request-11045/Accepted assignment"])
	require.Equal(t, "fail", status["request-11045/Route at attempt"])
	require.Len(t, status, 10)
}
