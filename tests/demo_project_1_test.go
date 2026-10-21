// Package tests exercises datatug-demo-projects/demo-project-1 against a
// real, tagged datatug-core: it proves the project loads and validates, that
// the declared field mappings plan task 4 (see ~/briefs/s3b-demo-mappings.md)
// listed are actually present, and that datatug-core's pkg/semantic resolver
// and applicability logic (PRs #303/#304) produce the results the
// core-investigation-loop feature's journeys describe for this project.
package tests

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/dal-go/dalgo/dtql"
	"github.com/datatug/datatug-core/pkg/datatug"
	"github.com/datatug/datatug-core/pkg/semantic"
	"github.com/datatug/datatug-core/pkg/storage/filestore"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

const projectDir = "../demo-project-1"

func newStore(t *testing.T) datatug.ProjectStore {
	t.Helper()
	return filestore.NewProjectStore("demo-project-1", projectDir)
}

func fieldByID(t *testing.T, entity *datatug.Entity, fieldID string) *datatug.EntityField {
	t.Helper()
	for _, f := range entity.Fields {
		if f.ID == fieldID {
			return f
		}
	}
	t.Fatalf("field %s.%s not found", entity.ID, fieldID)
	return nil
}

// loadQueries loads the three library queries these tests need, by their
// folder-qualified id. datatug-core's Project.LoadProject does not populate
// Project.Queries at all (a separate, still-open gap, unrelated to the
// entities/boards/dbmodels dual-layout fixes this module now pins) - so
// tests that need query definitions load them directly.
func loadQueries(t *testing.T, store datatug.ProjectStore, ids ...string) datatug.QueryDefs {
	t.Helper()
	ctx := context.Background()
	queries := make(datatug.QueryDefs, len(ids))
	for i, id := range ids {
		q, err := store.LoadQuery(ctx, id)
		require.NoError(t, err, "failed to load query %s", id)
		queries[i] = q
	}
	return queries
}

type queryMetadata struct {
	ID                   string                      `json:"id"`
	Title                string                      `json:"title"`
	Type                 string                      `json:"type"`
	ConnectionID         string                      `json:"connectionId"`
	Purpose              string                      `json:"purpose"`
	Parameters           []any                       `json:"parameters"`
	Targets              []any                       `json:"targets"`
	RelationshipBindings []queryRelationshipMetadata `json:"relationshipBindings"`
}

type queryRelationshipMetadata struct {
	ID      string `json:"id"`
	Version string `json:"version"`
	From    struct {
		Schema string `json:"schema"`
		Table  string `json:"table"`
	} `json:"from"`
	To struct {
		Schema string `json:"schema"`
		Table  string `json:"table"`
	} `json:"to"`
	Pairs []struct {
		FromField string `json:"fromField"`
		ToField   string `json:"toField"`
	} `json:"pairs"`
}

func readQueryMetadata(t *testing.T, relativePath string) queryMetadata {
	t.Helper()
	path := filepath.Join(projectDir, "queries", relativePath+".query.json")
	data, err := os.ReadFile(path)
	require.NoError(t, err, "failed to read query metadata %s", path)
	var metadata queryMetadata
	require.NoError(t, json.Unmarshal(data, &metadata), "failed to parse query metadata %s", path)
	return metadata
}

// TestDemoProject1_Validate checks the project as the real filestore loads it:
// entities, all saved boards (including nested chart/query widgets), the
// Chinook model, environments and saved queries must validate together.
func TestDemoProject1_Validate(t *testing.T) {
	store := newStore(t)
	project, err := store.LoadProject(context.Background())
	require.NoError(t, err, "failed to load %s", projectDir)

	wantEntityIDs := []string{"Album", "Artist", "Country", "Customer", "Invoice", "InvoiceLine", "Order", "Person", "ShippingRequest", "Track"}
	assert.ElementsMatch(t, wantEntityIDs, project.Entities.IDs())

	if assert.Len(t, project.Boards, 4) {
		boardIDs := make([]string, 0, len(project.Boards))
		for _, board := range project.Boards {
			boardIDs = append(boardIDs, board.ID)
			require.NotEmpty(t, board.Rows, "board %s has no useful content", board.ID)
			assert.NoError(t, board.Validate(), "board %s is invalid", board.ID)
		}
		assert.ElementsMatch(t, []string{"board1", "northwind", "showcase", "shipping"}, boardIDs)
	}

	if assert.Len(t, project.DbModels, 1) {
		assert.Equal(t, "chinook", project.DbModels[0].ID)
	}

	wantEnvIDs := []string{"dev", "local", "prod", "QA", "UAT"}
	assert.ElementsMatch(t, wantEnvIDs, project.Environments.IDs())

	require.NotNil(t, project.Queries)
	assert.NoError(t, project.Validate())
}

func TestDemoBoardsReferencePublishedQueries(t *testing.T) {
	store := newStore(t)
	project, err := store.LoadProject(context.Background())
	require.NoError(t, err)

	for _, board := range project.Boards {
		for _, row := range board.Rows {
			for _, card := range row.Cards {
				require.NotNil(t, card.Widget, "board %s card %s", board.ID, card.ID)
				assertBoardWidgetQueryReferences(t, store, board.ID, card.ID, card.Widget)
			}
		}
	}
}

