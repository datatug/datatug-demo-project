package tests

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/require"
	"gopkg.in/yaml.v3"
)

func TestNativeDemoMeaningsAndExactSavedQueryUses(t *testing.T) {
	var graph struct {
		Format, ID, Name, Description, License string
		Concepts                               []struct {
			ID, Kind, Of, Extends, Description string
			Labels                             map[string]string
		}
	}
	data, err := os.ReadFile("../demo.meaning.yaml")
	require.NoError(t, err)
	decoder := yaml.NewDecoder(bytes.NewReader(data))
	decoder.KnownFields(true)
	require.NoError(t, decoder.Decode(&graph))
	require.Equal(t, "meaning/draft-1", graph.Format)
	require.Equal(t, "CC0-1.0", graph.License)
	require.NotEmpty(t, graph.Name)
	require.NotEmpty(t, graph.Description)
	wantIDs := []string{"customer", "chinook-customer", "invoice", "invoice-line", "country", "customer-id", "chinook-customer-id", "invoice-id", "chinook-customer-country", "invoice-total", "unit-price", "quantity"}
	conceptKinds := make(map[string]string, len(graph.Concepts))
	var actualIDs []string
	for _, concept := range graph.Concepts {
		require.NotContains(t, conceptKinds, concept.ID)
		conceptKinds[concept.ID] = concept.Kind
		actualIDs = append(actualIDs, concept.ID)
		require.NotEmpty(t, concept.Labels["en"])
		require.NotEmpty(t, concept.Description)
	}
	require.ElementsMatch(t, wantIDs, actualIDs)
	for _, concept := range graph.Concepts {
		if concept.Of != "" {
			require.Equal(t, "entity", conceptKinds[concept.Of])
		}
		switch concept.ID {
		case "customer-id", "chinook-customer-id", "invoice-id":
			require.Empty(t, concept.Extends, "project identifiers have no invented shared definition")
		case "country":
			require.Equal(t, "meaning://github.com/meaninggraph/core/country?ref=982916d73f0a35ff2558b0062f58aa3ac4f24d97", concept.Extends)
		case "customer":
			// The demo story's customer is Northwind's (Bottom-Dollar Markets, BOTTM).
			require.Equal(t, "meaning://github.com/demo-db/northwind/customer?ref=f5855699eafaba6f09b7f4897abdb2a304698b67", concept.Extends)
		default:
			require.Equal(t, "meaning://github.com/demo-db/chinook/"+strings.TrimPrefix(concept.ID, "chinook-")+"?ref=3e7bb316d8a438eb7e5930067997a4e4543a275c", concept.Extends)
		}
	}
	var uses struct {
		Version  int `json:"version"`
		Bindings []struct {
			Query, QueryHash, Meaning string
			Parameter                 string
			Column                    *struct {
				Recordset int
				Name      string
			}
		}
	}
	data, err = os.ReadFile(filepath.Join(projectDir, "datatug-meaning-uses.json"))
	require.NoError(t, err)
	jsonDecoder := json.NewDecoder(bytes.NewReader(data))
	jsonDecoder.DisallowUnknownFields()
	require.NoError(t, jsonDecoder.Decode(&uses))
	require.Equal(t, 1, uses.Version)
	require.Len(t, uses.Bindings, 10)
	queryCounts := map[string]int{}
	for _, binding := range uses.Bindings {
		t.Run(binding.Query+"/"+binding.Meaning, func(t *testing.T) {
			require.Contains(t, conceptKinds, binding.Meaning)
			require.NotEqual(t, binding.Parameter != "", binding.Column != nil, "one exact target per binding")
			var query struct {
				Type, ConnectionID string
				Federation         json.RawMessage
				Parameters         []struct{ ID string }
				Recordsets         []struct{ Columns []struct{ Name string } }
			}
			path := filepath.Join(projectDir, "queries", binding.Query+".query")
			data, err := os.ReadFile(path + ".json")
			require.NoError(t, err)
			require.NoError(t, json.Unmarshal(data, &query))
			body, err := os.ReadFile(path + "." + strings.ToLower(query.Type))
			require.NoError(t, err)
			// Same tuple and exact sidecar bytes as semanticQueryHash. Encode
			// without Go's optional HTML escapes to match JSON.stringify.
			queryHash := func(text, connection string) string {
				var encoded bytes.Buffer
				encoder := json.NewEncoder(&encoded)
				encoder.SetEscapeHTML(false)
				require.NoError(t, encoder.Encode([]any{query.Type, text, connection, query.Federation}))
				digest := sha256.Sum256(bytes.TrimSuffix(encoded.Bytes(), []byte("\n")))
				return hex.EncodeToString(digest[:])
			}
			require.Equal(t, queryHash(string(body), query.ConnectionID), binding.QueryHash, "refresh an explicit use when its executable query changes")
			require.NotEqual(t, queryHash(string(body)+"\n", query.ConnectionID), binding.QueryHash)
			require.NotEqual(t, queryHash(string(body), query.ConnectionID+"-changed"), binding.QueryHash)
			if binding.Parameter != "" {
				var ids []string
				for _, parameter := range query.Parameters {
					ids = append(ids, parameter.ID)
				}
				require.Contains(t, ids, binding.Parameter)
			} else {
				require.GreaterOrEqual(t, binding.Column.Recordset, 0)
				require.Less(t, binding.Column.Recordset, len(query.Recordsets))
				var names []string
				for _, column := range query.Recordsets[binding.Column.Recordset].Columns {
					names = append(names, column.Name)
				}
				require.Contains(t, names, binding.Column.Name)
			}
		})
		queryCounts[binding.Query]++
	}
	require.Equal(t, map[string]int{"customers/customer-invoices": 3, "invoices/invoice-lines": 3, "demodb/chinook-top-customer-spend": 2, "northwind/customer-by-id": 1, "northwind/orders-by-customer": 1}, queryCounts)
}

