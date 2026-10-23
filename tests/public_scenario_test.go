package tests

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	detective "github.com/datatug/datatug-core/pkg/detective"
	"github.com/stretchr/testify/require"
)

// Every published Scenario must pass the same Core definition validator used
// by Detective and lead to definitions that a visitor can actually open.
func TestPublicScenariosReferencePublishedDemoDefinitions(t *testing.T) {
	files, err := filepath.Glob(filepath.Join(projectDir, "scenarios", "*.json"))
	require.NoError(t, err)
	require.NotEmpty(t, files, "the public Detective catalog needs a Scenario")
	store := newStore(t)
	for _, path := range files {
		t.Run(filepath.Base(path), func(t *testing.T) {
			data, err := os.ReadFile(path)
			require.NoError(t, err)
			var scenario detective.Scenario
			require.NoError(t, json.Unmarshal(data, &scenario))
			require.Equal(t, strings.TrimSuffix(filepath.Base(path), ".json"), scenario.ID)
			require.NoError(t, detective.ValidateScenario(scenario))
			require.Empty(t, scenario.Inputs, "public browser guide has no input collection")
			for _, step := range scenario.Steps {
				switch step.Kind {
				case "query":
					query, err := store.LoadQuery(context.Background(), step.Ref)
					require.NoError(t, err, "Scenario query %q", step.Ref)
					require.NotNil(t, query)
				case "check":
					checkPath := filepath.Join(projectDir, "checks", step.Ref+".json")
					checkData, err := os.ReadFile(checkPath)
					require.NoError(t, err, "Scenario Check %q", step.Ref)
					var check detective.Check
					require.NoError(t, json.Unmarshal(checkData, &check))
					require.Equal(t, step.Ref, check.ID)
				default:
					t.Fatalf("Core admitted unsupported Scenario step kind %q", step.Kind)
				}
			}
		})
	}
}
