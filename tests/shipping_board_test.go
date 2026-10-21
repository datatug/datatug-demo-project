package tests

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
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
	require.Equal(t, datatug.Parameters{{ID: "order_id", Title: "Order ID", Type: "integer", IsRequired: true}}, board.Parameters)
	require.Equal(t, [][]string{{"order_id"}}, board.RequiredParams)
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
			require.Equal(t, datatug.WidgetParameterBindings{{ID: "order_id", BoardParameterID: "order_id"}}, source.Parameters)
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
				rows, err := db.QueryContext(ctx, q.Text, sql.Named("order_id", order))
				require.NoError(t, err)
				names, err := rows.Columns()
				require.NoError(t, err)
				columns := map[string]int{}
				for i, name := range names {
					columns[name] = i
				}
				for role, name := range mapping {
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
					require.Equal(t, order, values[columns["order_id"]])
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
					if index, exists := columns["row_key"]; exists {
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