// Check every saved query through the real project loader, including chart
// sources and SQL children of tabs. A valid widget shape alone cannot catch a
// renamed or deleted query file, nor an empty saved query body.
func assertBoardWidgetQueryReferences(t *testing.T, store datatug.ProjectStore, boardID, cardID string, widget *datatug.BoardWidget) {
	t.Helper()
	data, err := json.Marshal(widget.Data)
	require.NoError(t, err)
	checkQuery := func(queryID string) {
		t.Helper()
		require.NotEmpty(t, queryID, "board %s card %s", boardID, cardID)
		metadata := readQueryMetadata(t, queryID)
		assert.Equal(t, filepath.Base(queryID), metadata.ID)
		query, err := store.LoadQuery(context.Background(), queryID)
		require.NoError(t, err, "board %s card %s query %s", boardID, cardID, queryID)
		require.NoError(t, query.Validate())
		require.NotEmpty(t, query.Text, "board %s card %s query %s has no saved body", boardID, cardID, queryID)
		assert.Equal(t, metadata.ConnectionID, query.ConnectionID)
	}
	switch widget.Name {
	case "SQL":
		var def datatug.SQLWidgetDef
		require.NoError(t, json.Unmarshal(data, &def))
		checkQuery(def.SQL.QueryID)
		if boardID == "board1" {
			assert.Equal(t, "chinook-sqlite", readQueryMetadata(t, def.SQL.QueryID).ConnectionID)
		}
	case "chart":
		var def datatug.ChartWidgetDef
		require.NoError(t, json.Unmarshal(data, &def))
		require.NotEmpty(t, def.Sources)
		for _, source := range def.Sources {
			checkQuery(source.QueryID)
		}
	case "tabs":
		var def datatug.TabsWidgetDef
		require.NoError(t, json.Unmarshal(data, &def))
		require.NotEmpty(t, def.Tabs)
		for _, tab := range def.Tabs {
			if tab.Widget.Name == "" {
				continue // older boards may contain title-only placeholder tabs
			}
			if boardID == "showcase" {
				require.NotEmpty(t, tab.ID, "new showcase tabs need stable IDs")
			}
			assertBoardWidgetQueryReferences(t, store, boardID, cardID+"/"+tab.Title, &tab.Widget)
		}
	default:
		t.Fatalf("board %s card %s has untested widget type %q", boardID, cardID, widget.Name)
	}
}

// TestDemoProject1_Environments loads every demo-project-1 environment
// individually and asserts its dbServers.sqlite3 ServerRef is valid (S42's
// fix for #307: environments/*/*.env.json declared "host":"localhost" for a
// sqlite3 server, which ServerRef.Validate() correctly rejects - sqlite3 is
// file-based and must have an empty host), then resolves the local and prod
// environments' chinook database catalogs and asserts their real content
// (S45: environments/{local,prod}/catalogs/*/*.db.json used to hold
// {"server":{"host","driver"}}, not datatug.DbCatalogBase's actual
// {"driver","path","dbModel"} shape, so Driver/Path/DbModel silently decoded
// to "" despite the catalog ID itself resolving - the query executor could
// never actually find the SQLite file).
func TestDemoProject1_Environments(t *testing.T) {
	store := newStore(t)
	ctx := context.Background()

	envs, err := store.LoadEnvironments(ctx)
	require.NoError(t, err)

	wantEnvIDs := []string{"dev", "local", "prod", "QA", "UAT"}
	assert.ElementsMatch(t, wantEnvIDs, envs.IDs())

	for _, env := range envs {
		t.Run(env.ID, func(t *testing.T) {
			if env.ID == "QA" || env.ID == "UAT" {
				// Their PostgreSQL editions are visible in the connection catalogue,
				// but no public query endpoint is configured yet.
				assert.Empty(t, env.DbServers)
			} else {
				require.NotEmpty(t, env.DbServers, "environment %s has no dbServers", env.ID)
			}
			for i, server := range env.DbServers {
				assert.NoError(t, server.ServerRef.Validate(), "dbServers[%d].ServerRef in environment %s", i, env.ID)
			}
			assert.NoError(t, env.Validate(), "environment %s", env.ID)
		})
	}

	catalogs, err := store.LoadEnvDbCatalogs(ctx, "local")
	require.NoError(t, err)
	require.Contains(t, catalogs.IDs(), "chinook-local",
		"the local environment must resolve its chinook-local database catalog")

	// S45: environments/local/catalogs/chinook-local/chinook-local.db.json
	// used to hold {"server":{"host":"localhost","driver":"sqlite3"}} - not
	// datatug.DbCatalogBase's real shape ({"driver","path","dbModel"}), so
	// every field below silently decoded to its zero value despite the
	// catalog ID itself resolving fine (SetID comes from the directory name,
	// not the JSON content). Assert the fields a query executor actually
	// needs to open the SQLite file are populated.
	var chinookLocal *datatug.DbCatalog
	for _, c := range catalogs {
		if c.ID == "chinook-local" {
			chinookLocal = c
			break
		}
	}
	require.NotNil(t, chinookLocal)
	assert.Equal(t, "sqlite3", chinookLocal.Driver)
	assert.Equal(t, "~/datatug/dbs/chinook-local.sqlite", chinookLocal.Path)
	assert.Equal(t, "chinook", chinookLocal.DbModel)

	prodCatalogs, err := store.LoadEnvDbCatalogs(ctx, "prod")
	require.NoError(t, err)
	var chinookProd *datatug.DbCatalog
	for _, c := range prodCatalogs {
		if c.ID == "chinook-prod" {
			chinookProd = c
			break
		}
	}
	require.NotNil(t, chinookProd, "the prod environment must resolve its chinook-prod database catalog")
	assert.Equal(t, "sqlite3", chinookProd.Driver)
	assert.Equal(t, "~/datatug/dbs/chinook-prod.sqlite", chinookProd.Path)
	assert.Equal(t, "chinook", chinookProd.DbModel)
}

