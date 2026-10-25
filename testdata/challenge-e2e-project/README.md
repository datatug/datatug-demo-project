# QA challenge end-to-end fixture project

This is a **QA-only** DataTug project. It exists to verify the approved challenge
execution contract end to end without changing the public demo.

- It is not listed in `.datatug.yaml`, the public `demo-project-1` project, the
  README catalogue or any featured/board list.
- It is fixture-only. No connection, credential or network source is needed.
- Every challenge is a normal project asset at
  `challenges/<challengeId>/1.json`, and every fixture is at the normal
  `challenges/<challengeId>/fixtures/<fixtureId>.db` path.
- The manifests pin the approved browser engine
  `@sqlite.org/sqlite-wasm` `3.54.1-build1` (SQLite `3.54.1`).

## Coverage

| Challenge | `timing` | Required parts |
|---|---|---|
| `qa-timing-off-select1` | `off` | one `sql` part, oracle `1` |
| `qa-timing-required-select1` | `required` | one `sql` part, oracle `1` |
| `qa-timing-optional-shared-sql` | `optional` | two independent `sql` parts on the same fixture: `value-one` expects `1`, `value-two` expects `2` |
| `qa-mixed-answer-kinds` | `required` | `sql` + closed `structured` + `check-definition` |

The optional challenge proves that one shared SQL answer cannot pass both
required parts: `SELECT 1 AS value` passes `value-one` and fails `value-two`,
and the reverse holds for `SELECT 2 AS value`.

The mixed challenge has two distinct fixtures:

| Fixture | Purpose | Check outcome |
|---|---|---|
| `broken` | byte-for-byte copy of `basic.db` from the public delete-duplicates suite | `fail` |
| `repaired` | byte-for-byte copy of `no-duplicates.db` from the public delete-duplicates suite | `pass` |

The Check part offers two saved training queries:

- `queries/check/duplicate-emails` returns one row per exact duplicate email; it
  produces `fail` on `broken` and `pass` on `repaired`.
- `queries/check/always-empty` is the negative control. It returns zero rows on
  both fixtures, so it passes `repaired` but cannot satisfy the required
  `fail` outcome on `broken`.

The learner must author the typed expectation, not inherit it from the query:

```json
{
  "id": "no-duplicate-emails",
  "scope": "set",
  "kind": "row-count",
  "severity": "critical",
  "expected": {"type": "integer", "value": "0"}
}
```

A wrong expectation (for example `expected` integer `1`) or a missing
expectation does not pass. A correct SQL answer with a wrong or missing required
structured or Check answer leaves the attempt incomplete.

## Valid and wrong answers

Valid mixed answer set:

- SQL: group `customers` by `email` and return groups with more than one row.
- Structured: `root-cause=duplicate-email-rows`,
  `remediation=deduplicate-then-constrain`.
- Check: `queryId=check/duplicate-emails` plus the typed expectation above.

Wrong examples exercised by verification:

- SQL `SELECT 2 AS value` fails the mixed SQL oracle.
- Structured `root-cause=missing-unique-index` fails the closed selection.
- Omitting the structured answer leaves `GradeAttempt` without a required part
  outcome and is refused.
- `queryId=check/always-empty` fails the broken Check case.
- A Check expectation with integer `1`, or no expectation at all, does not pass.

## Fixtures, hashes and determinism

The fixtures reuse the committed synthetic delete-duplicates bytes unchanged.
No public fixture is edited.

| Copied fixture | Source | SHA-256 | Bytes |
|---|---|---|---|
| `basic` / `broken` | `demo-project-1/challenges/delete-duplicates/fixtures/basic.db` | `74b2eb32b7f91a528e30d145eb253ad778e03517523a789a39308df2e3dae93c` | 12288 |
| `no-duplicates` / `repaired` | `demo-project-1/challenges/delete-duplicates/fixtures/no-duplicates.db` | `eac560957d32da9bc3dfee7074d0df004d6d9ffe73bce1e263a0324915746f56` | 12288 |

The public revision `demo-project-1/challenges/delete-duplicates/1.json` must
keep SHA-256
`6d533e46569eddde4566f0215e20e548bf8c744da3bbfb86518a6a197bb89ebb`, and all
nine public fixture files must keep their hashes. Verification checks both.

Generated assets are deterministic: two in-memory authoring builds must produce
identical bytes, and verification compares every committed byte with the
recomputed output. Regeneration is explicit:

```sh
# Trusted normal check; never rewrites fixtures or manifests.
python3 scripts/challenge-e2e-fixtures.py verify --require-core

# Focused unit tests.
python3 -m unittest discover -s tests -p 'test_challenge_e2e_fixtures.py' -v

# Explicit writer, only after an intentional asset change.
python3 scripts/challenge-e2e-fixtures.py regenerate
```

## Verification boundaries

`verify --require-core` opens every new manifest with the real
`pkg/challenge` `Open`/`LoadManifest` from a sibling `datatug-core` worktree,
checks `AssetPath`, `FixtureAssetPath`, the fixture pins and the manifest
structure, and runs Core's SQL, structured, Check-definition and
`GradeAttempt` grading functions through a temporary Go helper outside this Git
repository.

The reference rows and Check outcome matrix are executed with Python's native
`sqlite3` module on read-only in-memory copies of the committed bytes. That is a
fixture-authority check, not the browser runtime. It does **not** claim
Chromium, Firefox or WebKit acceptance, guided UI timing, worker isolation or
WASM behaviour. Task 4 must run the actual built WASM runtime for that.
