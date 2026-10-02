package tests

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"testing"

	"github.com/datatug/datatug-cli/pkg/secureread"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	_ "modernc.org/sqlite"
)

// The hero question - "Which countries buy the most music relative to their
// population?" - is the saved DTQL query sales/chinook-sales-per-capita. It
// joins three sources (Chinook Invoice -> geo country_aliases -> geo
// population_wb) with no AI involved, so its result is a pure function of the
// committed geo snapshot (demo-project-1/data/geo) and the pinned Chinook file.
//
// World Bank SP.POP.TOTL, latest year per country, fetched 2026-10-02
// (source last updated 2026-07-13). Re-pin these values when data/geo is
// refreshed with scripts/sync-geo-data.sh. They only pin the snapshot itself
// (TestGeoSnapshotPinned): every expectation about the query result is computed
// from the committed snapshot, so a refresh cannot flip a hard-coded ranking.
var pinnedPopulation = map[string]struct {
	Key        string
	Population int64
	Year       int64
}{
	"Ireland": {Key: "ie", Population: 5484367, Year: 2025},
	"USA":     {Key: "us", Population: 341784857, Year: 2025},
	"Canada":  {Key: "ca", Population: 41651653, Year: 2025},
}

const heroQueryID = "sales/chinook-sales-per-capita"

func geoSourceURL(t *testing.T) string {
	t.Helper()
	dir, err := filepath.Abs(filepath.Join(projectDir, "data", "geo"))
	require.NoError(t, err)
	return "ingitdb://" + dir
}

func number(t *testing.T, value any, field string) float64 {
	t.Helper()
	switch v := value.(type) {
	case float64:
		return v
	case int64:
		return float64(v)
	case int:
		return float64(v)
	default:
		t.Fatalf("%s has type %T", field, value)
		return 0
	}
}

// snapshotPopulation returns, for each Chinook billing-country spelling, the
// committed World Bank population of the country its alias points to: the
// expectation the saved query must reproduce, computed from data/geo itself.
func snapshotPopulation(t *testing.T) map[string]int64 {
	t.Helper()
	executor := secureread.NewExecutor(secureread.Session{Unrestricted: true})
	read := func(collection string) []map[string]any {
		result, err := executor.RunDTQL(context.Background(), geoSourceURL(t), []byte("from: {name: "+collection+"}\n"), nil)
		require.NoError(t, err)
		rows := make([]map[string]any, 0, len(result.Rows))
		for _, row := range result.Rows {
			rows = append(rows, row.Data)
		}
		return rows
	}
	populationByCountry := map[string]int64{}
	for _, row := range read("population_wb") {
		populationByCountry[row["country"].(string)] = int64(number(t, row["population"], "population"))
	}
	byAlias := map[string]int64{}
	for _, row := range read("country_aliases") {
		population, ok := populationByCountry[row["country"].(string)]
		require.True(t, ok, "alias %v has no population in the snapshot", row["alias"])
		byAlias[row["alias"].(string)] = population
	}
	return byAlias
}

// expectedPerMillion is total / population * 1e6 for every country in totals,
// with the population taken from the committed snapshot.
func expectedPerMillion(t *testing.T, totals map[string]float64) map[string]float64 {
	t.Helper()
	population := snapshotPopulation(t)
	out := make(map[string]float64, len(totals))
	for country, total := range totals {
		p, ok := population[country]
		require.True(t, ok, "%s has no alias and population in the snapshot", country)
		out[country] = total / float64(p) * 1e6
	}
	return out
}

// rankedDescending lists the countries by value, highest first.
func rankedDescending(values map[string]float64) []string {
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Slice(names, func(i, j int) bool { return values[names[i]] > values[names[j]] })
	return names
}

// heroRows runs the project's saved hero query with the given Chinook SQLite
// file and returns the rows keyed by country, in result order.
func heroRows(t *testing.T, chinookPath string) ([]string, map[string]map[string]any) {
	t.Helper()
	query, err := newStore(t).LoadQuery(context.Background(), heroQueryID)
	require.NoError(t, err)
	require.NotEmpty(t, query.Text)

	executor := secureread.NewExecutor(secureread.Session{Unrestricted: true})
	result, err := executor.RunFederatedDTQL(context.Background(), []byte(query.Text), map[string]string{
		"chinook": "sqlite://" + chinookPath,
		"geo":     geoSourceURL(t),
	}, nil)
	require.NoError(t, err)

	order := make([]string, 0, len(result.Rows))
	byCountry := make(map[string]map[string]any, len(result.Rows))
	for _, row := range result.Rows {
		country, ok := row.Data["country"].(string)
		require.True(t, ok, "country has type %T", row.Data["country"])
		order = append(order, country)
		byCountry[country] = row.Data
	}
	return order, byCountry
}

