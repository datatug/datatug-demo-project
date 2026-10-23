package tests

import (
	"encoding/json"
	"io/fs"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// localOnlyOVDBQueries read the orders/countries fixtures from an OVDB server on
// the visitor's own computer (see the README's "latest 100 invoices" section).
// They are the only saved queries allowed a loopback federation.ovdbBaseUrl, and
// each says so in its purpose so the public demo can label it before a click.
var localOnlyOVDBQueries = map[string]bool{
	"sales/latest-100-invoices-country-lookup": true,
	"sales/latest-100-sales-http-lookup":       true,
	"sales/latest-100-sales-per-capita":        true,
}

// TestDemoProject1_NoLoopbackOVDBInPublicQueries keeps loopback OVDB endpoints
// out of every query a datatug.app visitor can run. Before this guard the hero
// query sales/chinook-sales-per-capita sent production visitors' browsers to
// http://127.0.0.1:50501.
func TestDemoProject1_NoLoopbackOVDBInPublicQueries(t *testing.T) {
	root := filepath.Join(projectDir, "queries")
	seen := map[string]bool{}
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil || entry.IsDir() || !strings.HasSuffix(path, ".query.json") {
			return walkErr
		}
		relative, err := filepath.Rel(root, path)
		require.NoError(t, err)
		id := filepath.ToSlash(strings.TrimSuffix(relative, ".query.json"))
		data, err := os.ReadFile(path)
		require.NoError(t, err)
		var metadata struct {
			Purpose    string `json:"purpose"`
			Federation *struct {
				OVDBBaseURL string `json:"ovdbBaseUrl"`
			} `json:"federation"`
		}
		require.NoError(t, json.Unmarshal(data, &metadata), id)
		if metadata.Federation == nil {
			return nil
		}
		base, err := url.Parse(metadata.Federation.OVDBBaseURL)
		require.NoError(t, err, id)
		loopback := base.Hostname() == "127.0.0.1" || base.Hostname() == "localhost" || base.Hostname() == "::1"
		if localOnlyOVDBQueries[id] {
			seen[id] = true
			assert.True(t, loopback, "%s is declared local-only but names %s", id, base)
			assert.Contains(t, metadata.Purpose, "Local-only demo", id)
			return nil
		}
		assert.False(t, loopback, "%s sends public visitors to a loopback OVDB server %s", id, base)
		assert.Equal(t, "https", base.Scheme, id)
		return nil
	})
	require.NoError(t, err)
	assert.Len(t, seen, len(localOnlyOVDBQueries))
}

// TestDemoProject1_LegacyChinookQueriesRunInBrowser binds the three original
// Chinook SQL queries to the pinned browser SQLite fixture, so a signed-out
// visitor runs them without a DataTug agent.
func TestDemoProject1_LegacyChinookQueriesRunInBrowser(t *testing.T) {
	for _, path := range []string{
		"albums/albums_by_title.sql.json",
		"artists/artists_with_albums.sql.json",
		"tracks/tracks_by_title.sql.json",
	} {
		data, err := os.ReadFile(filepath.Join(projectDir, "queries", path))
		require.NoError(t, err)
		var metadata struct {
			ConnectionID string `json:"connectionId"`
			Targets      []any  `json:"targets"`
			Parameters   []struct {
				IsRequired *bool `json:"isRequired"`
			} `json:"parameters"`
		}
		require.NoError(t, json.Unmarshal(data, &metadata), path)
		assert.Equal(t, "chinook-sqlite", metadata.ConnectionID, path)
		assert.Empty(t, metadata.Targets, path)
		for _, parameter := range metadata.Parameters {
			// The browser binds an omitted optional input as NULL; a required one would block Run.
			require.NotNil(t, parameter.IsRequired, path)
			assert.False(t, *parameter.IsRequired, path)
		}
	}
}
