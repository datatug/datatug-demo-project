#!/usr/bin/env python3
"""Author and verify the QA challenge end-to-end fixture project.

This tool creates a dedicated, fixture-only DataTug project at
``testdata/challenge-e2e-project``. It does not touch the public
``demo-project-1`` project or the project catalogue.

The authored assets cover the approved execution contract's timing modes and
answer kinds:

* timing=off, one required read SQL part that returns integer 1;
* timing=required, the same read part;
* timing=optional, two independent required read SQL parts on one fixture,
  one expecting 1 and the other 2, so a single shared SQL cannot pass both;
* timing=required, mixed SQL + closed structured + Check-definition parts,
  with a broken/repaired fixture matrix for the Check.

Fixture bytes are byte-for-byte copies of the committed synthetic SQLite files
from ``demo-project-1/challenges/delete-duplicates/fixtures``. The copied bytes
are pinned by SHA-256 and byte length in each manifest. Manifests pin the
approved browser engine ``@sqlite.org/sqlite-wasm`` 3.54.1-build1, while the
reference execution in this tool uses Python's native SQLite module. That
distinction is deliberate and is reported separately: Python reference results
are not browser/WASM acceptance.

Usage from the repository root:

    python3 scripts/challenge-e2e-fixtures.py regenerate
    python3 scripts/challenge-e2e-fixtures.py verify --require-core

``regenerate`` is the only writer. ``verify`` never rewrites committed assets.
It recomputes every authored byte, executes the reference queries against
read-only in-memory copies, checks the original public assets, and (when a
Core worktree is available) calls the real ``pkg/challenge`` ``Open`` and
grading functions from that worktree through a temporary Go helper outside this
Git repository.

This module is also imported by ``tests/test_challenge_e2e_fixtures.py``.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "testdata/challenge-e2e-project"
SOURCE_SUITE_DIR = ROOT / "demo-project-1/challenges/delete-duplicates"

# The public revision and the nine public fixture files must remain untouched.
ORIGINAL_MANIFEST_SHA256 = (
    "6d533e46569eddde4566f0215e20e548bf8c744da3bbfb86518a6a197bb89ebb"
)
ORIGINAL_FIXTURE_SHA256 = {
    "basic": "74b2eb32b7f91a528e30d145eb253ad778e03517523a789a39308df2e3dae93c",
    "no-duplicates": "eac560957d32da9bc3dfee7074d0df004d6d9ffe73bce1e263a0324915746f56",
    "multi-group": "e831d7da684bd5be7799af17441d13449df9612dd8fef98757cee1bc76780a14",
    "nonsequential-created-at": "cb9c82521e0780c35cc36a71dfacf83711ff48611692b8c08895feba5434c9ac",
    "null-empty": "ff6390ca19f6e9a87db44da08646056199e159e5f87bfbec560f87911a560eda",
    "case-whitespace": "da7998bd59a0af4a1d2eef3d8da1ba204f37902cc9cfd63bbfa79240e95e16a0",
    "generated-variant-01": "7f733f9254fcd19a56156dc423ba50c5b4f338b0a6e8ed661e0fa772e6f62fa2",
    "generated-variant-02": "0e428ba96f95ba052fd41eae54aec1cd65a1a7561f4945b392f3440ef9ef9313",
    "generated-variant-03": "49f82c4c8ed16766eaf24571936fcbf1aadabda46f3a727fd46643b1f46ac862",
}
ORIGINAL_FIXTURE_BYTES = {fixture_id: 12288 for fixture_id in ORIGINAL_FIXTURE_SHA256}

SOURCE_FIXTURES = {
    "basic": {
        "path": "demo-project-1/challenges/delete-duplicates/fixtures/basic.db",
        "sha256": ORIGINAL_FIXTURE_SHA256["basic"],
        "bytes": ORIGINAL_FIXTURE_BYTES["basic"],
    },
    "no-duplicates": {
        "path": "demo-project-1/challenges/delete-duplicates/fixtures/no-duplicates.db",
        "sha256": ORIGINAL_FIXTURE_SHA256["no-duplicates"],
        "bytes": ORIGINAL_FIXTURE_BYTES["no-duplicates"],
    },
}

ENGINE = {
    "package": "@sqlite.org/sqlite-wasm",
    "version": "3.54.1-build1",
    "sqliteVersion": "3.54.1",
}

VISIBLE_SCHEMA = {
    "tables": [
        {
            "name": "customers",
            "columns": [
                {"name": "id", "type": "integer", "primaryKey": True},
                {
                    "name": "email",
                    "type": "string",
                    "collation": "BINARY",
                },
                {"name": "created_at", "type": "string", "notNull": True},
            ],
        },
        {
            "name": "unrelated_records",
            "columns": [
                {"name": "id", "type": "integer", "primaryKey": True},
                {
                    "name": "code",
                    "type": "string",
                    "notNull": True,
                    "collation": "BINARY",
                },
                {"name": "note", "type": "string", "notNull": True},
            ],
        },
    ]
}

PROJECT = {
    "id": "challenge-e2e-project",
    "title": "QA challenge end-to-end fixture project",
    "created": {"at": "2026-10-25T00:00:00Z"},
    "access": "private",
}

QUERY_ASSETS = {
    "check/duplicate-emails": {
        "json": {
            "createdAt": "2026-10-25T00:00:00Z",
            "id": "duplicate-emails",
            "title": "Duplicate customer emails",
            "type": "SQL",
            "purpose": (
                "QA saved training query. It returns one row per exact duplicate "
                "customer email. It is executed only against the challenge's pinned "
                "fixture bytes by the challenge runtime."
            ),
            "recordsets": [{"columns": [{"name": "email", "type": "string"}]}],
        },
        "sql": (
            "SELECT email\n"
            "FROM customers\n"
            "GROUP BY email\n"
            "HAVING COUNT(*) > 1\n"
        ),
    },
    "check/always-empty": {
        "json": {
            "createdAt": "2026-10-25T00:00:00Z",
            "id": "always-empty",
            "title": "Always-empty control query",
            "type": "SQL",
            "purpose": (
                "QA negative control. It deliberately returns no rows on every "
                "fixture, so a Check using it cannot satisfy the broken fixture's "
                "required fail outcome."
            ),
            "recordsets": [{"columns": [{"name": "email", "type": "string"}]}],
        },
        "sql": "SELECT email\nFROM customers\nWHERE 0\n",
    },
}

SELECT_ONE_SQL = "SELECT 1 AS value\n"
SELECT_TWO_SQL = "SELECT 2 AS value\n"
WRONG_SQL = (
    "SELECT email, COUNT(*) AS duplicate_count\n"
    "FROM customers\n"
    "WHERE 0\n"
    "GROUP BY email\n"
)
CHECK_EXPECTATION = {
    "id": "no-duplicate-emails",
    "scope": "set",
    "kind": "row-count",
    "severity": "critical",
    "expected": {"type": "integer", "value": "0"},
}
CHECK_EXPECTATION_WRONG = {
    "id": "no-duplicate-emails",
    "scope": "set",
    "kind": "row-count",
    "severity": "critical",
    "expected": {"type": "integer", "value": "1"},
}
VALUE_COLUMNS = [{"name": "value", "type": "integer"}]
EMAIL_COLUMNS = [{"name": "email", "type": "string"}]
DUPLICATE_COLUMNS = [
    {"name": "email", "type": "string"},
    {"name": "duplicate_count", "type": "integer"},
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def typed(value):
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "number", "value": value}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    raise TypeError(f"unsupported SQLite value {value!r}")


def recordset(columns, rows):
    return {
        "rows": {
            "columns": [dict(column) for column in columns],
            "rows": [[typed(value) for value in row] for row in rows],
        }
    }


def source_fixture(source_name: str) -> bytes:
    spec = SOURCE_FIXTURES[source_name]
    data = (ROOT / spec["path"]).read_bytes()
    observed = sha256_bytes(data)
    if observed != spec["sha256"] or len(data) != spec["bytes"]:
        raise RuntimeError(
            f"source fixture {source_name} changed: "
            f"{observed}/{len(data)} != {spec['sha256']}/{spec['bytes']}"
        )
    return data


def fixture_pin(fixture_id: str, source_name: str, label: str, runs: int = 1):
    data = source_fixture(source_name)
    return {
        "id": fixture_id,
        "label": label,
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "runs": runs,
    }


def sql_result_oracle(columns, rows):
    return {
        "kind": "result",
        "columns": [dict(column) for column in columns],
        "rows": [[typed(value) for value in row] for row in rows],
        "ordering": "unordered",
    }


def sql_part(part_id: str, title: str, cases):
    return {
        "id": part_id,
        "title": title,
        "required": True,
        "answerKind": "sql",
        "sql": {"cases": cases},
    }


def single_select_manifest(challenge_id: str, timing: str, title: str, objective: str, hint: str):
    fixture = fixture_pin(
        "basic",
        "basic",
        "QA read fixture: byte-for-byte copy of the synthetic delete-duplicates basic fixture",
    )
    return {
        "schemaVersion": 1,
        "gradingVersion": "challenge-grading-v1",
        "challengeId": challenge_id,
        "revision": 1,
        "title": title,
        "objective": objective,
        "difficulty": "intro",
        "dialect": "sqlite",
        "allowedOperation": "read",
        "timing": timing,
        "engine": dict(ENGINE),
        "fixtureSuite": {"id": challenge_id + "-v1", "fixtures": [fixture]},
        "visibleSchema": json.loads(json.dumps(VISIBLE_SCHEMA)),
        "parts": [
            sql_part(
                "select-one",
                "Return the integer 1",
                [
                    {
                        "fixture": "basic",
                        "oracle": sql_result_oracle(VALUE_COLUMNS, [(1,)]),
                    }
                ],
            )
        ],
        "hints": [
            {"id": "hint-1", "text": "Use a read-only SELECT that returns the literal integer 1."},
            {"id": "hint-2", "text": hint},
        ],
        "referenceSolutions": [
            {"partId": "select-one", "answer": {"sql": SELECT_ONE_SQL}}
        ],
    }


def optional_shared_sql_manifest():
    challenge_id = "qa-timing-optional-shared-sql"
    fixture = fixture_pin(
        "basic",
        "basic",
        "QA shared read fixture: byte-for-byte copy of the synthetic delete-duplicates basic fixture",
    )
    return {
        "schemaVersion": 1,
        "gradingVersion": "challenge-grading-v1",
        "challengeId": challenge_id,
        "revision": 1,
        "title": "QA timing optional: two independent read oracles",
        "objective": (
            "QA fixture coverage for timing=optional. Two independent required read "
            "parts run against the same pinned fixture. The first must return the "
            "integer 1 and the second must return the integer 2. The attempt mode is "
            "chosen before solving and cannot change during the attempt."
        ),
        "difficulty": "intro",
        "dialect": "sqlite",
        "allowedOperation": "read",
        "timing": "optional",
        "engine": dict(ENGINE),
        "fixtureSuite": {"id": "qa-timing-optional-v1", "fixtures": [fixture]},
        "visibleSchema": json.loads(json.dumps(VISIBLE_SCHEMA)),
        "parts": [
            sql_part(
                "value-one",
                "Return the integer 1",
                [
                    {
                        "fixture": "basic",
                        "oracle": sql_result_oracle(VALUE_COLUMNS, [(1,)]),
                    }
                ],
            ),
            sql_part(
                "value-two",
                "Return the integer 2",
                [
                    {
                        "fixture": "basic",
                        "oracle": sql_result_oracle(VALUE_COLUMNS, [(2,)]),
                    }
                ],
            ),
        ],
        "hints": [
            {
                "id": "hint-1",
                "text": "Both parts are required and each part has its own SQL answer.",
            },
            {
                "id": "hint-2",
                "text": (
                    "One shared SELECT cannot pass both parts: the first oracle requires "
                    "1 and the second requires 2."
                ),
            },
        ],
        "referenceSolutions": [
            {"partId": "value-one", "answer": {"sql": SELECT_ONE_SQL}},
            {"partId": "value-two", "answer": {"sql": SELECT_TWO_SQL}},
        ],
    }


def mixed_answer_kinds_manifest():
    challenge_id = "qa-mixed-answer-kinds"
    broken = fixture_pin(
        "broken",
        "basic",
        "Broken QA fixture: byte-for-byte copy of the synthetic duplicate-customer fixture",
    )
    repaired = fixture_pin(
        "repaired",
        "no-duplicates",
        "Repaired QA fixture: byte-for-byte copy of the synthetic no-duplicates fixture",
    )
    return {
        "schemaVersion": 1,
        "gradingVersion": "challenge-grading-v1",
        "challengeId": challenge_id,
        "revision": 1,
        "title": "QA mixed answer kinds: SQL, structured and Check definition",
        "objective": (
            "QA fixture coverage for all three answer kinds in one timing=required "
            "challenge. The SQL part reports duplicate email groups; the closed "
            "structured part names the root cause and remediation; the "
            "Check-definition part selects a saved training query and supplies a "
            "learner-authored typed set-scoped row-count expectation. The broken "
            "fixture must fail the Check and the repaired fixture must pass it. All "
            "required parts must pass: a correct SQL answer with a wrong or missing "
            "non-SQL answer remains incomplete."
        ),
        "difficulty": "intermediate",
        "dialect": "sqlite",
        "allowedOperation": "read",
        "timing": "required",
        "engine": dict(ENGINE),
        "fixtureSuite": {
            "id": "qa-mixed-answer-kinds-v1",
            "fixtures": [broken, repaired],
        },
        "visibleSchema": json.loads(json.dumps(VISIBLE_SCHEMA)),
        "parts": [
            {
                "id": "duplicate-groups",
                "title": "Report duplicate email groups",
                "required": True,
                "answerKind": "sql",
                "sql": {
                    "cases": [
                        {
                            "fixture": "broken",
                            "oracle": sql_result_oracle(
                                DUPLICATE_COLUMNS,
                                [
                                    ("ada@example.com", 2),
                                    ("bob@example.com", 2),
                                ],
                            ),
                        },
                        {
                            "fixture": "repaired",
                            "oracle": sql_result_oracle(DUPLICATE_COLUMNS, []),
                        },
                    ]
                },
            },
            {
                "id": "diagnosis",
                "title": "Select the closed diagnosis and remediation",
                "required": True,
                "answerKind": "structured",
                "structured": {
                    "fields": [
                        {
                            "id": "root-cause",
                            "label": "Root cause",
                            "cardinality": "single",
                            "required": True,
                            "options": [
                                {
                                    "id": "duplicate-email-rows",
                                    "label": "Duplicate customer rows for one exact email",
                                },
                                {
                                    "id": "missing-unique-index",
                                    "label": "Only a missing unique index",
                                },
                                {
                                    "id": "wrong-database",
                                    "label": "The wrong database was opened",
                                },
                            ],
                        },
                        {
                            "id": "remediation",
                            "label": "Remediation",
                            "cardinality": "multi",
                            "required": True,
                            "minSelections": 1,
                            "maxSelections": 2,
                            "options": [
                                {
                                    "id": "deduplicate-then-constrain",
                                    "label": "Deduplicate, then constrain exact email values",
                                },
                                {
                                    "id": "drop-customer-table",
                                    "label": "Drop the customer table",
                                },
                                {
                                    "id": "ignore-duplicates",
                                    "label": "Ignore duplicate rows",
                                },
                            ],
                        },
                    ],
                    "expected": {
                        "selections": {
                            "root-cause": ["duplicate-email-rows"],
                            "remediation": ["deduplicate-then-constrain"],
                        }
                    },
                },
            },
            {
                "id": "recurrence-check",
                "title": "Author a Check definition for recurring duplicates",
                "required": True,
                "answerKind": "check-definition",
                "checkDefinition": {
                    "queryIds": [
                        "check/duplicate-emails",
                        "check/always-empty",
                    ],
                    "expectation": json.loads(json.dumps(CHECK_EXPECTATION)),
                    "cases": [
                        {"fixture": "broken", "expectedOutcome": "fail"},
                        {"fixture": "repaired", "expectedOutcome": "pass"},
                    ],
                },
            },
        ],
        "hints": [
            {
                "id": "hint-1",
                "text": (
                    "For the SQL part, group customers by exact email and keep groups "
                    "with more than one row. The repaired fixture has no such group."
                ),
            },
            {
                "id": "hint-2",
                "text": (
                    "For the structured part, choose the root cause that describes "
                    "duplicate rows and the remediation that deduplicates before it "
                    "constrains the exact email value."
                ),
            },
            {
                "id": "hint-3",
                "text": (
                    "For the Check part, author the expectation explicitly: id "
                    "no-duplicate-emails, scope set, kind row-count, severity critical, "
                    "and expected integer value 0."
                ),
            },
            {
                "id": "hint-4",
                "text": (
                    "Choose check/duplicate-emails. check/always-empty returns zero rows "
                    "on both fixtures, so it passes the repaired case but cannot satisfy "
                    "the broken fixture's required fail outcome."
                ),
            },
            {
                "id": "hint-5",
                "text": (
                    "All three parts are required. Correct SQL alone is incomplete until "
                    "the structured selection and Check definition also pass."
                ),
            },
        ],
        "referenceSolutions": [
            {
                "partId": "duplicate-groups",
                "answer": {
                    "sql": (
                        "SELECT email, COUNT(*) AS duplicate_count\n"
                        "FROM customers\n"
                        "GROUP BY email\n"
                        "HAVING COUNT(*) > 1\n"
                        "ORDER BY email\n"
                    )
                },
            },
            {
                "partId": "diagnosis",
                "answer": {
                    "structured": {
                        "selections": {
                            "root-cause": ["duplicate-email-rows"],
                            "remediation": ["deduplicate-then-constrain"],
                        }
                    }
                },
            },
            {
                "partId": "recurrence-check",
                "answer": {
                    "checkDefinition": {
                        "queryId": "check/duplicate-emails",
                        "expectation": json.loads(json.dumps(CHECK_EXPECTATION)),
                    }
                },
            },
        ],
    }


def build_manifests():
    return {
        "qa-timing-off-select1": single_select_manifest(
            "qa-timing-off-select1",
            "off",
            "QA timing off: read the literal value",
            (
                "QA fixture coverage for timing=off. Return exactly one row containing "
                "the integer value 1 from the pinned fixture. No timer is recorded. "
                "The fixture tables are unrelated to this read probe; the answer is "
                "the literal required by the oracle."
            ),
            "The fixture is ready immediately, so no Start timed step applies.",
        ),
        "qa-timing-required-select1": single_select_manifest(
            "qa-timing-required-select1",
            "required",
            "QA timing required: read the literal value",
            (
                "QA fixture coverage for timing=required. Return exactly one row "
                "containing the integer value 1 from the pinned fixture. The editor "
                "must stay masked until Start timed opens the attempt; no untimed "
                "attempt is permitted."
            ),
            "Only a timed attempt may be opened for this revision.",
        ),
        "qa-timing-optional-shared-sql": optional_shared_sql_manifest(),
        "qa-mixed-answer-kinds": mixed_answer_kinds_manifest(),
    }


def build_assets(project_dir: Path = PROJECT_DIR):
    """Return every authored path -> byte mapping. Never touches disk."""
    project_dir = Path(project_dir)
    assets: dict[Path, bytes] = {}

    assets[project_dir / "datatug-project.json"] = json_bytes(PROJECT)

    for query_ref, asset in QUERY_ASSETS.items():
        base = project_dir / "queries" / query_ref
        assets[base.with_name(base.name + ".query.json")] = json_bytes(asset["json"])
        assets[base.with_name(base.name + ".query.sql")] = asset["sql"].encode("utf-8")

    manifests = build_manifests()
    for challenge_id, manifest in manifests.items():
        challenge_dir = project_dir / "challenges" / challenge_id
        assets[challenge_dir / "1.json"] = json_bytes(manifest)
        for fixture in manifest["fixtureSuite"]["fixtures"]:
            source_name = {
                ("qa-mixed-answer-kinds", "broken"): "basic",
                ("qa-mixed-answer-kinds", "repaired"): "no-duplicates",
            }.get((challenge_id, fixture["id"]), fixture["id"])
            assets[challenge_dir / "fixtures" / (fixture["id"] + ".db")] = source_fixture(
                source_name
            )
    return dict(sorted(assets.items(), key=lambda item: item[0].as_posix()))


def regenerate(project_dir: Path = PROJECT_DIR) -> dict:
    project_dir = Path(project_dir)
    assets = build_assets(project_dir)
    for path, data in assets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {
        "ok": True,
        "projectDir": str(project_dir),
        "files": [
            {
                "path": path.relative_to(project_dir).as_posix(),
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
            for path, data in assets.items()
        ],
    }


def execute_query(db: sqlite3.Connection, sql: str):
    cursor = db.execute(sql)
    columns = [description[0] for description in cursor.description]
    return [tuple(row) for row in cursor.fetchall()], columns


def _typed_rows(rows):
    return [[typed(value) for value in row] for row in rows]


def _oracle_rows(oracle):
    return [
        [cell["value"] if cell["type"] != "integer" else int(cell["value"]) for cell in row]
        for row in oracle["rows"]
    ]


def _compare_oracle(oracle, actual_rows):
    expected = _oracle_rows(oracle)
    if oracle.get("ordering") == "ordered":
        return expected == [list(row) for row in actual_rows]
    expected_counts = Counter(_json_cell(row) for row in expected)
    actual_counts = Counter(_json_cell(row) for row in actual_rows)
    return expected_counts == actual_counts


def _json_cell(row):
    return json.dumps([typed(value) for value in row], sort_keys=True)


def _fixture_bytes(manifest: dict, challenge_dir: Path, fixture_id: str) -> bytes:
    relative = f"fixtures/{fixture_id}.db"
    return (challenge_dir / relative).read_bytes()


def _reference_sql(manifest: dict, part_id: str):
    for reference in manifest.get("referenceSolutions", []):
        if reference["partId"] == part_id:
            return reference["answer"].get("sql")
    return None


def _reference_check(manifest: dict, part_id: str):
    for reference in manifest.get("referenceSolutions", []):
        if reference["partId"] == part_id:
            return reference["answer"].get("checkDefinition")
    return None


def verify_manifest_semantics(manifest: dict, project_dir: Path, errors: list[str]) -> dict:
    challenge_id = manifest["challengeId"]
    challenge_dir = project_dir / "challenges" / challenge_id
    prefix = f"{challenge_id}: "
    if manifest.get("schemaVersion") != 1:
        errors.append(prefix + "schemaVersion must be 1")
    if manifest.get("gradingVersion") != "challenge-grading-v1":
        errors.append(prefix + "gradingVersion must be challenge-grading-v1")
    if manifest.get("engine") != ENGINE:
        errors.append(prefix + "engine must pin the approved 3.54.1 build")
    if manifest.get("dialect") != "sqlite":
        errors.append(prefix + "dialect must be sqlite")
    if manifest.get("allowedOperation") != "read":
        errors.append(prefix + "QA fixtures must be read-only")
    if not (challenge_dir / "1.json").exists():
        errors.append(prefix + "manifest path missing")
    for fixture in manifest["fixtureSuite"]["fixtures"]:
        relative = f"challenges/{challenge_id}/fixtures/{fixture['id']}.db"
        path = project_dir / relative
        if not path.exists():
            errors.append(prefix + f"fixture path missing: {relative}")
            continue
        data = path.read_bytes()
        if len(data) != fixture["bytes"]:
            errors.append(prefix + f"{fixture['id']} byte length mismatch")
        if sha256_bytes(data) != fixture["sha256"]:
            errors.append(prefix + f"{fixture['id']} SHA-256 mismatch")

    parts = {part["id"]: part for part in manifest["parts"]}
    for part in manifest["parts"]:
        if not part["required"]:
            errors.append(prefix + f"part {part['id']} must be required")

    def fixture_rows(fixture_id):
        data = _fixture_bytes(manifest, challenge_dir, fixture_id)
        connection = sqlite3.connect(":memory:")
        try:
            connection.deserialize(data)
            return connection
        except Exception:
            connection.close()
            raise

    sql_parts = [part for part in manifest["parts"] if part["answerKind"] == "sql"]
    for part in sql_parts:
        sql = _reference_sql(manifest, part["id"])
        if not sql:
            errors.append(prefix + f"SQL part {part['id']} has no reference solution")
            continue
        for case in part["sql"]["cases"]:
            connection = fixture_rows(case["fixture"])
            try:
                rows, columns = execute_query(connection, sql)
            finally:
                connection.close()
            oracle = case["oracle"]
            if len(columns) != len(oracle["columns"]):
                errors.append(
                    prefix
                    + f"{part['id']}/{case['fixture']}: column count {len(columns)} != "
                    + str(len(oracle["columns"]))
                )
            if not _compare_oracle(oracle, rows):
                errors.append(
                    prefix
                    + f"{part['id']}/{case['fixture']}: reference rows do not match oracle "
                    + f"{rows!r}"
                )

    if challenge_id == "qa-timing-optional-shared-sql":
        part_one = next(part for part in manifest["parts"] if part["id"] == "value-one")
        part_two = next(part for part in manifest["parts"] if part["id"] == "value-two")
        connection = fixture_rows("basic")
        try:
            shared_rows, _ = execute_query(connection, SELECT_ONE_SQL)
        finally:
            connection.close()
        first = _compare_oracle(part_one["sql"]["cases"][0]["oracle"], shared_rows)
        second = _compare_oracle(part_two["sql"]["cases"][0]["oracle"], shared_rows)
        if first == second:
            errors.append(prefix + "one shared SQL must not pass both independent parts")
        if not first or second:
            errors.append(prefix + "the shared SQL probe did not produce the expected 1/2 split")

    if challenge_id == "qa-mixed-answer-kinds":
        check_part = parts["recurrence-check"]
        if check_part["answerKind"] != "check-definition":
            errors.append(prefix + "recurrence-check must be a Check-definition part")
        if check_part["checkDefinition"]["expectation"] != CHECK_EXPECTATION:
            errors.append(prefix + "declared Check expectation differs from the QA authority")
        if sorted(check_part["checkDefinition"]["queryIds"]) != [
            "check/always-empty",
            "check/duplicate-emails",
        ]:
            errors.append(prefix + "Check part must offer exactly two saved query choices")
        outcomes = {}
        for query_ref in check_part["checkDefinition"]["queryIds"]:
            query_json = project_dir / "queries" / (query_ref + ".query.json")
            query_sql = project_dir / "queries" / (query_ref + ".query.sql")
            if not query_json.exists() or not query_sql.exists():
                errors.append(prefix + f"saved query asset missing: {query_ref}")
                continue
            metadata = json.loads(query_json.read_text())
            if metadata["id"] != query_ref.rsplit("/", 1)[-1]:
                errors.append(prefix + f"saved query id mismatch: {query_ref}")
            sql = query_sql.read_text()
            query_outcomes = {}
            for case in check_part["checkDefinition"]["cases"]:
                connection = fixture_rows(case["fixture"])
                try:
                    rows, columns = execute_query(connection, sql)
                finally:
                    connection.close()
                if columns != ["email"]:
                    errors.append(prefix + f"{query_ref} must return only email")
                observed = "pass" if len(rows) == 0 else "fail"
                query_outcomes[case["fixture"]] = observed
                if query_ref == "check/duplicate-emails" and observed != case["expectedOutcome"]:
                    errors.append(
                        prefix
                        + f"correct Check query outcome {case['fixture']} "
                        + f"{observed} != {case['expectedOutcome']}"
                    )
            outcomes[query_ref] = query_outcomes
        control = outcomes.get("check/always-empty", {})
        if control.get("broken") != "pass" or control.get("repaired") != "pass":
            errors.append(prefix + "always-empty control must be pass on both fixtures")
        if control.get("broken") == check_part["checkDefinition"]["cases"][0]["expectedOutcome"]:
            errors.append(prefix + "control query must violate the broken fixture expectation")

        # The structure of the reference answers must match the declared closed
        # answers. Core performs the full structural check in the Go helper.
        ref_check = _reference_check(manifest, "recurrence-check")
        if ref_check != {
            "queryId": "check/duplicate-emails",
            "expectation": CHECK_EXPECTATION,
        }:
            errors.append(prefix + "reference Check answer is not the declared correct answer")
        structured = parts["diagnosis"]["structured"]
        if structured["expected"] != {
            "selections": {
                "root-cause": ["duplicate-email-rows"],
                "remediation": ["deduplicate-then-constrain"],
            }
        }:
            errors.append(prefix + "structured expected answer drift")
        for field in structured["fields"]:
            if field["id"] == "root-cause" and field["cardinality"] != "single":
                errors.append(prefix + "root-cause must be single-select")
            if field["id"] == "remediation" and field["cardinality"] != "multi":
                errors.append(prefix + "remediation must be multi-select")

    return {
        "challengeId": challenge_id,
        "revision": manifest["revision"],
        "timing": manifest["timing"],
        "parts": [
            {
                "id": part["id"],
                "answerKind": part["answerKind"],
                "required": part["required"],
            }
            for part in manifest["parts"]
        ],
        "fixtures": [
            {
                "id": fixture["id"],
                "path": f"challenges/{challenge_id}/fixtures/{fixture['id']}.db",
                "sha256": fixture["sha256"],
                "bytes": fixture["bytes"],
            }
            for fixture in manifest["fixtureSuite"]["fixtures"]
        ],
    }


def verify_original_assets(errors: list[str]) -> dict:
    manifest_path = SOURCE_SUITE_DIR / "1.json"
    observed_manifest = sha256_file(manifest_path)
    if observed_manifest != ORIGINAL_MANIFEST_SHA256:
        errors.append("public demo-project-1/challenges/delete-duplicates/1.json changed")
    observed_fixtures = {}
    for fixture_id, expected in ORIGINAL_FIXTURE_SHA256.items():
        path = SOURCE_SUITE_DIR / "fixtures" / (fixture_id + ".db")
        observed = sha256_file(path)
        observed_fixtures[fixture_id] = {
            "sha256": observed,
            "bytes": path.stat().st_size,
        }
        if observed != expected:
            errors.append(f"public fixture {fixture_id}.db changed")
        if path.stat().st_size != ORIGINAL_FIXTURE_BYTES[fixture_id]:
            errors.append(f"public fixture {fixture_id}.db changed byte length")
    return {
        "manifest": {
            "path": "demo-project-1/challenges/delete-duplicates/1.json",
            "sha256": observed_manifest,
            "expectedSha256": ORIGINAL_MANIFEST_SHA256,
        },
        "fixtures": observed_fixtures,
    }


def verify_no_catalogue_registration(errors: list[str]) -> dict:
    checked = []
    for relative in [".datatug.yaml", "demo-project-1/datatug-project.json", "README.md"]:
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text()
        checked.append(relative)
        if "challenge-e2e-project" in text:
            errors.append(f"{relative} must not register the QA fixture project")
    return {"checked": checked, "qaProjectRegistered": False}


def _query_observations(manifest: dict, challenge_dir: Path, scenario: str, sql: str, columns):
    result = {}
    for fixture_id in sorted(fixture["id"] for fixture in manifest["fixtureSuite"]["fixtures"]):
        connection = sqlite3.connect(":memory:")
        try:
            connection.deserialize(_fixture_bytes(manifest, challenge_dir, fixture_id))
            rows, _ = execute_query(connection, sql)
        finally:
            connection.close()
        result[fixture_id] = recordset(columns, rows)
    return result


def build_core_request(project_dir: Path = PROJECT_DIR) -> dict:
    manifests = build_manifests()
    observations = {}
    for challenge_id, manifest in manifests.items():
        challenge_dir = project_dir / "challenges" / challenge_id
        if challenge_id in {
            "qa-timing-off-select1",
            "qa-timing-required-select1",
        }:
            observations[challenge_id] = {
                "select-one": _query_observations(
                    manifest, challenge_dir, "select-one", SELECT_ONE_SQL, VALUE_COLUMNS
                )
            }
        elif challenge_id == "qa-timing-optional-shared-sql":
            observations[challenge_id] = {
                "value-one": _query_observations(
                    manifest, challenge_dir, "value-one", SELECT_ONE_SQL, VALUE_COLUMNS
                ),
                "value-two": _query_observations(
                    manifest, challenge_dir, "value-two", SELECT_TWO_SQL, VALUE_COLUMNS
                ),
                "shared": _query_observations(
                    manifest, challenge_dir, "shared", SELECT_ONE_SQL, VALUE_COLUMNS
                ),
            }
        elif challenge_id == "qa-mixed-answer-kinds":
            sql = _reference_sql(manifest, "duplicate-groups")
            check_sql = QUERY_ASSETS["check/duplicate-emails"]["sql"]
            control_sql = QUERY_ASSETS["check/always-empty"]["sql"]
            observations[challenge_id] = {
                "sql": _query_observations(
                    manifest, challenge_dir, "sql", sql, DUPLICATE_COLUMNS
                ),
                "sql-wrong": _query_observations(
                    manifest, challenge_dir, "sql-wrong", WRONG_SQL, DUPLICATE_COLUMNS
                ),
                "check": _query_observations(
                    manifest, challenge_dir, "check", check_sql, EMAIL_COLUMNS
                ),
                "check-control": _query_observations(
                    manifest, challenge_dir, "check-control", control_sql, EMAIL_COLUMNS
                ),
            }
    return {
        "projectDir": str(project_dir),
        "observations": observations,
        "sharedSql": SELECT_ONE_SQL,
    }


def find_core_dir() -> Path | None:
    candidates = []
    env = os.environ.get("DATATUG_CORE_DIR")
    if env:
        candidates.append(Path(env))
    # Worktree layout: .worktrees/<task>/github.com/datatug/<repo>
    candidates.append(ROOT.parent / "datatug-core")
    candidates.append(Path.home() / "projects/datatug/datatug-core")
    for candidate in candidates:
        if (candidate / "pkg/challenge/manifest.go").exists():
            return candidate.resolve()
    return None


CORE_HELPER_SOURCE = r'''package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/datatug/datatug-core/pkg/challenge"
	"github.com/datatug/datatug-core/pkg/detective"
	"github.com/datatug/datatug-core/pkg/investigation"
)

type request struct {
	ProjectDir   string                                          `json:"projectDir"`
	Observations map[string]map[string]map[string]challenge.Observation `json:"observations"`
	SharedSQL    string                                          `json:"sharedSql"`
}

type expectedPart struct {
	ID         string `json:"id"`
	AnswerKind string `json:"answerKind"`
}

type expectedChallenge struct {
	Timing string         `json:"timing"`
	Parts  []expectedPart `json:"parts"`
}

type response struct {
	OK       bool           `json:"ok"`
	Errors   []string       `json:"errors"`
	Receipts map[string]any `json:"receipts"`
}

var expected = map[string]expectedChallenge{
	"qa-timing-off-select1": {
		Timing: "off",
		Parts:  []expectedPart{{"select-one", "sql"}},
	},
	"qa-timing-required-select1": {
		Timing: "required",
		Parts:  []expectedPart{{"select-one", "sql"}},
	},
	"qa-timing-optional-shared-sql": {
		Timing: "optional",
		Parts:  []expectedPart{{"value-one", "sql"}, {"value-two", "sql"}},
	},
	"qa-mixed-answer-kinds": {
		Timing: "required",
		Parts: []expectedPart{
			{"duplicate-groups", "sql"},
			{"diagnosis", "structured"},
			{"recurrence-check", "check-definition"},
		},
	},
}

func main() {
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		panic(err)
	}
	var req request
	if err := json.Unmarshal(data, &req); err != nil {
		panic(err)
	}
	result := response{OK: true, Errors: []string{}, Receipts: map[string]any{}}
	fail := func(format string, args ...any) {
		result.OK = false
		result.Errors = append(result.Errors, fmt.Sprintf(format, args...))
	}
	ids := make([]string, 0, len(expected))
	for id := range expected {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	opened := map[string]*challenge.Opened{}
	for _, id := range ids {
		item, err := openChallenge(req.ProjectDir, id)
		if err != nil {
			fail("%s: %v", id, err)
			continue
		}
		opened[id] = item
		receipt := map[string]any{
			"definitionDigest": item.DefinitionDigest,
			"fixtures":        item.FixtureIDs(),
			"timing":          string(item.Manifest.Timing),
			"parts":           partReceipts(item.Manifest),
		}
		result.Receipts[id] = receipt
		checkExpected(id, item, expected[id], fail)
	}
	if item, ok := opened["qa-timing-off-select1"]; ok {
		verifySingle(req, item, "qa-timing-off-select1", result.Receipts["qa-timing-off-select1"].(map[string]any), fail)
	}
	if item, ok := opened["qa-timing-required-select1"]; ok {
		verifySingle(req, item, "qa-timing-required-select1", result.Receipts["qa-timing-required-select1"].(map[string]any), fail)
	}
	if item, ok := opened["qa-timing-optional-shared-sql"]; ok {
		verifyOptional(req, item, result.Receipts["qa-timing-optional-shared-sql"].(map[string]any), fail)
	}
	if item, ok := opened["qa-mixed-answer-kinds"]; ok {
		verifyMixed(req, item, result.Receipts["qa-mixed-answer-kinds"].(map[string]any), fail)
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(result); err != nil {
		panic(err)
	}
	if !result.OK {
		os.Exit(1)
	}
}

func partReceipts(manifest challenge.Manifest) []map[string]any {
	parts := make([]map[string]any, 0, len(manifest.Parts))
	for _, part := range manifest.Parts {
		parts = append(parts, map[string]any{
			"id":         part.ID,
			"answerKind": part.AnswerKind,
			"required":   part.Required,
		})
	}
	return parts
}

func openChallenge(projectDir, challengeID string) (*challenge.Opened, error) {
	asset, err := challenge.AssetPath(challengeID, 1)
	if err != nil {
		return nil, err
	}
	wantAsset := filepath.ToSlash(filepath.Join("challenges", challengeID, "1.json"))
	if asset != wantAsset {
		return nil, fmt.Errorf("AssetPath = %q, want %q", asset, wantAsset)
	}
	manifestData, err := os.ReadFile(filepath.Join(projectDir, filepath.FromSlash(asset)))
	if err != nil {
		return nil, err
	}
	manifest, err := challenge.LoadManifest(manifestData)
	if err != nil {
		return nil, err
	}
	fixtures := map[string][]byte{}
	for _, fixture := range manifest.FixtureSuite.Fixtures {
		relative, err := challenge.FixtureAssetPath(challengeID, fixture.ID)
		if err != nil {
			return nil, err
		}
		want := filepath.ToSlash(filepath.Join("challenges", challengeID, "fixtures", fixture.ID+".db"))
		if relative != want {
			return nil, fmt.Errorf("FixtureAssetPath(%s, %s) = %q, want %q", challengeID, fixture.ID, relative, want)
		}
		data, err := os.ReadFile(filepath.Join(projectDir, filepath.FromSlash(relative)))
		if err != nil {
			return nil, err
		}
		fixtures[fixture.ID] = data
	}
	opened, err := challenge.Open(manifestData, fixtures)
	if err != nil {
		return nil, err
	}
	if err := opened.RequireEngine(challenge.SupportedEngine); err != nil {
		return nil, err
	}
	return opened, nil
}

func checkExpected(id string, opened *challenge.Opened, want expectedChallenge, fail func(string, ...any)) {
	if string(opened.Manifest.Timing) != want.Timing {
		fail("%s: timing = %q, want %q", id, opened.Manifest.Timing, want.Timing)
	}
	if opened.Manifest.AllowedOperation != "read" {
		fail("%s: allowedOperation = %q, want read", id, opened.Manifest.AllowedOperation)
	}
	if len(opened.Manifest.Parts) != len(want.Parts) {
		fail("%s: %d parts, want %d", id, len(opened.Manifest.Parts), len(want.Parts))
	}
	byID := map[string]challenge.Part{}
	for _, part := range opened.Manifest.Parts {
		byID[part.ID] = part
	}
	for _, expectedPart := range want.Parts {
		part, ok := byID[expectedPart.ID]
		if !ok {
			fail("%s: missing part %q", id, expectedPart.ID)
			continue
		}
		if part.AnswerKind != expectedPart.AnswerKind {
			fail("%s: part %q answerKind = %q, want %q", id, part.ID, part.AnswerKind, expectedPart.AnswerKind)
		}
		if !part.Required {
			fail("%s: part %q must be required", id, part.ID)
		}
	}
}

func partByID(manifest challenge.Manifest, id string) challenge.Part {
	for _, part := range manifest.Parts {
		if part.ID == id {
			return part
		}
	}
	panic("unknown part " + id)
}

func referenceSQL(manifest challenge.Manifest, partID string) string {
	for _, reference := range manifest.ReferenceSolutions {
		if reference.PartID == partID {
			if reference.Answer.SQL == "" {
				panic("reference solution for " + partID + " is not SQL")
			}
			return reference.Answer.SQL
		}
	}
	panic("missing reference SQL for " + partID)
}

func referenceCheck(manifest challenge.Manifest, partID string) challenge.CheckDefinitionAnswer {
	for _, reference := range manifest.ReferenceSolutions {
		if reference.PartID == partID {
			if reference.Answer.CheckDefinition == nil {
				panic("reference solution for " + partID + " is not a Check definition")
			}
			return *reference.Answer.CheckDefinition
		}
	}
	panic("missing reference Check for " + partID)
}

func complete(manifest challenge.Manifest, outcomes []challenge.PartOutcome) (bool, []string, error) {
	attempt, err := challenge.GradeAttempt(manifest, outcomes)
	if err != nil {
		return false, nil, err
	}
	return attempt.Complete, attempt.BlockingParts, nil
}

func observation(req request, challengeID, scenario string) map[string]challenge.Observation {
	return req.Observations[challengeID][scenario]
}

func verifySingle(req request, opened *challenge.Opened, challengeID string, receipt map[string]any, fail func(string, ...any)) {
	part := partByID(opened.Manifest, "select-one")
	result := challenge.GradeSQLPart(*part.SQL, referenceSQL(opened.Manifest, part.ID), observation(req, challengeID, "select-one"))
	receipt["sql"] = result
	if result.Outcome != challenge.OutcomePass {
		fail("%s: reference SQL outcome = %s (%s)", challengeID, result.Outcome, result.Message)
	}
	pass, blocking, err := complete(opened.Manifest, []challenge.PartOutcome{result.AsOutcome(part)})
	if err != nil || !pass {
		fail("%s: complete = %v, blocking = %v, err = %v", challengeID, pass, blocking, err)
	}
}

func verifyOptional(req request, opened *challenge.Opened, receipt map[string]any, fail func(string, ...any)) {
	manifest := opened.Manifest
	first := partByID(manifest, "value-one")
	second := partByID(manifest, "value-two")
	sharedObs := observation(req, "qa-timing-optional-shared-sql", "shared")
	firstShared := challenge.GradeSQLPart(*first.SQL, req.SharedSQL, sharedObs)
	secondShared := challenge.GradeSQLPart(*second.SQL, req.SharedSQL, sharedObs)
	receipt["sharedSql"] = map[string]any{"value-one": firstShared, "value-two": secondShared}
	if firstShared.Outcome == secondShared.Outcome {
		fail("optional: one shared SQL must not produce the same outcome for both parts")
	}
	if firstShared.Outcome != challenge.OutcomePass || secondShared.Outcome != challenge.OutcomeFail {
		fail("optional: shared SELECT 1 must pass value-one and fail value-two")
	}
	sharedPass, _, err := complete(manifest, []challenge.PartOutcome{firstShared.AsOutcome(first), secondShared.AsOutcome(second)})
	if err != nil || sharedPass {
		fail("optional: shared SQL attempt must be incomplete (complete=%v, err=%v)", sharedPass, err)
	}

	firstCorrect := challenge.GradeSQLPart(*first.SQL, referenceSQL(manifest, first.ID), observation(req, "qa-timing-optional-shared-sql", "value-one"))
	secondCorrect := challenge.GradeSQLPart(*second.SQL, referenceSQL(manifest, second.ID), observation(req, "qa-timing-optional-shared-sql", "value-two"))
	receipt["correct"] = map[string]any{"value-one": firstCorrect, "value-two": secondCorrect}
	pass, blocking, err := complete(manifest, []challenge.PartOutcome{firstCorrect.AsOutcome(first), secondCorrect.AsOutcome(second)})
	if err != nil || !pass {
		fail("optional: correct attempt complete=%v blocking=%v err=%v", pass, blocking, err)
	}
}

func verifyMixed(req request, opened *challenge.Opened, receipt map[string]any, fail func(string, ...any)) {
	manifest := opened.Manifest
	sqlPart := partByID(manifest, "duplicate-groups")
	structuredPart := partByID(manifest, "diagnosis")
	checkPart := partByID(manifest, "recurrence-check")
	challengeID := "qa-mixed-answer-kinds"

	sqlResult := challenge.GradeSQLPart(*sqlPart.SQL, referenceSQL(manifest, sqlPart.ID), observation(req, challengeID, "sql"))
	structuredResult := challenge.EvaluateStructured(*structuredPart.Structured, structuredPart.Structured.Expected)
	checkAnswer := referenceCheck(manifest, checkPart.ID)
	checkResult := challenge.EvaluateCheckDefinition(*checkPart.CheckDefinition, checkAnswer, observation(req, challengeID, "check"))
	receipt["correct"] = map[string]any{"sql": sqlResult, "structured": structuredResult, "check": checkResult}
	if sqlResult.Outcome != challenge.OutcomePass {
		fail("mixed: reference SQL outcome = %s (%s)", sqlResult.Outcome, sqlResult.Message)
	}
	if structuredResult.Outcome != challenge.OutcomePass {
		fail("mixed: structured expected answer outcome = %s (%s)", structuredResult.Outcome, structuredResult.Message)
	}
	if checkResult.Outcome != challenge.OutcomePass {
		fail("mixed: correct Check outcome = %s (%s)", checkResult.Outcome, checkResult.Message)
	}
	for _, item := range checkResult.Cases {
		if item.Outcome != challenge.OutcomePass {
			fail("mixed: Check case %s outcome = %s (%s)", item.Fixture, item.Outcome, item.Message)
		}
	}
	correctOutcomes := []challenge.PartOutcome{
		sqlResult.AsOutcome(sqlPart),
		structuredResult.AsOutcome(structuredPart),
		checkResult.AsOutcome(checkPart),
	}
	pass, blocking, err := complete(manifest, correctOutcomes)
	if err != nil || !pass {
		fail("mixed: correct attempt complete=%v blocking=%v err=%v", pass, blocking, err)
	}

	wrongStructured := challenge.StructuredAnswer{Selections: map[string][]string{}}
	for _, field := range structuredPart.Structured.Fields {
		if field.Cardinality == challenge.CardinalitySingle {
			wrongStructured.Selections[field.ID] = []string{field.Options[1].ID}
		} else {
			wrongStructured.Selections[field.ID] = structuredPart.Structured.Expected.Selections[field.ID]
		}
	}
	wrongStructuredResult := challenge.EvaluateStructured(*structuredPart.Structured, wrongStructured)
	receipt["wrongStructured"] = wrongStructuredResult
	if wrongStructuredResult.Outcome != challenge.OutcomeFail {
		fail("mixed: wrong structured answer must fail, got %s", wrongStructuredResult.Outcome)
	}
	wrongStructuredPass, wrongStructuredBlocking, err := complete(manifest, []challenge.PartOutcome{
		sqlResult.AsOutcome(sqlPart),
		wrongStructuredResult.AsOutcome(structuredPart),
		checkResult.AsOutcome(checkPart),
	})
	if err != nil || wrongStructuredPass {
		fail("mixed: correct SQL + wrong structured must be incomplete (complete=%v err=%v)", wrongStructuredPass, err)
	}
	if !contains(wrongStructuredBlocking, structuredPart.ID) {
		fail("mixed: blocking parts %v do not name %s", wrongStructuredBlocking, structuredPart.ID)
	}

	missingStructuredResult := challenge.EvaluateStructured(*structuredPart.Structured, challenge.StructuredAnswer{Selections: map[string][]string{}})
	receipt["missingStructured"] = missingStructuredResult
	if missingStructuredResult.Outcome != challenge.OutcomeFail {
		fail("mixed: missing structured answer must fail, got %s", missingStructuredResult.Outcome)
	}
	missingStructuredPass, _, err := complete(manifest, []challenge.PartOutcome{
		sqlResult.AsOutcome(sqlPart),
		checkResult.AsOutcome(checkPart),
	})
	if err == nil || missingStructuredPass {
		fail("mixed: missing required structured outcome must be refused and incomplete")
	}
	receipt["missingStructuredRefused"] = err != nil

	missingCheckPass, _, err := complete(manifest, []challenge.PartOutcome{
		sqlResult.AsOutcome(sqlPart),
		structuredResult.AsOutcome(structuredPart),
	})
	if err == nil || missingCheckPass {
		fail("mixed: missing required Check outcome must be refused and incomplete")
	}
	receipt["missingCheckRefused"] = err != nil

	unknownStructured := challenge.StructuredAnswer{Selections: map[string][]string{
		"root-cause": {"duplicate-email-rows"},
		"remediation": {"deduplicate-then-constrain"},
		"not-a-field": {"unknown"},
	}}
	unknownStructuredResult := challenge.EvaluateStructured(*structuredPart.Structured, unknownStructured)
	receipt["unknownStructured"] = unknownStructuredResult
	if unknownStructuredResult.Outcome != challenge.OutcomeUnknown {
		fail("mixed: unknown structured field must be unknown, got %s", unknownStructuredResult.Outcome)
	}

	wrongSQLResult := challenge.GradeSQLPart(*sqlPart.SQL, "SELECT 2 AS value\n", observation(req, challengeID, "sql-wrong"))
	receipt["wrongSql"] = wrongSQLResult
	if wrongSQLResult.Outcome != challenge.OutcomeFail {
		fail("mixed: wrong SQL must fail, got %s", wrongSQLResult.Outcome)
	}
	wrongSQLPass, _, err := complete(manifest, []challenge.PartOutcome{
		wrongSQLResult.AsOutcome(sqlPart),
		structuredResult.AsOutcome(structuredPart),
		checkResult.AsOutcome(checkPart),
	})
	if err != nil || wrongSQLPass {
		fail("mixed: wrong SQL + correct non-SQL must be incomplete (complete=%v err=%v)", wrongSQLPass, err)
	}

	wrongQueryAnswer := checkAnswer
	wrongQueryAnswer.QueryID = "check/always-empty"
	wrongQueryResult := challenge.EvaluateCheckDefinition(*checkPart.CheckDefinition, wrongQueryAnswer, observation(req, challengeID, "check-control"))
	receipt["wrongQuery"] = wrongQueryResult
	if wrongQueryResult.Outcome != challenge.OutcomeFail {
		fail("mixed: wrong saved query must fail the Check, got %s", wrongQueryResult.Outcome)
	}
	brokenFailed := false
	for _, item := range wrongQueryResult.Cases {
		if item.Fixture == "broken" && item.Outcome == challenge.OutcomeFail {
			brokenFailed = true
		}
	}
	if !brokenFailed {
		fail("mixed: always-empty control must fail the broken Check case")
	}
	wrongQueryPass, _, err := complete(manifest, []challenge.PartOutcome{
		sqlResult.AsOutcome(sqlPart),
		structuredResult.AsOutcome(structuredPart),
		wrongQueryResult.AsOutcome(checkPart),
	})
	if err != nil || wrongQueryPass {
		fail("mixed: wrong saved query must leave the attempt incomplete (complete=%v err=%v)", wrongQueryPass, err)
	}

	wrongExpectation := checkAnswer.Expectation
	wrongValue := investigation.NewIntegerValue("1")
	wrongExpectation.Expected = &wrongValue
	wrongExpectationAnswer := challenge.CheckDefinitionAnswer{QueryID: checkAnswer.QueryID, Expectation: wrongExpectation}
	wrongExpectationResult := challenge.EvaluateCheckDefinition(*checkPart.CheckDefinition, wrongExpectationAnswer, observation(req, challengeID, "check"))
	receipt["wrongExpectation"] = wrongExpectationResult
	if wrongExpectationResult.Outcome == challenge.OutcomePass {
		fail("mixed: wrong typed expectation must not pass")
	}
	wrongExpectationPass, _, err := complete(manifest, []challenge.PartOutcome{
		sqlResult.AsOutcome(sqlPart),
		structuredResult.AsOutcome(structuredPart),
		wrongExpectationResult.AsOutcome(checkPart),
	})
	if err != nil || wrongExpectationPass {
		fail("mixed: wrong typed expectation must leave the attempt incomplete (complete=%v err=%v)", wrongExpectationPass, err)
	}

	missingExpectationAnswer := challenge.CheckDefinitionAnswer{QueryID: checkAnswer.QueryID}
	missingExpectationResult := challenge.EvaluateCheckDefinition(*checkPart.CheckDefinition, missingExpectationAnswer, observation(req, challengeID, "check"))
	receipt["missingExpectation"] = missingExpectationResult
	if missingExpectationResult.Outcome == challenge.OutcomePass || missingExpectationResult.ExecutionStatus != challenge.StatusError {
		fail("mixed: missing typed expectation must be an error/unknown outcome")
	}
	missingExpectationPass, _, err := complete(manifest, []challenge.PartOutcome{
		sqlResult.AsOutcome(sqlPart),
		structuredResult.AsOutcome(structuredPart),
		missingExpectationResult.AsOutcome(checkPart),
	})
	if err != nil || missingExpectationPass {
		fail("mixed: missing typed expectation must leave the attempt incomplete (complete=%v err=%v)", missingExpectationPass, err)
	}

	// Guard the expectation shape the learner must author: a set-scoped
	// row-count validator with an integer expected value and a declared severity.
	var expectation detective.Validator = checkPart.CheckDefinition.Expectation
	receipt["authoredExpectation"] = map[string]any{
		"id":       expectation.ID,
		"scope":    expectation.Scope,
		"kind":     expectation.Kind,
		"severity": expectation.Severity,
		"expected": expectation.Expected,
	}
	if expectation.ID == "" || expectation.Scope != "set" || expectation.Kind != "row-count" ||
		expectation.Severity == "" || expectation.Expected == nil || expectation.Expected.Type != investigation.ValueTypeInteger {
		fail("mixed: authored expectation is not a typed set row-count")
	}

	var _ = detective.Validator{}
}

func contains(values []string, want string) bool {
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}
'''


def verify_core(project_dir: Path = PROJECT_DIR, core_dir: Path | None = None) -> dict:
    core_dir = core_dir or find_core_dir()
    if core_dir is None:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "no sibling datatug-core worktree found",
        }
    request = build_core_request(project_dir)
    with tempfile.TemporaryDirectory(prefix="challenge-e2e-core-") as temp:
        temp_dir = Path(temp)
        (temp_dir / "go.mod").write_text(
            "module challengeqa/verify\n\n"
            "go 1.27.0\n\n"
            "require github.com/datatug/datatug-core v0.0.0\n\n"
            f"replace github.com/datatug/datatug-core => {core_dir.as_posix()}\n",
            encoding="utf-8",
        )
        (temp_dir / "main.go").write_text(CORE_HELPER_SOURCE, encoding="utf-8")
        request_path = temp_dir / "request.json"
        request_path.write_text(json.dumps(request, sort_keys=True), encoding="utf-8")
        env = dict(os.environ)
        env.setdefault("GOFLAGS", "-mod=mod")
        try:
            completed = subprocess.run(
                ["go", "run", "-mod=mod", ".", str(request_path)],
                cwd=temp_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return {
                "ok": False,
                "status": "error",
                "coreDir": str(core_dir),
                "error": str(error),
            }
        stdout = completed.stdout.strip()
        if not stdout:
            return {
                "ok": False,
                "status": "error",
                "coreDir": str(core_dir),
                "exitCode": completed.returncode,
                "stderr": completed.stderr,
            }
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as error:
            return {
                "ok": False,
                "status": "error",
                "coreDir": str(core_dir),
                "exitCode": completed.returncode,
                "error": f"helper output is not JSON: {error}",
                "stdout": stdout,
                "stderr": completed.stderr,
            }
        result["status"] = "ok" if result.get("ok") else "failed"
        result["coreDir"] = str(core_dir)
        result["exitCode"] = completed.returncode
        revision = subprocess.run(
            ["git", "-C", str(core_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        result["coreRevision"] = revision.stdout.strip() if revision.returncode == 0 else None
        schema_status = subprocess.run(
            [
                "git",
                "-C",
                str(core_dir),
                "status",
                "--porcelain",
                "--",
                "pkg/challenge/manifest.go",
                "pkg/challenge/bundle.go",
                "pkg/challenge/oracle.go",
                "pkg/challenge/checkdef.go",
                "pkg/challenge/structured.go",
                "pkg/challenge/paths.go",
                "pkg/challenge/limits.go",
            ],
            capture_output=True,
            text=True,
        )
        result["coreOpenSchemaClean"] = (
            schema_status.returncode == 0 and not schema_status.stdout.strip()
        )
        result["coreOpenSchemaStatus"] = schema_status.stdout.splitlines()
        if completed.stderr:
            result["stderr"] = completed.stderr
        return result


def verify(
    project_dir: Path = PROJECT_DIR,
    *,
    require_core: bool = False,
    core_dir: Path | None = None,
) -> dict:
    project_dir = Path(project_dir)
    errors: list[str] = []

    first = build_assets(project_dir)
    second = build_assets(project_dir)
    if first != second:
        errors.append("authoring is not deterministic across two in-memory builds")

    authored = {}
    for path, expected in first.items():
        relative = path.relative_to(project_dir).as_posix()
        authored[relative] = {
            "bytes": len(expected),
            "sha256": sha256_bytes(expected),
        }
        if not path.exists():
            errors.append(f"authored asset missing: {relative}")
            continue
        observed = path.read_bytes()
        if observed != expected:
            errors.append(f"authored asset differs from deterministic output: {relative}")

    manifests = {}
    for challenge_id in build_manifests():
        manifest_path = project_dir / "challenges" / challenge_id / "1.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        manifests[challenge_id] = manifest
        verify_manifest_semantics(manifest, project_dir, errors)

    # Only the four expected revisions are authored under this project.
    expected_manifests = {
        f"challenges/{challenge_id}/1.json" for challenge_id in build_manifests()
    }
    observed_manifests = {
        path.relative_to(project_dir).as_posix()
        for path in project_dir.glob("challenges/*/1.json")
    }
    if observed_manifests != expected_manifests:
        errors.append(
            f"challenge manifest set drift: {sorted(observed_manifests)} != "
            f"{sorted(expected_manifests)}"
        )

    original = verify_original_assets(errors)
    catalogue = verify_no_catalogue_registration(errors)

    core = None
    if core_dir is not None or require_core or find_core_dir() is not None:
        core = verify_core(project_dir, core_dir)
        if not core.get("ok"):
            if require_core:
                errors.append("Core Open/grading verification failed: " + json.dumps(core, sort_keys=True))
            else:
                errors.append("Core Open/grading verification failed (optional): " + json.dumps(core, sort_keys=True))

    report = {
        "ok": not errors,
        "projectDir": str(project_dir),
        "qaOnly": True,
        "publicRegistration": catalogue,
        "originalDemoProjectAssets": original,
        "promptEngine": ENGINE,
        "referenceExecution": {
            "runtime": "Python native sqlite3",
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "browserWasmAcceptance": False,
            "note": (
                "Reference rows and Check outcomes are proven with native Python "
                "SQLite. This is not the Chromium/Firefox/WebKit WASM acceptance "
                "journey; Task 4 must use the built WASM runtime."
            ),
        },
        "authored": authored,
        "manifests": {
            challenge_id: {
                "revision": manifest["revision"],
                "timing": manifest["timing"],
                "allowedOperation": manifest["allowedOperation"],
                "parts": [
                    {
                        "id": part["id"],
                        "answerKind": part["answerKind"],
                        "required": part["required"],
                    }
                    for part in manifest["parts"]
                ],
                "fixtures": [
                    {
                        "id": fixture["id"],
                        "sha256": fixture["sha256"],
                        "bytes": fixture["bytes"],
                    }
                    for fixture in manifest["fixtureSuite"]["fixtures"]
                ],
            }
            for challenge_id, manifest in sorted(manifests.items())
        },
        "core": core,
        "errors": errors,
    }
    return report


def _print_report(report: dict):
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "projectDir": report["projectDir"],
                "manifests": report["manifests"],
                "authored": report["authored"],
                "originalDemoProjectAssets": report["originalDemoProjectAssets"],
                "referenceExecution": report["referenceExecution"],
                "coreOpenStatus": (report.get("core") or {}).get("status"),
                "coreRevision": (report.get("core") or {}).get("coreRevision"),
                "coreOpenSchemaClean": (report.get("core") or {}).get(
                    "coreOpenSchemaClean"
                ),
                "coreOpenReceipts": (report.get("core") or {}).get("receipts"),
                "errors": report["errors"],
            },
            indent=2,
            sort_keys=True,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["regenerate", "verify"])
    parser.add_argument("--project-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--core-dir", type=Path, default=None)
    parser.add_argument(
        "--require-core",
        action="store_true",
        help="fail verification when Core Open/grading cannot run from a sibling worktree",
    )
    args = parser.parse_args(argv)

    if args.command == "regenerate":
        report = regenerate(args.project_dir)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    report = verify(
        args.project_dir,
        require_core=args.require_core,
        core_dir=args.core_dir,
    )
    _print_report(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
