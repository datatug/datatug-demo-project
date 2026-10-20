package tests

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"github.com/datatug/datatug-core/pkg/apicontract"
	"github.com/datatug/datatug-core/pkg/datatug"
	"github.com/datatug/datatug-core/pkg/detective"
	"github.com/datatug/datatug-core/pkg/incidents"
	"github.com/datatug/datatug-core/pkg/investigation"
	"github.com/stretchr/testify/require"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"testing"
)

type shippingCatalog struct{ root string }

func (s shippingCatalog) GetCheck(_ context.Context, id string) (detective.Check, error) {
	var c detective.Check
	b, e := os.ReadFile(filepath.Join(s.root, "checks", id+".json"))
	if e == nil {
		e = json.Unmarshal(b, &c)
	}
	return c, e
}
func (s shippingCatalog) GetPublishedValidator(context.Context, string) (detective.PublishedValidator, error) {
	return detective.PublishedValidator{}, detective.ErrNotFound
}
func (s shippingCatalog) GetQueryValidators(context.Context, string) (detective.QueryValidators, bool, error) {
	return detective.QueryValidators{}, false, nil
}
func (s shippingCatalog) QueryExists(_ context.Context, id string) (bool, error) {
	_, e := os.Stat(filepath.Join(s.root, "queries", id+".query.json"))
	if os.IsNotExist(e) {
		return false, nil
	}
	return e == nil, e
}
func TestShippingChecksExecuteRealSQLiteEvidence(t *testing.T) {
	root, e := filepath.Abs(projectDir)
	require.NoError(t, e)
	b, e := os.ReadFile(filepath.Join(root, "fixtures/shipping/base.sqlite"))
	require.NoError(t, e)
	path := filepath.Join(t.TempDir(), "shipping.sqlite")
	require.NoError(t, os.WriteFile(path, b, 0600))
	db, e := sql.Open("sqlite", path)
	require.NoError(t, e)
	defer func() {
		if err := db.Close(); err != nil {
			t.Errorf("close shipping database: %v", err)
		}
	}()

	declaration, err := os.ReadFile(filepath.Join(root, "connections/shipping.json"))
	require.NoError(t, err)
	var connections datatug.ProjectConnections
	require.NoError(t, json.Unmarshal(declaration, &connections))
	require.NoError(t, connections.Validate())
	require.False(t, connections.Connections[0].ReadyForBinding())

	ctx := context.Background()
	runner := func(ctx context.Context, id, _ string, inputs map[string]apicontract.TypedValueOrSet) (apicontract.Result, error) {
		text, e := os.ReadFile(filepath.Join(root, "queries", id+".query.sql"))
		if e != nil {
			return apicontract.Result{}, e
		}
		input := inputs["order_id"]
		if input.Scalar == nil {
			return apicontract.Result{}, fmt.Errorf("missing input")
		}
		order, e := strconv.Atoi(input.Scalar.Str)
		if e != nil {
			return apicontract.Result{}, e
		}
		rows, e := db.QueryContext(ctx, string(text), sql.Named("order_id", order))
		if e != nil {
			return apicontract.Result{}, e
		}
		defer func() {
			if err := rows.Close(); err != nil {
				t.Errorf("close shipping query rows: %v", err)
			}
		}()
		names, e := rows.Columns()
		if e != nil {
			return apicontract.Result{}, e
		}
		result := apicontract.Result{}
		for _, n := range names {
			result.Recordset.Columns = append(result.Recordset.Columns, apicontract.Column{Name: n, Type: "string"})
		}
		for rows.Next() {
			v := make([]any, len(names))
			p := make([]any, len(names))
			for i := range v {
				p[i] = &v[i]
			}
			if e := rows.Scan(p...); e != nil {
				return result, e
			}
			typed := make([]investigation.TypedValue, len(v))
			for i, x := range v {
				if x == nil {
					typed[i] = investigation.NewNullValue()
				} else {
					typed[i] = investigation.NewStringValue(fmt.Sprint(x))
				}
			}
			result.Recordset.Rows = append(result.Recordset.Rows, typed)
		}
		return result, rows.Err()
	}
	run := func(id string, order int, want string) {
		t.Helper()
		catalog, e := detective.LoadCatalog(ctx, id, "", shippingCatalog{root})
		require.NoError(t, e)
		v := investigation.NewIntegerValue(strconv.Itoa(order))
		result, e := detective.EvaluateCheck(ctx, detective.RunRequest{ID: fmt.Sprintf("run-%d", order), CheckID: id, Environment: "training", Actor: "fixture-test", Inputs: map[string]detective.InputValue{"order_id": {Scalar: &v}}}, catalog, runner, nil)
		require.NoError(t, e)
		require.Equal(t, want, result.Outcome)
	}

	// Resolve all new definitions with the actual file-store reader.
	store := newStore(t)
	for _, name := range []string{"request-receipt", "current-route", "partner-enabled", "assignment-outcome", "historical-route", "events", "timings", "readiness"} {
		query, err := store.LoadQuery(ctx, "shipping/"+name)
		require.NoError(t, err)
		require.Equal(t, "shipping-working-copy", query.ConnectionID)
		require.NotEmpty(t, query.Text)
		require.NoError(t, query.Validate())
	}
	catalog, err := detective.LoadCatalog(ctx, "shipping-request-received", "", shippingCatalog{root})
	require.NoError(t, err)
	value := investigation.NewIntegerValue("11045")
	unavailable, err := detective.EvaluateCheck(ctx, detective.RunRequest{ID: "run-unavailable", CheckID: "shipping-request-received", Environment: "training", Actor: "fixture-test", Inputs: map[string]detective.InputValue{"order_id": {Scalar: &value}}}, catalog, func(context.Context, string, string, map[string]apicontract.TypedValueOrSet) (apicontract.Result, error) {
		return apicontract.Result{}, fmt.Errorf("source unavailable")
	}, nil)
	require.NoError(t, err)
	require.NotEqual(t, "pass", unavailable.Outcome)

	// Raw SQL has no authority to mint execution IDs. Its NULL ref slots
	// must fail the actual shared ArtifactRef admission validator.
	for _, name := range []string{"events", "readiness"} {
		text, err := os.ReadFile(filepath.Join(root, "queries/shipping", name+".query.sql"))
		require.NoError(t, err)
		rows, err := db.Query("SELECT evidence_ref FROM ("+string(text)+")", sql.Named("order_id", 11045))
		require.NoError(t, err)
		count := 0
		for rows.Next() {
			var raw any
			require.NoError(t, rows.Scan(&raw))
			require.Nil(t, raw)
			wire, err := json.Marshal(raw)
			require.NoError(t, err)
			var ref incidents.ArtifactRef
			require.NoError(t, json.Unmarshal(wire, &ref))
			require.Error(t, ref.Validate(), "raw unadmitted SQL row must not become chart evidence")
			count++
		}
		require.NoError(t, rows.Err())
		require.NoError(t, rows.Close())
		require.Positive(t, count)
	}

	run("shipping-request-received", 11045, "pass")
	for _, order := range []int{90004, 90005, 99999} {
		run("shipping-request-received", order, "fail")
	}
	run("shipping-carrier-assignment", 11045, "fail")
	mutate := func(replay bool) {
		t.Helper()
		code := "import importlib.util,json,sqlite3,sys; s=importlib.util.spec_from_file_location('shipping',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); d=sqlite3.connect(sys.argv[2]); m.correct(d); "
		if replay {
			code += "m.replay(d,11045,json.loads((m.FIXTURE/'manifest.json').read_text())['logs'][1]); "
		}
		code += "d.commit(); d.close()"
		out, e := exec.Command("python3", "-c", code, filepath.Join(root, "..", "scripts/build-shipping-fixture.py"), path).CombinedOutput()
		require.NoError(t, e, string(out))
	}
	mutate(false)
	run("shipping-carrier-assignment", 11045, "fail")
	mutate(true)
	run("shipping-carrier-assignment", 11045, "pass")
	run("shipping-carrier-assignment", 11062, "fail")
	mutate(true)
	run("shipping-carrier-assignment", 11045, "pass")
	// A later effective configuration/partner invalidates the old accepted
	// assignment without changing this saved Check definition.
	_, e = db.Exec("INSERT INTO configurations VALUES(19,'2018-05-20T10:06:00Z'); INSERT INTO partners VALUES('new-partner',1); INSERT INTO routes VALUES('route-19-2',19,2,'new-partner','2018-05-20T10:06:00Z',NULL); UPDATE workspace_state SET current_config=19,business_clock='2018-05-20T10:06:00Z'")
	require.NoError(t, e)
	run("shipping-carrier-assignment", 11045, "fail")
}