// TestDemoProject1_QueriesLoad checks representative query types and saved
// bodies after LoadProject populates Project.Queries directly.
func TestDemoProject1_QueriesLoad(t *testing.T) {
	store := newStore(t)
	project, err := store.LoadProject(context.Background())
	require.NoError(t, err, "failed to load %s", projectDir)

	require.NotNil(t, project.Queries)
	var findQuery func(folder *datatug.QueriesFolder, id string) *datatug.QueryDef
	findQuery = func(folder *datatug.QueriesFolder, id string) *datatug.QueryDef {
		for _, item := range folder.Items {
			if item.ID == id {
				return item
			}
		}
		for _, sub := range folder.Folders {
			if q := findQuery(sub, id); q != nil {
				return q
			}
		}
		return nil
	}

	wantTypes := map[string]datatug.QueryType{
		"customer-invoices":           datatug.QueryTypeDTQL,
		"customer-purchases-by-genre": datatug.QueryTypeSQL,
		"invoice-lines":               datatug.QueryTypeSQL,
		"country-facts":               datatug.QueryTypeHTTP,
		"currency-rate":               datatug.QueryTypeHTTP,
	}
	for id, wantType := range wantTypes {
		q := findQuery(project.Queries, id)
		require.NotNil(t, q, "query %s not found in Project.Queries", id)
		assert.Equal(t, wantType, q.Type, "query %s type", id)
		assert.NotEmpty(t, q.Text, "query %s text", id)
	}

	assert.NoError(t, project.Validate())
}

// TestDemoProject1_HostedCustomerPreview pins the browser-federated starter
// query's source, projected columns, and bounded result count. It loads both
// files through the same filestore used for saved project queries.
func TestDemoProject1_HostedCustomerPreview(t *testing.T) {
	query, err := newStore(t).LoadQuery(context.Background(), "hosted/chinook-customer-preview")
	require.NoError(t, err)
	require.Equal(t, datatug.QueryTypeDTQL, query.Type)
	require.NotNil(t, query.Federation)
	assert.Equal(t, "https://demodb.dev/ovdb", query.Federation.OVDBBaseURL)
	require.Len(t, query.Federation.Tables, 1)
	assert.Equal(t, datatug.QueryFederationTable{
		Database: "chinook",
		Name:     "Customer",
		Fields:   []string{"CustomerId", "FirstName", "LastName", "Country"},
	}, query.Federation.Tables[0])
	assert.Contains(t, query.Text, "limit: 20")
	for _, field := range []string{"CustomerId", "FirstName", "LastName", "Country"} {
		assert.Contains(t, query.Text, field)
	}
}

// TestDemoProject1_StandaloneChinookBrowserBindings keeps the browser-ready
// SQL allowlist limited to reviewed standalone SQLite examples. The separate
// Northwind DTQL bindings name public OVDB sources; they do not claim that
// the DataTug app can execute or compose them yet.
func TestDemoProject1_StandaloneChinookBrowserBindings(t *testing.T) {
	allowed := map[string]string{
		"demodb/northwind-orders-browser-sqlite":         "northwind-sqlite",
		"demodb/northwind-country-counts-browser-sqlite": "northwind-sqlite",
		"demodb/chinook-billing-browser-sqlite":          "chinook-sqlite",
		"demodb/chinook-customer-inventory":              "chinook-sqlite",
		"demodb/chinook-customer-genre-mix":              "chinook-sqlite",
		"demodb/chinook-playlist-composition":            "chinook-sqlite",
		"demodb/chinook-top-customer-spend":              "chinook-sqlite",
	}
	allowedTugQL := map[string]string{
		"demodb/chinook-invoice-author":                      "chinook-sqlite",
		"demodb/chinook-customer-invoice-count":              "chinook-sqlite",
		"demodb/chinook-customer-count-cte":                  "chinook-sqlite",
		"demodb/chinook-customer-count-graph":                "chinook-sqlite",
		"demodb/chinook-customer-invoice-join":               "chinook-sqlite",
		"demodb/chinook-invoice-compare":                     "chinook-sqlite",
		"demodb/northwind-shipping-country-count-sqlite":     "northwind-sqlite",
		"demodb/northwind-shipping-country-count-postgresql": "northwind-postgresql",
		"demodb/northwind-shipping-country-race":             "northwind-postgresql",
		"demodb/northwind-orders-full-sqlite":                "northwind-sqlite",
	}
	for queryPath, connectionID := range allowed {
		metadata := readQueryMetadata(t, queryPath)
		assert.Equal(t, strings.TrimPrefix(queryPath, "demodb/"), metadata.ID, queryPath)
		assert.Equal(t, connectionID, metadata.ConnectionID, queryPath)
		assert.Equal(t, "SQL", metadata.Type, queryPath)
		assert.Contains(t, strings.ToLower(metadata.Purpose), "standalone", queryPath)
		assert.Contains(t, strings.ToLower(metadata.Purpose), "browser", queryPath)
		assert.Empty(t, metadata.Parameters, queryPath)
		assert.Empty(t, metadata.Targets, queryPath)
	}

	// Any future standalone DemoDB example stays unbound unless it is added to
	// the allowlist above.
	queryFiles, err := filepath.Glob(filepath.Join(projectDir, "queries", "demodb", "*.query.json"))
	require.NoError(t, err)
	for _, path := range queryFiles {
		data, err := os.ReadFile(path)
		require.NoError(t, err)
		var metadata queryMetadata
		require.NoError(t, json.Unmarshal(data, &metadata), path)
		if metadata.ConnectionID != "" {
			queryPath := filepath.ToSlash(filepath.Join("demodb", strings.TrimSuffix(filepath.Base(path), ".query.json")))
			if expectedConnection, ok := allowedTugQL[queryPath]; ok {
				assert.Equal(t, strings.TrimPrefix(queryPath, "demodb/"), metadata.ID, path)
				assert.Equal(t, expectedConnection, metadata.ConnectionID, path)
				assert.Equal(t, "DTQL", metadata.Type, path)
				continue
			}
			assert.Equal(t, allowed["demodb/"+strings.TrimSuffix(filepath.Base(path), ".query.json")], metadata.ConnectionID, path)
		}
	}

	for _, queryPath := range []string{
		"demodb/chinook-postgresql-artist-tracks",
		"demodb/northwind-top-customer-orders",
		"customers/customer-purchases-by-genre",
		"invoices/invoice-lines",
	} {
		assert.Empty(t, readQueryMetadata(t, queryPath).ConnectionID, queryPath)
	}
}

