package tests

import (
	"bytes"
	"encoding/json"
	"os"
	"testing"

	"github.com/datatug/datatug-core/pkg/datatug"
)

// This exercises the existing tagged Core's opaque ProjectFile metadata path.
// It proves serializer preservation, not every older provider's write safety.
func TestDataModelsMetadataProjectFileRoundTrip(t *testing.T) {
	body, err := os.ReadFile("../demo-project-1/datatug-project.json")
	if err != nil {
		t.Fatal(err)
	}
	var before map[string]json.RawMessage
	if err = json.Unmarshal(body, &before); err != nil {
		t.Fatal(err)
	}
	if len(before["dataModels"]) == 0 {
		t.Fatal("missing dataModels")
	}
	var project datatug.ProjectFile
	if err = json.Unmarshal(body, &project); err != nil {
		t.Fatal(err)
	}
	encoded, err := json.Marshal(project)
	if err != nil {
		t.Fatal(err)
	}
	var after map[string]json.RawMessage
	if err = json.Unmarshal(encoded, &after); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"dataModels", "dbModels", "connectionCatalog"} {
		var a, b bytes.Buffer
		if err = json.Compact(&a, before[key]); err != nil {
			t.Fatal(err)
		}
		if err = json.Compact(&b, after[key]); err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(a.Bytes(), b.Bytes()) {
			t.Fatalf("%s changed: %s", key, b.Bytes())
		}
	}
}
