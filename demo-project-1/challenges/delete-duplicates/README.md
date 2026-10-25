# Delete duplicates challenge

This folder holds both the internal fixture-suite index and the public revision
1 manifest for the standalone delete-duplicates exercise.

- `1.json` is the immutable public revision at the declaring project's generic
  asset path `challenges/delete-duplicates/1.json`. Its wire shape is the
  accepted Core contract at
  `github.com/datatug/datatug-core@0f250aa pkg/challenge` (`schemaVersion: 1`,
  `gradingVersion: challenge-grading-v1`). It has no latest alias, discovery
  registration or UI-specific fields.
- `suite.json` remains the internal index (`publicManifest: false`). It records
  fixture hashes/bytes, expected tables, reference/mutation receipts and the
  synthetic-data declaration. It is not a published manifest.
- `fixtures/*.sqlite` are the immutable pinned inputs. The manifest pins each
  fixture by SHA-256 and byte length, not by its conventional relative path.
  Other declaring projects may spell the same convention differently; fixture
  bytes are the identity.

The data is synthetic. No real customer record, source database, log or
production snapshot was sampled, copied or snapshotted. The invented emails,
timestamps, identifiers and unrelated records are released with this
repository's own files under CC0 1.0.

## Schema and rule

```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    email TEXT COLLATE BINARY,
    created_at TEXT NOT NULL
);

CREATE TABLE unrelated_records (
    id INTEGER PRIMARY KEY,
    code TEXT COLLATE BINARY NOT NULL,
    note TEXT NOT NULL
);
```

The retention rule is: **keep the lowest numeric `id` for each exact `email`
value**. SQLite `BINARY` equality applies, so case, leading/trailing whitespace
and inner whitespace are significant. `NULL` is one duplicate group; the empty
string is a different group. `created_at` is evidence only and is never the
retention rule. `unrelated_records` must not change.

The Python oracle groups by exact Python string equality (with `None` as its
own key) and keeps `MIN(id)`. The SQL references and every mutation are checked
against the committed expected rows, not against SQL spelling. The oracle order
is `(id, email, created_at)` ascending by `id`; unrelated rows are compared the
same way.

## Public revision manifest

`1.json` declares one required SQL part, `delete-duplicates`, with one
`final-state` case per pinned fixture. Every case compares both
`customers(id, email, created_at)` and
`unrelated_records(id, code, note)` exactly, so missing survivors, retained
duplicates and collateral writes all fail. Each case also declares the
`keep-lowest-id` `group-min` invariant over `customers.email` with `id` as the
retention column. The invariant explains a violated lowest-id rule while the
expected table remains the answer key.

Integer cells use the API contract's typed union
(`{"type":"integer","value":"2"}`), not JSON numeric cells. String and NULL
cells use the same union. Exact SQL spelling is never graded.

The manifest pins the approved browser engine
`@sqlite.org/sqlite-wasm` `3.54.1-build1` (SQLite `3.54.1`). That pin is
independent of the fixture builder's Python SQLite version recorded in
`suite.json`; committed fixture bytes remain the authority.

Hints are progressive and explicit. The single reference solution is an
assisted answer: revealing it must tag the attempt as assisted and must not by
itself award completion. The accepted Core contract permits at most one
reference answer per part, so revision 1 pins the canonical NULL-safe `EXISTS`
formulation; the grouped `MIN` and window alternatives remain verified internal
generator receipts rather than additional wire answers.

## Fixtures

There are nine small committed SQLite files: six authored fixtures and three
deterministic generated variants.

| Fixture | Purpose | Expected surviving ids |
|---|---|---|
| `fixtures/basic.sqlite` | basic duplicate pairs and one unique row | `2, 3, 5` |
| `fixtures/no-duplicates.sqlite` | no duplicate groups, including singleton `NULL` and `''` | `1, 2, 4, 6, 9` |
| `fixtures/multi-group.sqlite` | multiple groups, including groups of three and four | `2, 3, 5, 8, 25` |
| `fixtures/nonsequential-created-at.sqlite` | nonsequential ids and insertion order; earlier `created_at` on higher ids | `2, 3, 7, 41` |
| `fixtures/null-empty.sqlite` | three-member `NULL` group, three-member empty-string group, distinct `'NULL'` | `1, 2, 4, 5` |
| `fixtures/case-whitespace.sqlite` | case, leading/trailing space and inner space are distinct | `2, 3, 5, 6, 11, 12, 13, 14` |
| `fixtures/generated-variant-01.sqlite` | fixed-seed generated mix | computed in `suite.json` |
| `fixtures/generated-variant-02.sqlite` | fixed-seed generated mix | computed in `suite.json` |
| `fixtures/generated-variant-03.sqlite` | fixed-seed generated mix | computed in `suite.json` |