func TestAllSavedQueryLegacyMeaningReferencesResolve(t *testing.T) {
	ctx := context.Background()
	store := newStore(t)
	project, err := store.LoadProject(ctx)
	require.NoError(t, err)
	definitions := map[string]map[string]bool{}
	for _, entity := range project.Entities {
		fields := map[string]bool{}
		for _, field := range entity.Fields {
			fields[field.ID] = true
		}
		definitions[entity.ID] = fields
	}
	var files []string
	err = filepath.WalkDir(filepath.Join(projectDir, "queries"), func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !entry.IsDir() && strings.HasSuffix(path, ".json") {
			files = append(files, path)
		}
		return nil
	})
	require.NoError(t, err)
	require.NotEmpty(t, files)
	require.LessOrEqual(t, len(files), 1000)
	references := 0
	for _, path := range files {
		data, err := os.ReadFile(path)
		require.NoError(t, err)
		require.LessOrEqual(t, len(data), 1<<20)
		var document any
		require.NoError(t, json.Unmarshal(data, &document), path)
		var visit func(any)
		visit = func(value any) {
			switch value := value.(type) {
			case map[string]any:
				if meta, ok := value["meta"].(map[string]any); ok && (meta["entity"] != nil || meta["field"] != nil) {
					references++
					entity, entityOK := meta["entity"].(string)
					field, fieldOK := meta["field"].(string)
					if !entityOK || !fieldOK || entity == "" || field == "" || !definitions[entity][field] {
						t.Errorf("%s has unresolved legacy meaning %v.%v", path, meta["entity"], meta["field"])
					}
				}
				for _, child := range value {
					visit(child)
				}
			case []any:
				for _, child := range value {
					visit(child)
				}
			}
		}
		visit(document)
	}
	require.Positive(t, references, "the scan must exercise declared query references")
	for _, expected := range []struct{ Entity, Field, Type, Collection string }{
		{"ChinookCustomer", "FirstName", "string", "Customer"},
		{"ChinookCustomer", "LastName", "string", "Customer"},
		{"Invoice", "InvoiceDate", "datetime", "Invoice"},
	} {
		entity, err := store.LoadEntity(ctx, expected.Entity)
		require.NoError(t, err)
		field := fieldByID(t, entity, expected.Field)
		require.Equal(t, expected.Type, field.Type)
		require.Len(t, field.Mappings, 1)
		require.Equal(t, "chinook", field.Mappings[0].Source)
		require.Equal(t, expected.Collection, field.Mappings[0].Collection)
		require.Equal(t, expected.Field, field.Mappings[0].Column)
	}
}