func TestDemoProject1_NorthwindShowcaseQueriesLoadAndDeserialize(t *testing.T) {
	for _, tc := range []struct {
		id, connectionID string
	}{
		{"northwind-shipping-country-count-sqlite", "northwind-sqlite"},
		{"northwind-shipping-country-count-postgresql", "northwind-postgresql"},
		{"northwind-shipping-country-race", "northwind-postgresql"},
		{"northwind-orders-full-sqlite", "northwind-sqlite"},
	} {
		t.Run(tc.id, func(t *testing.T) {
			metadata := readQueryMetadata(t, "demodb/"+tc.id)
			assert.Equal(t, tc.id, metadata.ID)
			assert.Equal(t, tc.connectionID, metadata.ConnectionID)
			query := loadQueries(t, newStore(t), "demodb/"+tc.id)[0]
			require.Equal(t, datatug.QueryTypeDTQL, query.Type)
			_, err := dtql.Deserialize([]byte(query.Text))
			require.NoError(t, err, "saved structured DTQL must deserialize")
		})
	}
}

func TestDemoProject1_ChinookCustomerInvoiceJoinStarter(t *testing.T) {
	metadata := readQueryMetadata(t, "demodb/chinook-customer-invoice-join")
	assert.Equal(t, "chinook-customer-invoice-join", metadata.ID)
	assert.Equal(t, "DTQL", metadata.Type)
	assert.Equal(t, "chinook-sqlite", metadata.ConnectionID)
	assert.Contains(t, strings.ToLower(metadata.Purpose), "browser")
	require.Len(t, metadata.RelationshipBindings, 1)
	assert.Equal(t, "FK_Invoice_Customer_CustomerId", metadata.RelationshipBindings[0].ID)
	assert.Equal(t,
		"7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15:main.Invoice.CustomerId:INTEGER->main.Customer.CustomerId:INTEGER:PRIMARY_KEY:v1",
		metadata.RelationshipBindings[0].Version,
	)
	assert.Equal(t, "main", metadata.RelationshipBindings[0].From.Schema)
	assert.Equal(t, "Invoice", metadata.RelationshipBindings[0].From.Table)
	assert.Equal(t, "main", metadata.RelationshipBindings[0].To.Schema)
	assert.Equal(t, "Customer", metadata.RelationshipBindings[0].To.Table)
	require.Len(t, metadata.RelationshipBindings[0].Pairs, 1)
	assert.Equal(t, "CustomerId", metadata.RelationshipBindings[0].Pairs[0].FromField)
	assert.Equal(t, "CustomerId", metadata.RelationshipBindings[0].Pairs[0].ToField)

	source, err := os.ReadFile(filepath.Join(projectDir, "queries", "demodb", "chinook-customer-invoice-join.query.dtql"))
	require.NoError(t, err)
	text := string(source)
	for _, expected := range []string{
		"@CustomerId integer required",
		"from Invoice as i",
		"join Customer as c",
		"on i.CustomerId = c.CustomerId",
		"where i.CustomerId = @CustomerId",
		"order by i.InvoiceId",
		"limit 100",
		"select i.InvoiceId as InvoiceId, i.CustomerId as CustomerId, c.FirstName as FirstName, c.LastName as LastName, c.Email as Email",
	} {
		assert.Contains(t, text, expected)
	}
	assert.NotContains(t, text, "InvoiceDate")
	assert.NotContains(t, text, "Total")

	data, err := os.ReadFile(filepath.Join(projectDir, "queries", "demodb", "chinook-customer-invoice-join.query.json"))
	require.NoError(t, err)
	var definition struct {
		Parameters []struct {
			ID         string `json:"id"`
			Type       string `json:"type"`
			IsRequired bool   `json:"isRequired"`
			Meta       struct {
				Entity string `json:"entity"`
				Field  string `json:"field"`
			} `json:"meta"`
		} `json:"parameters"`
		Recordsets []struct {
			Columns []struct {
				Name string `json:"name"`
				Type string `json:"type"`
				Meta struct {
					Entity string `json:"entity"`
					Field  string `json:"field"`
				} `json:"meta"`
			} `json:"columns"`
		} `json:"recordsets"`
	}
	require.NoError(t, json.Unmarshal(data, &definition))
	require.Len(t, definition.Parameters, 1)
	assert.Equal(t, "CustomerId", definition.Parameters[0].ID)
	assert.Equal(t, "integer", definition.Parameters[0].Type)
	assert.True(t, definition.Parameters[0].IsRequired)
	assert.Equal(t, "Customer", definition.Parameters[0].Meta.Entity)
	assert.Equal(t, "ID", definition.Parameters[0].Meta.Field)
	require.Len(t, definition.Recordsets, 1)
	require.Len(t, definition.Recordsets[0].Columns, 5)
	wantColumns := []struct {
		name, typ, entity, field string
	}{
		{"InvoiceId", "integer", "Invoice", "ID"},
		{"CustomerId", "integer", "Customer", "ID"},
		{"FirstName", "string", "Customer", "FirstName"},
		{"LastName", "string", "Customer", "LastName"},
		{"Email", "string", "Customer", "Email"},
	}
	for i, want := range wantColumns {
		got := definition.Recordsets[0].Columns[i]
		assert.Equal(t, want.name, got.Name)
		assert.Equal(t, want.typ, got.Type)
		assert.Equal(t, want.entity, got.Meta.Entity)
		assert.Equal(t, want.field, got.Meta.Field)
	}
}

