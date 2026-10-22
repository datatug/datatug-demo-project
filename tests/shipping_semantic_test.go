package tests

import (
	"context"
	"database/sql"
	"encoding/json"
	"path/filepath"
	"strings"
	"testing"

	"github.com/datatug/datatug-core/pkg/datatug"
	"github.com/datatug/datatug-core/pkg/semantic"
	"github.com/datatug/datatug-core/pkg/storage/filestore"
	"github.com/stretchr/testify/require"
)

// Definition compatibility only: the learned mapping is a detached copy, not publication.
func TestShippingSemanticSeedActualStoreAndSQLite(t *testing.T) {
	ctx := context.Background()
	store := newStore(t)
	project, err := store.LoadProject(ctx)
	require.NoError(t, err)
	require.NoError(t, project.Validate())
	var entities []*datatug.Entity
	for _, e := range project.Entities {
		if e.ID == "Order" || e.ID == "ShippingRequest" {
			entities = append(entities, e)
		}
	}
	require.Len(t, entities, 2)
	roundtrip := filestore.NewProjectStore("semantic-roundtrip", t.TempDir())
	for _, entity := range entities {
		require.NoError(t, roundtrip.SaveEntity(ctx, entity))
		loaded, err := roundtrip.LoadEntity(ctx, entity.ID)
		require.NoError(t, err)
		require.Equal(t, entity, loaded)
	}
	for _, e := range entities {
		require.Len(t, e.Fields, 1)
		require.Empty(t, e.Fields[0].NamePatterns)
		require.Equal(t, "id", e.Fields[0].ID)
	}
	require.Equal(t, []semantic.Resolution{{Column: "OrderID", Entity: "Order", Field: "id", Provenance: semantic.Declared}}, semantic.Resolve(entities, "northwind-postgresql", "Orders", []semantic.Column{{Name: "OrderID", Type: "integer"}}))
	require.Empty(t, semantic.Resolve(entities, "wrong-source", "Orders", []semantic.Column{{Name: "OrderID", Type: "integer"}}))
	for _, e := range entities {
		if e.ID == "Order" {
			require.Equal(t, "integer", e.Fields[0].Type)
			// Northwind's public SQLite (anonymous Acts 1-2) and PostgreSQL editions, the public
			// Shipping OVDB provider and the signed-in working copy all carry Order.id.
			require.Equal(t, datatug.PhysicalRefs{{Source: "northwind-sqlite", Collection: "Orders", Column: "OrderID"}, {Source: "northwind-postgresql", Collection: "Orders", Column: "OrderID"}, {Source: "shipping-sqlite", Collection: "requests", Column: "order_id"}, {Source: "shipping-working-copy", Collection: "requests", Column: "order_id"}}, e.Fields[0].Mappings)
		} else {
			require.Equal(t, "string", e.Fields[0].Type)
			require.Equal(t, datatug.PhysicalRefs{{Source: "shipping-working-copy", Collection: "requests", Column: "request_id"}}, e.Fields[0].Mappings)
		}
	}
	require.Equal(t, []semantic.Resolution{{Column: "order_id", Entity: "Order", Field: "id", Provenance: semantic.Declared}, {Column: "request_id", Entity: "ShippingRequest", Field: "id", Provenance: semantic.Declared}}, semantic.Resolve(entities, "shipping-working-copy", "requests", []semantic.Column{{Name: "order_id", Type: "integer"}, {Name: "request_id", Type: "string"}}))
	order := semantic.SemanticValue{Entity: "Order", Field: "id", Value: int64(11045), Source: "northwind-postgresql", Collection: "Orders", Column: "OrderID", Provenance: semantic.Declared}
	require.Equal(t, []semantic.Lookup{{Source: "northwind-sqlite", Collection: "Orders", Column: "OrderID", Kind: semantic.LookupSameField, Via: "field:Order.id"}, {Source: "shipping-sqlite", Collection: "requests", Column: "order_id", Kind: semantic.LookupSameField, Via: "field:Order.id"}, {Source: "shipping-working-copy", Collection: "requests", Column: "order_id", Kind: semantic.LookupSameField, Via: "field:Order.id"}}, semantic.RelatedLookups(entities, nil, order))
	// Anonymous Act 2: the public Northwind SQLite order reaches the public Shipping request by meaning, not a join.
	public := semantic.SemanticValue{Entity: "Order", Field: "id", Value: int64(11045), Source: "northwind-sqlite", Collection: "Orders", Column: "OrderID", Provenance: semantic.Declared}
	require.Contains(t, semantic.RelatedLookups(entities, nil, public), semantic.Lookup{Source: "shipping-sqlite", Collection: "requests", Column: "order_id", Kind: semantic.LookupSameField, Via: "field:Order.id"})
	require.Equal(t, []semantic.Resolution{{Column: "order_id", Entity: "Order", Field: "id", Provenance: semantic.Declared}}, semantic.Resolve(entities, "shipping-sqlite", "requests", []semantic.Column{{Name: "order_id", Type: "integer"}, {Name: "request_id", Type: "string"}}), "the public copy carries no ShippingRequest mapping, so Act 7 learning stays a working-copy change")
	files, err := filepath.Glob(filepath.Join(projectDir, "queries/shipping/*.query.json"))
	require.NoError(t, err)
	require.Len(t, files, 11) // 10 SQL + the carrier-status HTTP query
	var queries []*datatug.QueryDef
	var carrier *datatug.QueryDef
	for _, file := range files {
		q, err := store.LoadQuery(ctx, "shipping/"+strings.TrimSuffix(filepath.Base(file), ".query.json"))
		require.NoError(t, err)
		require.NoError(t, q.Validate())
		if q.Type == datatug.QueryTypeHTTP {
			require.Equal(t, "carrier-status", q.ID)
			require.Empty(t, q.ConnectionID)
			require.Equal(t, "https://carrier.demodb.dev/v1/bookings?request_id={request_id}", strings.TrimSpace(q.Text))
			require.Equal(t, datatug.Parameters{{ID: "request_id", Type: "string", IsRequired: true, Meta: &datatug.EntityFieldRef{Entity: "ShippingRequest", Field: "id"}}}, q.Parameters)
			carrier = q
			continue
		}
		require.Equal(t, "shipping-working-copy", q.ConnectionID)
		if q.ID == "readiness-comparison" {
			require.Nil(t, q.Comparison, "timeline pair projection does not describe heatmap cells")
			require.Equal(t, datatug.Parameters{{ID: "order_id", Type: "integer", IsRequired: true, Meta: &datatug.EntityFieldRef{Entity: "Order", Field: "id"}}, {ID: "comparison_order_id", Type: "integer", IsRequired: true}}, q.Parameters)
			continue
		}
		if q.Comparison != nil {
			require.Equal(t, "events-comparison", q.ID)
			require.Len(t, q.Parameters, 2)
			require.Equal(t, datatug.ParameterDef{ID: "comparison_order_id", Type: "integer", IsRequired: true}, q.Parameters[1])
			// Explicit control is not supplied by the selected Order.id semantic value.
			continue
		}
		require.Len(t, q.Parameters, 1)
		require.Equal(t, datatug.ParameterDef{ID: "order_id", Type: "integer", IsRequired: true, Meta: &datatug.EntityFieldRef{Entity: "Order", Field: "id"}}, q.Parameters[0])
		queries = append(queries, q)
	}
	require.NotNil(t, carrier)
	shippingRequest := semantic.SemanticValue{Entity: "ShippingRequest", Field: "id", Value: "request-11038", Source: "shipping-working-copy", Collection: "requests", Column: "request_id", Provenance: semantic.Declared}
	carrierReady, carrierMissing := semantic.Applicable([]*datatug.QueryDef{carrier}, []semantic.SemanticValue{shippingRequest})
	require.Empty(t, carrierMissing)
	require.Equal(t, "request-11038", carrierReady[0].Bindings[0].Value)
	_, carrierMissing = semantic.Applicable([]*datatug.QueryDef{carrier}, []semantic.SemanticValue{order})
	require.Equal(t, []string{"ShippingRequest.id"}, carrierMissing[0].Missing) // an order number alone cannot drive it
	ready, missing := semantic.Applicable(queries, []semantic.SemanticValue{order})
	require.Empty(t, missing)
	require.Len(t, ready, 8)
	for _, q := range ready {
		require.Len(t, q.Bindings, 1)
		require.Equal(t, "order_id", q.Bindings[0].Parameter)
		require.Equal(t, int64(11045), q.Bindings[0].Value)
	}
	ready, missing = semantic.Applicable(queries, nil)
	require.Empty(t, ready)
	require.Len(t, missing, 8)
	for _, q := range missing {
		require.Equal(t, []string{"Order.id"}, q.Missing)
	}
	path, err := filepath.Abs(filepath.Join(projectDir, "fixtures/shipping/base.sqlite"))
	require.NoError(t, err)
	db, err := sql.Open("sqlite", "file:"+path+"?mode=ro&immutable=1")
	require.NoError(t, err)
	t.Cleanup(func() { require.NoError(t, db.Close()) })
	var requestID string
	var partner sql.NullString
	require.NoError(t, db.QueryRowContext(ctx, "SELECT request_id,partner_id FROM current_routes WHERE order_id = ?", int64(11045)).Scan(&requestID, &partner))
	require.NotEmpty(t, requestID)
	require.False(t, partner.Valid, "NULL cannot supply a partner lookup")
	rows, err := db.QueryContext(ctx, "PRAGMA table_info(current_routes)")
	require.NoError(t, err)
	var columns []semantic.Column
	for rows.Next() {
		var cid, notNull, pk int
		var name, typ string
		var d any
		require.NoError(t, rows.Scan(&cid, &name, &typ, &notNull, &d, &pk))
		columns = append(columns, semantic.Column{Name: name, Type: typ})
	}
	require.NoError(t, rows.Err())
	require.NoError(t, rows.Close())
	require.NotEmpty(t, columns)
	require.Empty(t, semantic.Resolve(entities, "shipping-working-copy", "current_routes", columns))
	request := semantic.SemanticValue{Entity: "ShippingRequest", Field: "id", Value: requestID, Source: "shipping-working-copy", Collection: "requests", Column: "request_id", Provenance: semantic.Declared}
	require.Empty(t, semantic.RelatedLookups(entities, nil, request))
	raw, err := json.Marshal(entities)
	require.NoError(t, err)
	var learned []*datatug.Entity
	require.NoError(t, json.Unmarshal(raw, &learned))
	for _, e := range learned {
		if e.ID == "ShippingRequest" {
			e.Fields[0].Mappings = append(e.Fields[0].Mappings, datatug.PhysicalRef{Source: "shipping-working-copy", Collection: "current_routes", Column: "request_id"})
		}
	}
	require.Equal(t, []semantic.Resolution{{Column: "request_id", Entity: "ShippingRequest", Field: "id", Provenance: semantic.Declared}}, semantic.Resolve(learned, "shipping-working-copy", "current_routes", columns))
	require.Equal(t, []semantic.Lookup{{Source: "shipping-working-copy", Collection: "current_routes", Column: "request_id", Kind: semantic.LookupSameField, Via: "field:ShippingRequest.id"}}, semantic.RelatedLookups(learned, nil, request))
	view := request
	view.Collection = "current_routes"
	require.Equal(t, []semantic.Lookup{{Source: "shipping-working-copy", Collection: "requests", Column: "request_id", Kind: semantic.LookupSameField, Via: "field:ShippingRequest.id"}}, semantic.RelatedLookups(learned, nil, view))
	require.Empty(t, semantic.RelatedLookups(entities, nil, request), "in-memory learning must not mutate seed")
	var actualOrder int64
	require.NoError(t, db.QueryRowContext(ctx, "SELECT order_id FROM requests WHERE request_id = ?", requestID).Scan(&actualOrder))
	require.Equal(t, int64(11045), actualOrder)
}
