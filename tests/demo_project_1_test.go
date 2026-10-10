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

// TestDemoProject1_Validate loads demo-project-1 through the real
// filestore.LoadProject (datatug-core v0.20.0/#305 fixed entities loading
// from demo-project-1's per-entity directories; v0.21.0/#306 fixed the same
// bug class for boards and DB models, v0.22.0 makes LoadProject load each
// environment's own "<id>.env.json" and fixes #307 so a file-based sqlite3
// ServerRef with an empty host validates, and Project.Validate() has
// covered declared mappings since v0.17.0/#302) and asserts: every entity
// loads, the demo's board1 board and chinook DB model load with their real
// content, every environment loads with a validating sqlite3 ServerRef, and
// - once its three library queries are attached, the one thing LoadProject
// still doesn't populate - Project.Validate() passes.
func TestDemoProject1_Validate(t *testing.T) {
	store := newStore(t)
	project, err := store.LoadProject(context.Background())
	require.NoError(t, err, "failed to load %s", projectDir)

	wantEntityIDs := []string{"Album", "Artist", "Country", "Customer", "Invoice", "InvoiceLine", "Person", "Track"}
	assert.ElementsMatch(t, wantEntityIDs, project.Entities.IDs())

	if assert.Len(t, project.Boards, 1) {
		assert.Equal(t, "board1", project.Boards[0].ID)
		assert.Equal(t, "1st board", project.Boards[0].Title)
	}

	if assert.Len(t, project.DbModels, 1) {
		assert.Equal(t, "chinook", project.DbModels[0].ID)
	}

	wantEnvIDs := []string{"dev", "local", "prod", "QA", "UAT"}
	assert.ElementsMatch(t, wantEnvIDs, project.Environments.IDs())

	project.Queries = &datatug.QueriesFolder{
		Items: loadQueries(t, store, "customers/customer-invoices", "customers/customer-purchases-by-genre", "invoices/invoice-lines"),
	}

	assert.NoError(t, project.Validate())
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

// TestDemoProject1_QueriesLoad proves LoadProject itself (datatug-core
// v0.23.0/#309) now populates Project.Queries directly - no manual
// loadQueries patch-up needed, unlike TestDemoProject1_Validate above (still
// kept as-is; not in scope for this bump) - with all 5 real demo queries
// (DTQL customer-invoices, SQL customer-purchases-by-genre/invoice-lines,
// HTTP country-facts/currency-rate), each with its non-empty Text body, and
// that Project.Validate() passes on the project exactly as LoadProject
// returned it, with no query-loading workaround at all. None of the 5 real
// queries currently declare Targets (confirmed by direct inspection of
// demo-project-1/queries/**/*.query.json) - the empty-credential path is
// exercised separately, by construction, in datatug-core's own fixture test.
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
// SQL allowlist limited to the three standalone Chinook SQLite examples. The
// other DemoDB datasets, PostgreSQL federation example, and parameterized
// library queries remain outside that saved-connection path.
func TestDemoProject1_StandaloneChinookBrowserBindings(t *testing.T) {
	allowed := map[string]string{
		"demodb/chinook-customer-genre-mix":   "chinook-sqlite",
		"demodb/chinook-playlist-composition": "chinook-sqlite",
		"demodb/chinook-top-customer-spend":   "chinook-sqlite",
	}
	allowedTugQL := map[string]string{
		"chinook-invoice-author":         "chinook-sqlite",
		"chinook-customer-invoice-count": "chinook-sqlite",
		"chinook-customer-invoice-join":  "chinook-sqlite",
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
			if expectedConnection, ok := allowedTugQL[metadata.ID]; ok {
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
		{Name: "FirstName", Type: "string"}, // no mapping, no pattern -> absent
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

	_, hasFirstName := byColumn["FirstName"]
	assert.False(t, hasFirstName, "FirstName has no mapping or name pattern and must not resolve")
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