func TestDemoProject1_ChinookInvoiceCompareStarterResolves(t *testing.T) {
	const queryID = "chinook-invoice-compare"
	const fixtureSchemaVersion = "7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15"
	metadata := readQueryMetadata(t, "demodb/"+queryID)
	assert.Equal(t, queryID, metadata.ID)
	assert.Equal(t, "Chinook Invoice Comparison", metadata.Title)
	assert.Equal(t, "DTQL", metadata.Type)
	assert.Equal(t, "chinook-sqlite", metadata.ConnectionID)
	assert.Contains(t, strings.ToLower(metadata.Purpose), "synthetic candidate")
	assert.Contains(t, strings.ToLower(metadata.Purpose), "page-memory")
	require.Len(t, metadata.RelationshipBindings, 1)
	relationship := metadata.RelationshipBindings[0]
	assert.Equal(t, "FK_Invoice_Customer_CustomerId", relationship.ID)
	assert.Equal(t, fixtureSchemaVersion+":main.Invoice.CustomerId:INTEGER->main.Customer.CustomerId:INTEGER:PRIMARY_KEY:v1", relationship.Version)
	assert.Equal(t, "main", relationship.From.Schema)
	assert.Equal(t, "Invoice", relationship.From.Table)
	assert.Equal(t, "main", relationship.To.Schema)
	assert.Equal(t, "Customer", relationship.To.Table)
	require.Len(t, relationship.Pairs, 1)
	assert.Equal(t, "CustomerId", relationship.Pairs[0].FromField)
	assert.Equal(t, "CustomerId", relationship.Pairs[0].ToField)

	queries := loadQueries(t, newStore(t), "demodb/"+queryID)
	require.Len(t, queries, 1)
	query := queries[0]
	assert.Equal(t, datatug.QueryTypeDTQL, query.Type)
	assert.Contains(t, query.Text, "@CustomerId integer required")
	assert.NotContains(t, strings.ToLower(query.Text), " default ", "CustomerId has no default")
	document, parseDiagnostics := dtql.ParseTugQL(query.Text)
	require.Empty(t, parseDiagnostics, "comparison starter TugQL must parse")
	require.NotNil(t, document.Tree)

	resolved, resolveDiagnostics := dtql.ResolveTugQL(document, dtql.TugQLResolveContext{
		AuthorizedSchemas: []dtql.TugQLAuthorizedSchema{{
			Database: "chinook",
			Schema:   "main",
			Version:  fixtureSchemaVersion,
			Tables: []dtql.TugQLTable{
				{Name: "Invoice", Fields: []dtql.TugQLField{
					{Name: "InvoiceId", Type: "integer", Authorized: true},
					{Name: "CustomerId", Type: "integer", Authorized: true},
					{Name: "InvoiceDate", Type: "datetime", Authorized: true},
				}},
				{Name: "Customer", Fields: []dtql.TugQLField{
					{Name: "CustomerId", Type: "integer", Authorized: true},
					{Name: "FirstName", Type: "string", Authorized: true},
				}},
			},
		}},
		Bindings: []dtql.TugQLBinding{{Name: "CustomerId", Set: true, Value: int64(1)}},
	})
	require.Empty(t, resolveDiagnostics, "comparison starter must resolve using the declared Invoice-Customer schema")
	assert.Equal(t, fixtureSchemaVersion, resolved.SchemaVersion)
	require.Len(t, resolved.Columns, 2)
	assert.Equal(t, "InvoiceId", resolved.Columns[0].Name)
	assert.Equal(t, "integer", resolved.Columns[0].Type)
	assert.Equal(t, []dtql.TugQLOutputLineage{{Source: "i", Field: "InvoiceId"}}, resolved.Columns[0].Lineage)
	assert.Equal(t, "InvoiceDate", resolved.Columns[1].Name)
	assert.Equal(t, "datetime", resolved.Columns[1].Type)
	assert.Equal(t, []dtql.TugQLOutputLineage{{Source: "i", Field: "InvoiceDate"}}, resolved.Columns[1].Lineage)

	data, err := os.ReadFile(filepath.Join(projectDir, "queries", "demodb", queryID+".query.json"))
	require.NoError(t, err)
	var definition struct {
		Parameters []struct {
			ID         string `json:"id"`
			Type       string `json:"type"`
			IsRequired bool   `json:"isRequired"`
		} `json:"parameters"`
		Recordsets []struct {
			Columns []struct {
				Name string `json:"name"`
				Type string `json:"type"`
			} `json:"columns"`
		} `json:"recordsets"`
	}
	require.NoError(t, json.Unmarshal(data, &definition))
	require.Len(t, definition.Parameters, 1)
	assert.Equal(t, "CustomerId", definition.Parameters[0].ID)
	assert.Equal(t, "integer", definition.Parameters[0].Type)
	assert.True(t, definition.Parameters[0].IsRequired)
	require.Len(t, definition.Recordsets, 1)
	require.Len(t, definition.Recordsets[0].Columns, 2)
	assert.Equal(t, "InvoiceId", definition.Recordsets[0].Columns[0].Name)
	assert.Equal(t, "integer", definition.Recordsets[0].Columns[0].Type)
	assert.Equal(t, "InvoiceDate", definition.Recordsets[0].Columns[1].Name)
	assert.Equal(t, "datetime", definition.Recordsets[0].Columns[1].Type)
}