// TestGeoSnapshotPinned pins the committed reference data the hero query reads.
func TestGeoSnapshotPinned(t *testing.T) {
	executor := secureread.NewExecutor(secureread.Session{Unrestricted: true})
	run := func(t *testing.T, collection string) map[string]map[string]any {
		t.Helper()
		result, err := executor.RunDTQL(context.Background(), geoSourceURL(t), []byte("from: {name: "+collection+"}\n"), nil)
		require.NoError(t, err)
		rows := make(map[string]map[string]any, len(result.Rows))
		for _, row := range result.Rows {
			rows[row.Key] = row.Data
		}
		return rows
	}

	t.Run("population_wb", func(t *testing.T) {
		rows := run(t, "population_wb")
		assert.Len(t, rows, 216)
		for name, want := range pinnedPopulation {
			got := rows[want.Key]
			require.NotNil(t, got, name)
			assert.Equal(t, want.Population, int64(number(t, got["population"], "population")), name)
			assert.Equal(t, want.Year, int64(number(t, got["year"], "year")), name)
			assert.Equal(t, "SP.POP.TOTL", got["indicator"], name)
			assert.Equal(t, want.Key, got["country"], "FK to countries")
			assert.NotEmpty(t, got["source_url"], name)
			assert.NotEmpty(t, got["fetched_at"], name)
		}
		assert.Nil(t, rows["wld"], "World Bank aggregates must not be in the snapshot")
	})

	t.Run("country_aliases", func(t *testing.T) {
		rows := run(t, "country_aliases")
		assert.Len(t, rows, 24, "the 24 Chinook Invoice.BillingCountry values")
		for name, want := range pinnedPopulation {
			var found map[string]any
			for _, row := range rows {
				if row["alias"] == name {
					found = row
				}
			}
			require.NotNil(t, found, name)
			assert.Equal(t, want.Key, found["country"], name)
			assert.NotEmpty(t, found["source"], name)
		}
		// Spellings that differ from the GeoNames English name are manual matches.
		assert.Equal(t, "cz", rows["czech-republic"]["country"])
		assert.Equal(t, "nl", rows["netherlands"]["country"])
	})
}

// TestHeroQuery_SyntheticInvoices runs the real saved query in the ordinary
// unit suite, with invented invoices standing in for Chinook (the real file is
// not vendored; see TestHeroQuery_PinnedChinook). Population and aliases are
// the committed snapshot.
func TestHeroQuery_SyntheticInvoices(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "invoices.sqlite")
	db, err := sql.Open("sqlite", dbPath)
	require.NoError(t, err)
	_, err = db.Exec(`CREATE TABLE Invoice (id TEXT PRIMARY KEY, BillingCountry TEXT, Total REAL)`)
	require.NoError(t, err)
	seed := []struct {
		country string
		total   float64
	}{
		{"Ireland", 10}, {"Ireland", 30},
		{"USA", 100}, {"USA", 200},
		{"Canada", 60},
		{"Czech Republic", 5},
		{"Atlantis", 999}, // no alias: an inner join drops it
	}
	for i, s := range seed {
		_, err = db.Exec(`INSERT INTO Invoice (id, BillingCountry, Total) VALUES (?, ?, ?)`, fmt.Sprint(i+1), s.country, s.total)
		require.NoError(t, err)
	}
	require.NoError(t, db.Close())

	order, rows := heroRows(t, dbPath)

	assert.NotContains(t, rows, "Atlantis")
	require.Len(t, order, 4)
	want := expectedPerMillion(t, map[string]float64{
		"Ireland": 40, "USA": 300, "Canada": 60, "Czech Republic": 5,
	})
	for country, perMillion := range want {
		assert.InDelta(t, perMillion, number(t, rows[country]["salesPerMillion"], "salesPerMillion"), 1e-9, country)
	}
	assert.Equal(t, rankedDescending(want), order, "ordered by sales per million, descending")
	for i := 1; i < len(order); i++ {
		assert.GreaterOrEqual(t,
			number(t, rows[order[i-1]]["salesPerMillion"], "salesPerMillion"),
			number(t, rows[order[i]]["salesPerMillion"], "salesPerMillion"), "row %d out of order", i)
	}
}