Every fixture has an unrelated `unrelated_records` table with rows that must
stay byte-for-byte equivalent after a submission. Generated variants use the
fixed seed `20261025`; each variant records both that base seed and its derived
variant seed. They include multiple groups, a three-plus group, `NULL`, empty
string, case/whitespace variants, nonsequential ids/insertion order and at
least one group whose earliest timestamp has a higher id.

`suite.json` is the internal fixture-suite index. It records, for every fixture:

- relative path, SHA-256 and byte length;
- insertion order, initial customer rows and expected final rows;
- expected final columns `(id, email, created_at)` with declared SQLite types;
- initial and expected unrelated rows and columns;
- purpose, properties and generator metadata.

It also records coverage, the internal reference/mutation definitions and their
per-fixture receipts, plus a synthetic-data declaration. The published manifest
must pin the fixture SHA-256/byte length and the validator semantics, not this
internal file's shape.

## Reference formulations

Three distinct correct formulations are exercised on every fixture, each applied
twice to prove idempotency:

1. `NULL`-safe `EXISTS` using `keeper.email IS customers.email COLLATE BINARY`
   and `keeper.id < customers.id`.
2. Grouped `MIN(id)` with `GROUP BY email` and `NOT IN`.
3. `ROW_NUMBER() OVER (PARTITION BY email ORDER BY id)` with rank greater than
   one.

All 27 reference checks pass and are idempotent. The full SQL is in `suite.json`
and in `scripts/delete-duplicates-fixtures.py`.

## Wrong-answer mutation matrix

Each mutation is executed on all nine fixtures. Every mutation is rejected on at
least one fixture; 63 mutation checks are recorded.

| Mutation | Detected on | Relevant invariant |
|---|---|---|
| `delete-all` | all fixtures | expected survivors missing, row count wrong |
| `keep-highest-id` | `basic` (and others) | lowest-id survivor missing, higher id retained, same row count |
| `keep-earliest-created-at` | `nonsequential-created-at` (and others) | lowest-id survivor missing, earlier-timestamp higher id retained |
| `ignore-null-group-equality` | `null-empty` | `NULL` duplicate group remains, extra rows retained |
| `case-trim-collapse` | `case-whitespace` (and generated/null fixtures) | case/whitespace survivors missing, collapsed groups wrongly deleted |
| `delete-one-duplicate` | `basic` (and others) | a duplicate group remains after deleting only one row |
| `collateral-unrelated-delete` | every fixture | correct customer rows but unrelated rows changed |

The `keep-highest-id` and `keep-earliest-created-at` cases intentionally preserve
the expected row count on the selected fixtures while returning different
contents, so a row-count-only check cannot pass them.

## Regeneration and verification

Run from the repository root:

```sh
# Trusted normal check: hashes + semantics + the checked public manifest.
# It never rewrites fixtures or the manifest.
python3 scripts/delete-duplicates-fixtures.py verify

# Focused unit tests, including the mutation matrix, manifest wire checks and
# deterministic generation.
python3 -m unittest discover -s tests -p 'test_delete_duplicates_fixtures.py' -v

# Explicit regeneration only after an intentional fixture or builder change.
# The same command rewrites suite.json and 1.json from verified fixtures.
python3 scripts/delete-duplicates-fixtures.py regenerate
```

Normal `verify` refuses a changed fixture hash and also refuses a checked
`1.json` that differs from the trusted generator's deterministic output. Editing
the manifest by hand is not a supported path: the explicit regeneration command
is the only writer. No verification run silently regenerates anything.

The suite was generated with SQLite **3.53.4** and Python **3.14.7**. SQLite
embeds its library version in the database header, so committed fixture bytes are
authoritative: ordinary verification checks the committed SHA-256 and semantic
answers and does not require byte-for-byte regeneration on another SQLite
version. Regeneration records the builder's SQLite/Python versions and tool
SHA-256 in `suite.json`. Any edit to the trusted tool requires an explicit
regeneration so its recorded tool hash stays valid.

Every solution runs through `sqlite3.Connection.backup()` into a new in-memory
database from a read-only `mode=ro&immutable=1` source connection. Tests hash the
committed files before and after the run; the source `.sqlite` files are never
opened for writing and no solution is executed against a committed file.

The Python reference/mutation harness compares final table data, column names and
typed values, not the SQLite schema text or the browser runtime. It is a trusted
generator/verification tool, never a learner SQL service, and it does not expose
an execution endpoint. Python fixture validation is also not browser acceptance:
it does not prove the guided UI, worker isolation, limits, timing or the
Chromium/Firefox/WebKit journey required by the feature specification.