func TestDemoProject1_ChinookInvoiceAuthorStarter(t *testing.T) {
	metadata := readQueryMetadata(t, "demodb/chinook-invoice-author")
	assert.Equal(t, "chinook-invoice-author", metadata.ID)
	assert.Equal(t, "DTQL", metadata.Type)
	assert.Equal(t, "chinook-sqlite", metadata.ConnectionID)
	assert.Empty(t, metadata.Parameters, "TugQL declares its visible typed parameter in the source")

	source, err := os.ReadFile(filepath.Join(projectDir, "queries", "demodb", "chinook-invoice-author.query.dtql"))
	require.NoError(t, err)
	assert.Contains(t, string(source), "@CustomerId integer required")
	assert.Contains(t, string(source), "where i.CustomerId = @CustomerId")
	assert.Contains(t, string(source), "select i.InvoiceId, i.InvoiceDate")
	assert.Contains(t, string(source), "limit 100")
	assert.NotContains(t, string(source), "Total", "SQLite NUMERIC money values are outside this exactness profile")
}

func TestDemoProject1_ChinookCustomerInvoiceCountStarter(t *testing.T) {
	metadata := readQueryMetadata(t, "demodb/chinook-customer-invoice-count")
	assert.Equal(t, "chinook-customer-invoice-count", metadata.ID)
	assert.Equal(t, "DTQL", metadata.Type)
	assert.Equal(t, "chinook-sqlite", metadata.ConnectionID)
	assert.Empty(t, metadata.Parameters, "TugQL declares its visible typed parameter in the source")

	source, err := os.ReadFile(filepath.Join(projectDir, "queries", "demodb", "chinook-customer-invoice-count.query.dtql"))
	require.NoError(t, err)
	text := string(source)
	assert.Contains(t, text, "@CustomerId integer required")
	assert.Contains(t, text, "where i.CustomerId = @CustomerId")
	assert.Contains(t, text, "group by i.CustomerId")
	assert.Contains(t, text, "having count(*) >= 7")
	assert.Contains(t, text, "select i.CustomerId, count(*) as InvoiceCount")
	assert.Contains(t, text, "limit 100")
	assert.NotContains(t, text, "Total", "SQLite NUMERIC money values are outside this exactness profile")
}