// chinookForHeroQuery locates the pinned Chinook SQLite file and returns a copy
// with the `id` column the DALgo SQLite adapter needs (what
// scripts/prepare_chinook.py does). It skips when the file is not available,
// unless DATATUG_REQUIRE_CHINOOK is set (CI sets it), when that is a failure.
func chinookForHeroQuery(t *testing.T) string {
	t.Helper()
	src := os.Getenv("DATATUG_CHINOOK_DB")
	if src == "" {
		sibling := filepath.Join("..", "..", "chinook-database", "ChinookDatabase", "DataSources", "Chinook_Sqlite.sqlite")
		if _, err := os.Stat(sibling); err != nil {
			const need = "DATATUG_CHINOOK_DB (or a chinook-database checkout beside this repository) is required for the pinned Chinook check"
			if os.Getenv("DATATUG_REQUIRE_CHINOOK") != "" {
				t.Fatal(need + "; DATATUG_REQUIRE_CHINOOK is set, so a missing file is a failure")
			}
			t.Skip(need)
		}
		src = sibling
	}
	f, err := os.Open(src)
	require.NoError(t, err)
	raw, err := io.ReadAll(f)
	require.NoError(t, err)
	require.NoError(t, f.Close())
	require.Equal(t, loadAcceptanceFixture(t).Database.SHA256, fmt.Sprintf("%x", sha256.Sum256(raw)), "not the pinned Chinook database")

	dst := filepath.Join(t.TempDir(), "chinook.sqlite")
	require.NoError(t, os.WriteFile(dst, raw, 0o600))
	db, err := sql.Open("sqlite", dst)
	require.NoError(t, err)
	defer func() { require.NoError(t, db.Close()) }()
	_, err = db.Exec(`ALTER TABLE Invoice ADD COLUMN id TEXT`)
	require.NoError(t, err)
	_, err = db.Exec(`UPDATE Invoice SET id = CAST(InvoiceId AS TEXT)`)
	require.NoError(t, err)
	return dst
}

// TestHeroQuery_PinnedChinook is the real answer: the actual Chinook invoices
// against the committed World Bank snapshot. The expected ranking and values are
// computed from the snapshot and from the invoices (summed by SQL, independently
// of the query engine), so a World Bank refresh moves them with the data.
func TestHeroQuery_PinnedChinook(t *testing.T) {
	chinook := chinookForHeroQuery(t)
	order, rows := heroRows(t, chinook)
	require.Len(t, order, 24, "every Chinook billing country has an alias and a population")

	db, err := sql.Open("sqlite", chinook)
	require.NoError(t, err)
	defer func() { require.NoError(t, db.Close()) }()
	sums, err := db.Query(`SELECT BillingCountry, SUM(Total) FROM Invoice GROUP BY BillingCountry`)
	require.NoError(t, err)
	totals := map[string]float64{}
	for sums.Next() {
		var country string
		var total float64
		require.NoError(t, sums.Scan(&country, &total))
		totals[country] = total
	}
	require.NoError(t, sums.Err())
	require.NoError(t, sums.Close())
	require.Len(t, totals, 24)

	// Chinook Invoice.Total sums are a property of the pinned file alone.
	for country, total := range map[string]float64{"Ireland": 45.62, "USA": 523.06, "Canada": 303.96} {
		assert.InDelta(t, total, totals[country], 1e-6, country)
		assert.InDelta(t, total, number(t, rows[country]["totalSales"], "totalSales"), 1e-6, country)
	}

	// Everything that depends on the population is computed from the committed snapshot.
	population := snapshotPopulation(t)
	want := expectedPerMillion(t, totals)
	for country, perMillion := range want {
		row := rows[country]
		require.NotNil(t, row, country)
		assert.InDelta(t, totals[country], number(t, row["totalSales"], "totalSales"), 1e-6, country)
		assert.Equal(t, population[country], int64(number(t, row["population"], "population")), country)
		assert.InDelta(t, perMillion, number(t, row["salesPerMillion"], "salesPerMillion"), 1e-9, country)
	}
	for name, pinned := range pinnedPopulation {
		assert.Equal(t, pinned.Population, int64(number(t, rows[name]["population"], "population")), name)
		assert.Equal(t, pinned.Year, int64(number(t, rows[name]["populationYear"], "populationYear")), name)
	}
	assert.Equal(t, rankedDescending(want), order, "the query returns the countries ranked by sales per million, highest first")
}
