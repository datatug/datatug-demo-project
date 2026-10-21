package tests

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
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
	wantIDs := []string{"customer", "invoice", "invoice-line", "country", "customer-id", "invoice-id", "customer-country", "invoice-total", "unit-price", "quantity"}
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
		case "customer-id", "invoice-id":
			require.Empty(t, concept.Extends, "project identifiers have no invented shared definition")
		case "country":
			require.Equal(t, "meaning://github.com/meaninggraph/core/country?ref=982916d73f0a35ff2558b0062f58aa3ac4f24d97", concept.Extends)
		default:
			require.Equal(t, "meaning://github.com/demo-db/chinook/"+concept.ID+"?ref=3e7bb316d8a438eb7e5930067997a4e4543a275c", concept.Extends)
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
	require.Len(t, uses.Bindings, 8)
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
	require.Equal(t, map[string]int{"customers/customer-invoices": 3, "invoices/invoice-lines": 3, "demodb/chinook-top-customer-spend": 2}, queryCounts)
}