func TestDemoProject1_ChinookCustomerCountsCTE(t *testing.T) {
	const queryID = "chinook-customer-count-cte"
	metadata := readQueryMetadata(t, "demodb/"+queryID)
	assert.Equal(t, queryID, metadata.ID)
	assert.Equal(t, "Chinook Customer Counts CTE", metadata.Title)
	assert.Equal(t, "DTQL", metadata.Type)
	assert.Equal(t, "chinook-sqlite", metadata.ConnectionID)
	assert.Empty(t, metadata.Parameters, "TugQL declares the visible typed parameter in the source")
	assert.Empty(t, metadata.RelationshipBindings, "the explicit join from a CTE export has no physical relationship binding")

	connectionData, err := os.ReadFile(filepath.Join(projectDir, "connections", "demo-db.json"))
	require.NoError(t, err)
	var catalogue struct {
		Connections []struct {
			ID             string `json:"id"`
			FixtureSHA256  string `json:"fixtureSha256"`
			BrowserFixture struct {
				URL string `json:"url"`
			} `json:"browserFixture"`
		} `json:"connections"`
	}
	require.NoError(t, json.Unmarshal(connectionData, &catalogue))
	connectionFound := false
	for i := range catalogue.Connections {
		if catalogue.Connections[i].ID == metadata.ConnectionID {
			connectionFound = true
			assert.Equal(t, "7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15", catalogue.Connections[i].FixtureSHA256)
			assert.Equal(t, "/assets/showcase/chinook.sqlite", catalogue.Connections[i].BrowserFixture.URL)
			break
		}
	}
	require.True(t, connectionFound, "saved connection must exist in the catalogue")

	store := newStore(t)
	query, err := store.LoadQuery(context.Background(), "demodb/"+queryID)
	require.NoError(t, err)
	assert.Equal(t, datatug.QueryTypeDTQL, query.Type)

	var definition struct {
		Recordsets []struct {
			Columns []struct {
				Name string          `json:"name"`
				Type string          `json:"type"`
				Meta json.RawMessage `json:"meta"`
			} `json:"columns"`
		} `json:"recordsets"`
	}
	data, err := os.ReadFile(filepath.Join(projectDir, "queries", "demodb", queryID+".query.json"))
	require.NoError(t, err)
	require.NoError(t, json.Unmarshal(data, &definition))
	require.Len(t, definition.Recordsets, 1)
	require.Len(t, definition.Recordsets[0].Columns, 5)
	wantColumns := []struct{ name, typ string }{
		{"CustomerId", "integer"},
		{"InvoiceCount", "integer"},
		{"FirstName", "string"},
		{"LastName", "string"},
		{"Email", "string"},
	}
	for i, want := range wantColumns {
		column := definition.Recordsets[0].Columns[i]
		assert.Equal(t, want.name, column.Name)
		assert.Equal(t, want.typ, column.Type)
		assert.Empty(t, column.Meta, "lineage is supplied by compiler and worker execution metadata")
	}

}

func TestDemoProject1_ChinookCustomerCountsGraphResolves(t *testing.T) {
	const queryID = "chinook-customer-count-graph"
	metadata := readQueryMetadata(t, "demodb/"+queryID)
	assert.Equal(t, queryID, metadata.ID)
	assert.Equal(t, "Chinook Customer Counts Graph", metadata.Title)
	assert.Equal(t, "DTQL", metadata.Type)
	assert.Equal(t, "chinook-sqlite", metadata.ConnectionID)
	assert.Empty(t, metadata.Parameters, "TugQL declares the visible typed parameter in the source")
	assert.Empty(t, metadata.RelationshipBindings, "the CTE-to-CTE join has no physical relationship binding")

	queries := loadQueries(t, newStore(t), "demodb/"+queryID)
	require.Len(t, queries, 1)
	query := queries[0]
	require.Equal(t, datatug.QueryTypeDTQL, query.Type)
	document, parseDiagnostics := dtql.ParseTugQL(query.Text)
	require.Empty(t, parseDiagnostics, "maintained graph TugQL must parse")
	require.NotNil(t, document.Tree)

	const fixtureSchemaVersion = "7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15"
	resolved, resolveDiagnostics := dtql.ResolveTugQL(document, dtql.TugQLResolveContext{
		AuthorizedSchemas: []dtql.TugQLAuthorizedSchema{{
			Database: "chinook",
			Schema:   "main",
			Version:  fixtureSchemaVersion,
			Tables: []dtql.TugQLTable{
				{Name: "Invoice", Fields: []dtql.TugQLField{
					{Name: "CustomerId", Type: "integer", Authorized: true},
				}},
				{Name: "Customer", Fields: []dtql.TugQLField{
					{Name: "CustomerId", Type: "integer", Authorized: true},
					{Name: "FirstName", Type: "string", Authorized: true},
					{Name: "LastName", Type: "string", Authorized: true},
					{Name: "Email", Type: "string", Authorized: true},
				}},
			},
		}},
		Bindings: []dtql.TugQLBinding{{Name: "CustomerId", Set: true, Value: int64(1)}},
	})
	require.Empty(t, resolveDiagnostics, "maintained graph must resolve against the admitted Chinook physical schema")
	assert.Equal(t, fixtureSchemaVersion, resolved.SchemaVersion)
	assert.Empty(t, resolved.Relationships, "the explicit join between derived CTE sources must not fabricate physical relationship evidence")
	require.Len(t, resolved.Columns, 5)
	wantColumns := []struct {
		name, typ string
		lineage   []dtql.TugQLOutputLineage
	}{
		{"CustomerId", "integer", []dtql.TugQLOutputLineage{{Source: "i", Field: "CustomerId"}}},
		{"InvoiceCount", "integer", nil},
		{"FirstName", "string", []dtql.TugQLOutputLineage{{Source: "c", Field: "FirstName"}}},
		{"LastName", "string", []dtql.TugQLOutputLineage{{Source: "c", Field: "LastName"}}},
		{"Email", "string", []dtql.TugQLOutputLineage{{Source: "c", Field: "Email"}}},
	}
	for i, want := range wantColumns {
		got := resolved.Columns[i]
		assert.Equal(t, want.name, got.Name)
		assert.Equal(t, want.typ, got.Type)
		assert.Equal(t, want.lineage, got.Lineage)
	}

	data, err := os.ReadFile(filepath.Join(projectDir, "queries", "demodb", queryID+".query.json"))
	require.NoError(t, err)
	var definition struct {
		Recordsets []struct {
			Columns []struct {
				Name string          `json:"name"`
				Type string          `json:"type"`
				Meta json.RawMessage `json:"meta"`
			} `json:"columns"`
		} `json:"recordsets"`
	}
	require.NoError(t, json.Unmarshal(data, &definition))
	require.Len(t, definition.Recordsets, 1)
	require.Len(t, definition.Recordsets[0].Columns, len(wantColumns))
	for i, want := range wantColumns {
		column := definition.Recordsets[0].Columns[i]
		assert.Equal(t, want.name, column.Name)
		assert.Equal(t, want.typ, column.Type)
		assert.Empty(t, column.Meta, "derived lineage belongs to compiler/worker execution metadata")
	}
}

// TestDemoProject1_DeclaredMappings asserts the mappings needed by the demo
// are present, exactly as declared.
func TestDemoProject1_DeclaredMappings(t *testing.T) {
	store := newStore(t)
	ctx := context.Background()

	loadEntity := func(id string) *datatug.Entity {
		e, err := store.LoadEntity(ctx, id)
		require.NoError(t, err, "failed to load entity %s", id)
		return e
	}
	customer := loadEntity("Customer")
	invoice := loadEntity("Invoice")
	country := loadEntity("Country")

	assert.Contains(t, fieldByID(t, customer, "ID").Mappings,
		datatug.PhysicalRef{Source: "chinook", Collection: "Customer", Column: "CustomerId"})
	assert.Contains(t, fieldByID(t, customer, "ID").Mappings,
		datatug.PhysicalRef{Source: "support-notes", Collection: "support-notes", Column: "CustomerId"})
	assert.Contains(t, fieldByID(t, customer, "Email").Mappings,
		datatug.PhysicalRef{Source: "chinook", Collection: "Customer", Column: "Email"})
	assert.Contains(t, fieldByID(t, invoice, "ID").Mappings,
		datatug.PhysicalRef{Source: "chinook", Collection: "Invoice", Column: "InvoiceId"})
	assert.Contains(t, fieldByID(t, country, "Name").Mappings,
		datatug.PhysicalRef{Source: "chinook", Collection: "Customer", Column: "Country"})
	assert.Contains(t, fieldByID(t, country, "Name").Mappings,
		datatug.PhysicalRef{Source: "support-notes", Collection: "support-notes", Column: "Country"})
}

// TestDemoProject1_ResolveChinookCustomerColumns runs semantic.Resolve over a
// hard-coded Chinook Customer column list, per s3b-demo-mappings.md item 3.
func TestDemoProject1_ResolveChinookCustomerColumns(t *testing.T) {
	store := newStore(t)
	entities, err := store.LoadEntities(context.Background())
	require.NoError(t, err)

	columns := []semantic.Column{
		{Name: "CustomerId", Type: "integer"},
		{Name: "Country", Type: "string"},
		{Name: "Email", Type: "string"},
		{Name: "FirstName", Type: "string"},
		{Name: "LastName", Type: "string"},
		{Name: "Phone", Type: "string"}, // no mapping, no pattern -> absent
	}
	got := semantic.Resolve(entities, "chinook", "Customer", columns)

	byColumn := make(map[string]semantic.Resolution, len(got))
	for _, r := range got {
		byColumn[r.Column] = r
	}

	assertDeclared := func(column, entity, field string) {
		r, ok := byColumn[column]
		require.True(t, ok, "expected a resolution for column %q", column)
		assert.Equal(t, entity, r.Entity, "column %q entity", column)
		assert.Equal(t, field, r.Field, "column %q field", column)
		assert.Equal(t, semantic.Declared, r.Provenance, "column %q provenance", column)
	}
	assertDeclared("CustomerId", "Customer", "ID")
	assertDeclared("Country", "Country", "Name")
	assertDeclared("Email", "Customer", "Email")

	assertDeclared("FirstName", "Customer", "FirstName")
	assertDeclared("LastName", "Customer", "LastName")

	_, hasPhone := byColumn["Phone"]
	assert.False(t, hasPhone, "Phone has no mapping or name pattern and must not resolve")
}

// TestDemoProject1_ApplicableQueries runs semantic.Applicable with
// Customer.ID=5, per s3b-demo-mappings.md item 3.
func TestDemoProject1_ApplicableQueries(t *testing.T) {
	store := newStore(t)
	queries := loadQueries(t, store, "customers/customer-invoices", "customers/customer-purchases-by-genre", "invoices/invoice-lines")
	customerInvoices, customerPurchasesByGenre, invoiceLines := queries[0], queries[1], queries[2]

	assert.Equal(t, datatug.QueryTypeDTQL, customerInvoices.Type, "customer-invoices must have been converted to DTQL")

	available := []semantic.SemanticValue{
		{Entity: "Customer", Field: "ID", Value: 5, Source: "chinook", Collection: "Customer", Column: "CustomerId", Provenance: semantic.Declared},
	}

	applicable, notYet := semantic.Applicable(
		[]*datatug.QueryDef{customerInvoices, customerPurchasesByGenre, invoiceLines},
		available,
	)

	applicableIDs := make([]string, len(applicable))
	for i, a := range applicable {
		applicableIDs[i] = a.Query.ID
	}
	assert.ElementsMatch(t, []string{"customer-invoices", "customer-purchases-by-genre"}, applicableIDs)

	require.Len(t, notYet, 1)
	assert.Equal(t, "invoice-lines", notYet[0].Query.ID)
	assert.Equal(t, []string{"Invoice.ID"}, notYet[0].Missing)
}
