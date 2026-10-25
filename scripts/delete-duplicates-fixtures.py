#!/usr/bin/env python3
"""Regenerate or verify the internal delete-duplicates challenge fixture suite.

The committed SQLite files under demo-project-1/challenges/delete-duplicates/
are immutable inputs. Normal verification checks their SHA-256 bytes, reads them
through read-only connections, and executes every reference/mutation on a fresh
in-memory copy. It never rewrites a committed fixture. Regeneration is an
explicit action and may change bytes when SQLite's own library version changes,
because SQLite embeds its library version in the database header.

The internal index records fixture bytes and oracle receipts. The same trusted
tool also emits the checked public revision manifest,
`challenges/delete-duplicates/1.json`, from those verified fixtures. The
manifest wire shape comes from the accepted Core contract
`github.com/datatug/datatug-core@0f250aa pkg/challenge`, not from this tool.
The Python checks validate fixture semantics only; they do not establish
browser acceptance of the challenge. Reference and mutation SQL runs only
against disposable in-memory copies for fixture verification; this tool is not
a learner SQL service and exposes no execution endpoint.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
import platform
from pathlib import Path
import random
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE_DIR = ROOT / "demo-project-1/challenges/delete-duplicates"
INDEX_FILENAME = "suite.json"
MANIFEST_FILENAME = "1.json"

FORMAT = "datatug.internal.challenge-fixture-suite/v1"
KIND = "internal-fixture-suite-index"
CHALLENGE_ID = "delete-duplicates"
GENERATED_SEED = 20261025
GENERATED_VARIANTS = 3

# The public revision wire shape is owned by Core. This tool only populates the
# accepted closed schema; it must never add fields of its own.
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_GRADING_VERSION = "challenge-grading-v1"
MANIFEST_REVISION = 1
MANIFEST_TITLE = "Delete duplicate customers"
MANIFEST_OBJECTIVE = (
    "Delete duplicate customer rows while preserving the lowest numeric id for "
    "each exact email value. BINARY equality is significant, so case and "
    "whitespace differences remain separate groups and NULL is one group. "
    "created_at is evidence only, and unrelated_records must survive unchanged."
)
MANIFEST_DIFFICULTY = "intro"
MANIFEST_TIMING = "optional"
MANIFEST_FIXTURE_SUITE_ID = "delete-duplicates-v1"
MANIFEST_PART_ID = "delete-duplicates"
MANIFEST_PART_TITLE = "Delete duplicate customer rows"
MANIFEST_ENGINE = {
    "package": "@sqlite.org/sqlite-wasm",
    "version": "3.54.1-build1",
    "sqliteVersion": "3.54.1",
}
MANIFEST_INVARIANT = {
    "id": "keep-lowest-id",
    "kind": "group-min",
    "table": "customers",
    "groupBy": ["email"],
    "column": "id",
    "description": (
        "Preserve the lowest numeric id per exact BINARY email value; NULL is "
        "one group and created_at is not the retention rule."
    ),
}
MANIFEST_HINTS = [
    {
        "id": "hint-1",
        "text": (
            "Find the email values that occur more than once. Compare the exact "
            "stored text: case, leading or trailing spaces and inner spaces all "
            "make different values, and NULL is one group."
        ),
    },
    {
        "id": "hint-2",
        "text": (
            "The survivor is the row with the lowest numeric id, not the earliest "
            "created_at and not the most recently created row."
        ),
    },
    {
        "id": "hint-3",
        "text": (
            "Do not lowercase or trim the email. SQLite BINARY equality is the "
            "declared grouping, so a case or whitespace collapse deletes rows that "
            "must remain."
        ),
    },
    {
        "id": "hint-4",
        "text": (
            "Delete a row only when another row in the same exact email group has a "
            "lower id. The statement must be safe to apply twice and must not touch "
            "unrelated_records."
        ),
    },
]


SCHEMA_SQL = """CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    email TEXT COLLATE BINARY,
    created_at TEXT NOT NULL
);

CREATE TABLE unrelated_records (
    id INTEGER PRIMARY KEY,
    code TEXT COLLATE BINARY NOT NULL,
    note TEXT NOT NULL
);
"""

CUSTOMER_COLUMNS = [
    {
        "name": "id",
        "declaredType": "INTEGER",
        "notNull": False,
        "primaryKey": True,
    },
    {
        "name": "email",
        "declaredType": "TEXT",
        "notNull": False,
        "primaryKey": False,
        "collation": "BINARY",
    },
    {
        "name": "created_at",
        "declaredType": "TEXT",
        "notNull": True,
        "primaryKey": False,
    },
]

UNRELATED_COLUMNS = [
    {
        "name": "id",
        "declaredType": "INTEGER",
        "notNull": False,
        "primaryKey": True,
    },
    {
        "name": "code",
        "declaredType": "TEXT",
        "notNull": True,
        "primaryKey": False,
        "collation": "BINARY",
    },
    {
        "name": "note",
        "declaredType": "TEXT",
        "notNull": True,
        "primaryKey": False,
    },
]

SCHEMA_TABLES = [
    {"name": "customers", "columns": CUSTOMER_COLUMNS},
    {"name": "unrelated_records", "columns": UNRELATED_COLUMNS},
]

REQUIRED_COVERAGE = {
    "basic-duplicates": "At least one exact duplicate group is present.",
    "no-duplicates": "A fixture with no duplicate group, including NULL and empty string.",
    "multiple-groups": "More than one duplicate group is exercised together.",
    "three-plus-member-group": "A duplicate group with three or more members.",
    "unrelated-records": "An unrelated table with rows that must not change.",
    "null-duplicate-group": "NULL email values form one duplicate group.",
    "empty-string-duplicate-group": "Empty-string email values form their own group.",
    "null-vs-empty-distinct": "NULL and empty string are distinct grouping keys.",
    "nonsequential-ids": "Primary-key values are not a contiguous insertion sequence.",
    "nonsequential-insertion-order": "Rows are inserted in an order unrelated to id order.",
    "earliest-timestamp-higher-id": "The earliest created_at in a duplicate group has a higher id.",
    "created-at-not-retention-rule": "A fixture proves created_at is not the survivor rule.",
    "case-sensitive-email": "Email comparison preserves case.",
    "whitespace-sensitive-email": "Email comparison preserves leading, trailing and inner whitespace.",
    "exact-binary-equality": "Duplicates are defined by SQLite BINARY equality.",
    "generated-fixed-seed": "A deterministic generated variant with a recorded fixed seed.",
}

REFERENCE_SOLUTIONS = [
    {
        "id": "null-safe-exists-lowest-id",
        "description": (
            "Delete every row that has a lower-id row in the same exact BINARY email "
            "group. IS keeps NULL as one group."
        ),
        "sql": """DELETE FROM customers
WHERE EXISTS (
    SELECT 1
    FROM customers AS keeper
    WHERE keeper.email IS customers.email COLLATE BINARY
      AND keeper.id < customers.id
);
""",
    },
    {
        "id": "grouped-min-lowest-id",
        "description": (
            "Group by the email column (BINARY collation) and keep the minimum numeric "
            "id in each group, including the NULL group."
        ),
        "sql": """DELETE FROM customers
WHERE id NOT IN (
    SELECT MIN(id)
    FROM customers
    GROUP BY email
);
""",
    },
    {
        "id": "window-ranked-lowest-id",
        "description": (
            "Rank rows within each email group by id and delete every rank above one. "
            "This is a window-function alternative to the grouped MIN formulation."
        ),
        "sql": """DELETE FROM customers
WHERE id IN (
    SELECT id
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (PARTITION BY email ORDER BY id) AS duplicate_rank
        FROM customers
    ) AS ranked
    WHERE duplicate_rank > 1
);
""",
    },
]

# The Core contract permits at most one reference answer per part. Revision 1
# therefore pins the canonical NULL-safe EXISTS formulation; the other verified
# formulations remain internal generator receipts, not additional wire answers.
MANIFEST_REFERENCE_SQL = REFERENCE_SOLUTIONS[0]["sql"]

MUTATION_SOLUTIONS = [
    {
        "id": "delete-all",
        "description": "Delete every customer row instead of deduplicating.",
        "sql": "DELETE FROM customers;\n",
    },
    {
        "id": "keep-highest-id",
        "description": "Invert the id comparison and keep the highest id per email group.",
        "sql": """DELETE FROM customers
WHERE EXISTS (
    SELECT 1
    FROM customers AS keeper
    WHERE keeper.email IS customers.email COLLATE BINARY
      AND keeper.id > customers.id
);
""",
    },
    {
        "id": "keep-earliest-created-at",
        "description": (
            "Treat created_at as the retention rule and keep the earliest timestamp. "
            "The nonsequential fixture has an earlier timestamp on a higher id."
        ),
        "sql": """DELETE FROM customers
WHERE EXISTS (
    SELECT 1
    FROM customers AS keeper
    WHERE keeper.email IS customers.email COLLATE BINARY
      AND keeper.created_at < customers.created_at
);
""",
    },
    {
        "id": "ignore-null-group-equality",
        "description": (
            "Use plain equality instead of NULL-safe IS, so the NULL duplicate group "
            "is never deduplicated."
        ),
        "sql": """DELETE FROM customers
WHERE EXISTS (
    SELECT 1
    FROM customers AS keeper
    WHERE keeper.email = customers.email COLLATE BINARY
      AND keeper.id < customers.id
);
""",
    },
    {
        "id": "case-trim-collapse",
        "description": (
            "Collapse case and surrounding whitespace before comparing emails, which "
            "is not the declared exact BINARY rule."
        ),
        "sql": """DELETE FROM customers
WHERE EXISTS (
    SELECT 1
    FROM customers AS keeper
    WHERE keeper.email IS NOT NULL
      AND customers.email IS NOT NULL
      AND lower(trim(keeper.email)) = lower(trim(customers.email))
      AND keeper.id < customers.id
);
""",
    },
    {
        "id": "delete-one-duplicate",
        "description": (
            "Delete only the highest-id row among all duplicated emails, leaving every "
            "other duplicate in place."
        ),
        "sql": """DELETE FROM customers
WHERE id = (
    SELECT MAX(candidate.id)
    FROM customers AS candidate
    WHERE EXISTS (
        SELECT 1
        FROM customers AS other
        WHERE other.email IS candidate.email COLLATE BINARY
          AND other.id <> candidate.id
    )
);
""",
    },
    {
        "id": "collateral-unrelated-delete",
        "description": (
            "Apply the correct customer deduplication but also delete the unrelated "
            "table. The unrelated rows prove collateral writes are graded."
        ),
        "sql": """DELETE FROM customers
WHERE EXISTS (
    SELECT 1
    FROM customers AS keeper
    WHERE keeper.email IS customers.email COLLATE BINARY
      AND keeper.id < customers.id
);

DELETE FROM unrelated_records;
""",
    },
]


def _unrelated(prefix: str, count: int):
    return [
        (
            index,
            f"SKU-{prefix}-{index}",
            f"Synthetic unrelated row {index} for {prefix}; must survive deduplication.",
        )
        for index in range(1, count + 1)
    ]


AUTHORED_FIXTURE_SPECS = [
    {
        "id": "basic",
        "filename": "basic.db",
        "label": "Basic duplicate groups",
        "purpose": (
            "Two exact duplicate pairs and one unique email. The earliest created_at "
            "in the first pair belongs to the higher id."
        ),
        "properties": [
            "basic-duplicates",
            "multiple-groups",
            "earliest-timestamp-higher-id",
            "unrelated-records",
        ],
        "generator": {"kind": "authored"},
        "customers": [
            (10, "ada@example.com", "2024-01-01T09:00:00Z"),
            (3, "ada@example.com", "2024-01-03T09:00:00Z"),
            (2, "bob@example.com", "2024-02-01T09:00:00Z"),
            (7, "bob@example.com", "2024-02-02T09:00:00Z"),
            (5, "cy@example.com", "2024-03-01T09:00:00Z"),
        ],
        "unrelated": _unrelated("BASIC", 2),
    },
    {
        "id": "no-duplicates",
        "filename": "no-duplicates.db",
        "label": "No duplicate groups",
        "purpose": (
            "Unique emails plus one NULL and one empty string. A correct statement "
            "must be a no-op."
        ),
        "properties": [
            "no-duplicates",
            "null-vs-empty-distinct",
            "unrelated-records",
        ],
        "generator": {"kind": "authored"},
        "customers": [
            (9, "dana@example.com", "2024-01-01T00:00:00Z"),
            (4, "eli@example.com", "2024-01-02T00:00:00Z"),
            (1, "fay@example.com", "2024-01-03T00:00:00Z"),
            (6, None, "2024-01-04T00:00:00Z"),
            (2, "", "2024-01-05T00:00:00Z"),
        ],
        "unrelated": _unrelated("NO-DUPLICATES", 3),
    },
    {
        "id": "multi-group",
        "filename": "multi-group.db",
        "label": "Multiple groups including three-plus members",
        "purpose": (
            "Four duplicate groups, two of them with three or more members, plus a "
            "unique row. Several groups have an earlier timestamp on a higher id."
        ),
        "properties": [
            "multiple-groups",
            "three-plus-member-group",
            "nonsequential-ids",
            "earliest-timestamp-higher-id",
            "unrelated-records",
        ],
        "generator": {"kind": "authored"},
        "customers": [
            (30, "group-c@example.com", "2024-05-01T00:00:00Z"),
            (11, "group-d@example.com", "2024-06-02T00:00:00Z"),
            (3, "group-a@example.com", "2024-02-02T00:00:00Z"),
            (19, "group-c@example.com", "2024-05-03T00:00:00Z"),
            (8, "group-b@example.com", "2024-04-04T00:00:00Z"),
            (25, "unique@example.com", "2024-07-07T00:00:00Z"),
            (14, "group-a@example.com", "2024-03-03T00:00:00Z"),
            (2, "group-c@example.com", "2024-05-04T00:00:00Z"),
            (12, "group-b@example.com", "2024-04-03T00:00:00Z"),
            (20, "group-a@example.com", "2024-01-01T00:00:00Z"),
            (7, "group-c@example.com", "2024-05-02T00:00:00Z"),
            (5, "group-d@example.com", "2024-06-01T00:00:00Z"),
        ],
        "unrelated": _unrelated("MULTI", 3),
    },
    {
        "id": "nonsequential-created-at",
        "filename": "nonsequential-created-at.db",
        "label": "Nonsequential ids where created_at disagrees with id",
        "purpose": (
            "Every duplicate group has its earliest created_at on a higher id. The "
            "insertion order is unrelated to id order, exposing timestamp-versus-id "
            "retention ambiguity."
        ),
        "properties": [
            "multiple-groups",
            "nonsequential-ids",
            "nonsequential-insertion-order",
            "earliest-timestamp-higher-id",
            "created-at-not-retention-rule",
            "unrelated-records",
        ],
        "generator": {"kind": "authored"},
        "customers": [
            (100, "early@example.com", "2024-01-01T00:00:00Z"),
            (50, "other@example.com", "2024-04-01T00:00:00Z"),
            (2, "early@example.com", "2024-09-01T00:00:00Z"),
            (41, "unique@example.com", "2024-02-02T00:00:00Z"),
            (9, "later@example.com", "2024-03-03T00:00:00Z"),
            (7, "other@example.com", "2024-08-01T00:00:00Z"),
            (3, "later@example.com", "2024-07-07T00:00:00Z"),
        ],
        "unrelated": _unrelated("NONSEQUENTIAL", 2),
    },
    {
        "id": "null-empty",
        "filename": "null-empty.db",
        "label": "NULL and empty-string duplicate groups",
        "purpose": (
            "A three-member NULL group, a three-member empty-string group and the "
            "string 'NULL' as a distinct value. Plain equality leaves the NULL group "
            "undeduplicated."
        ),
        "properties": [
            "multiple-groups",
            "null-duplicate-group",
            "empty-string-duplicate-group",
            "null-vs-empty-distinct",
            "unrelated-records",
        ],
        "generator": {"kind": "authored"},
        "customers": [
            (9, None, "2024-01-01T00:00:00Z"),
            (7, "", "2024-02-01T00:00:00Z"),
            (4, None, "2024-01-02T00:00:00Z"),
            (2, "", "2024-02-02T00:00:00Z"),
            (12, None, "2024-01-03T00:00:00Z"),
            (5, "person@example.com", "2024-03-01T00:00:00Z"),
            (15, "", "2024-02-03T00:00:00Z"),
            (1, "NULL", "2024-03-02T00:00:00Z"),
        ],
        "unrelated": _unrelated("NULL-EMPTY", 2),
    },
    {
        "id": "case-whitespace",
        "filename": "case-whitespace.db",
        "label": "Case and whitespace distinctions",
        "purpose": (
            "Exact duplicates coexist with case-only and whitespace-only variants that "
            "must survive as separate email groups. A lower/trim collapse deletes rows "
            "the BINARY rule keeps."
        ),
        "properties": [
            "multiple-groups",
            "case-sensitive-email",
            "whitespace-sensitive-email",
            "exact-binary-equality",
            "unrelated-records",
        ],
        "generator": {"kind": "authored"},
        "customers": [
            (8, "case@example.com", "2024-01-02T00:00:00Z"),
            (11, " padded@example.com", "2024-02-03T00:00:00Z"),
            (3, "case@example.com", "2024-01-01T00:00:00Z"),
            (15, "two words@example.com", "2024-03-02T00:00:00Z"),
            (6, "Case@Example.com", "2024-01-03T00:00:00Z"),
            (12, "padded@example.com ", "2024-02-04T00:00:00Z"),
            (5, "padded@example.com", "2024-02-01T00:00:00Z"),
            (2, "CASE@example.com", "2024-01-04T00:00:00Z"),
            (13, "two  words@example.com", "2024-03-03T00:00:00Z"),
            (9, "padded@example.com", "2024-02-02T00:00:00Z"),
            (14, "two words@example.com", "2024-03-01T00:00:00Z"),
        ],
        "unrelated": _unrelated("CASE-WHITESPACE", 2),
    },
]


def generated_fixture_spec(variant: int) -> dict:
    """Build one deterministic generated variant from the fixed suite seed."""
    if variant < 0 or variant >= GENERATED_VARIANTS:
        raise ValueError(f"variant must be in [0, {GENERATED_VARIANTS})")
    variant_seed = GENERATED_SEED + variant
    rng = random.Random(variant_seed)
    prefix = f"v{variant + 1:02d}"
    alpha = f"alpha.{prefix}@example.com"
    beta = f"beta.{prefix}@example.com"
    gamma = f"gamma.{prefix}@example.com"
    lower_case = f"case.{prefix}@example.com"
    upper_case = f"Case.{prefix}@Example.com"
    trim_email = f"trim.{prefix}@example.com"

    emails: list[str | None] = []
    emails += [alpha] * rng.choice([2, 3, 4])
    emails += [beta] * rng.choice([2, 3])
    emails += [gamma] * 3
    emails += [None] * rng.choice([2, 3])
    emails += [""] * 2
    emails += [lower_case] * 2
    emails += [upper_case]
    emails += [trim_email] * 2
    emails += [f" leading.{prefix}@example.com"]
    emails += [f"trailing.{prefix}@example.com "]
    emails += [f"unique.{prefix}@example.com", f"another.{prefix}@example.com"]
    emails += ["NULL"]
    rng.shuffle(emails)

    ids = rng.sample(range(1, 200), len(emails))
    dates = [
        f"2025-{3 + (index // 27):02d}-{1 + (index % 27):02d}T{index % 24:02d}:00:00Z"
        for index in range(len(emails))
    ]
    records = [
        {"id": row_id, "email": email, "created_at": created_at}
        for row_id, email, created_at in zip(ids, emails, dates)
    ]

    # Guarantee the timestamp-versus-id ambiguity in every generated variant:
    # the highest id in the alpha group gets the earliest created_at.
    alpha_records = sorted(
        [record for record in records if record["email"] == alpha],
        key=lambda record: record["id"],
        reverse=True,
    )
    for rank, record in enumerate(alpha_records):
        record["created_at"] = f"2025-01-{rank + 1:02d}T00:00:00Z"

    rng.shuffle(records)
    insertion = [record["id"] for record in records]
    if insertion == sorted(insertion):
        records = records[1:] + records[:1]

    unrelated_count = rng.randint(2, 4)
    return {
        "id": f"generated-variant-{variant + 1:02d}",
        "filename": f"generated-variant-{variant + 1:02d}.db",
        "label": f"Deterministic generated variant {variant + 1}",
        "purpose": (
            "A fixed-seed generated mix of duplicate groups, NULL, empty string, "
            "case/whitespace variants, nonsequential ids, timestamp ambiguity and "
            "unrelated rows."
        ),
        "properties": [
            "basic-duplicates",
            "multiple-groups",
            "three-plus-member-group",
            "null-duplicate-group",
            "empty-string-duplicate-group",
            "null-vs-empty-distinct",
            "nonsequential-ids",
            "nonsequential-insertion-order",
            "earliest-timestamp-higher-id",
            "created-at-not-retention-rule",
            "case-sensitive-email",
            "whitespace-sensitive-email",
            "exact-binary-equality",
            "generated-fixed-seed",
            "unrelated-records",
        ],
        "generator": {
            "kind": "fixed-seed",
            "algorithm": "python-random-mt19937",
            "seed": GENERATED_SEED,
            "variantSeed": variant_seed,
            "variant": variant + 1,
        },
        "customers": [
            (record["id"], record["email"], record["created_at"]) for record in records
        ],
        "unrelated": _unrelated(f"GENERATED-{prefix}", unrelated_count),
    }


def all_fixture_specs() -> list[dict]:
    return [
        *AUTHORED_FIXTURE_SPECS,
        *[generated_fixture_spec(index) for index in range(GENERATED_VARIANTS)],
    ]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def rows_from_json(rows) -> list[tuple]:
    return [tuple(row) for row in rows]


def expected_survivors(rows) -> list[tuple]:
    """Independent Python oracle: keep MIN(id) per exact email, NULL is a group."""
    groups: dict[str | None, list[tuple]] = {}
    for row in rows:
        groups.setdefault(row[1], []).append(tuple(row))
    survivors = [min(group, key=lambda row: row[0]) for group in groups.values()]
    return sorted(survivors, key=lambda row: row[0])


def duplicate_emails(rows) -> list[str | None]:
    counts = Counter(row[1] for row in rows)
    duplicates = [email for email, count in counts.items() if count > 1]
    return sorted(
        duplicates,
        key=lambda email: (email is not None, "" if email is None else email),
    )


@contextmanager
def fresh_copy(path: Path):
    """Yield a fresh in-memory copy; the committed source is opened read-only."""
    path = Path(path)
    uri = f"file:{quote(path.resolve().as_posix())}?mode=ro&immutable=1"
    source = sqlite3.connect(uri, uri=True)
    memory = sqlite3.connect(":memory:")
    try:
        source.backup(memory)
    finally:
        source.close()
    try:
        memory.execute("PRAGMA foreign_keys=ON")
        yield memory
    finally:
        memory.close()


def read_customers(db: sqlite3.Connection) -> list[tuple]:
    return [
        tuple(row)
        for row in db.execute(
            "SELECT id, email, created_at FROM customers ORDER BY id"
        ).fetchall()
    ]


def read_unrelated(db: sqlite3.Connection) -> list[tuple]:
    return [
        tuple(row)
        for row in db.execute(
            "SELECT id, code, note FROM unrelated_records ORDER BY id"
        ).fetchall()
    ]


def inspect_schema(db: sqlite3.Connection) -> dict:
    tables = {}
    for table_name in ("customers", "unrelated_records"):
        info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        sql_row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        tables[table_name] = {
            "columns": [
                {
                    "name": row[1],
                    "declaredType": row[2],
                    "notNull": bool(row[3]),
                    "primaryKey": bool(row[5]),
                }
                for row in info
            ],
            "sql": sql_row[0] if sql_row else "",
        }
    return tables


def _column_signature(column: dict) -> tuple:
    return (
        column["name"],
        column.get("declaredType", "").upper(),
        bool(column.get("notNull", False)),
        bool(column.get("primaryKey", False)),
    )


def _validate_schema(db: sqlite3.Connection, expected_tables: list[dict]) -> list[str]:
    errors = []
    actual = inspect_schema(db)
    expected_names = [table["name"] for table in expected_tables]
    if set(actual) != set(expected_names):
        errors.append(f"schema tables differ: {sorted(actual)} != {sorted(expected_names)}")
        return errors
    object_rows = db.execute(
        "SELECT type, name FROM sqlite_master WHERE type IN ('view', 'trigger') ORDER BY name"
    ).fetchall()
    if object_rows:
        errors.append(f"unexpected views/triggers: {object_rows}")
    for table in expected_tables:
        name = table["name"]
        actual_columns = actual[name]["columns"]
        expected_columns = table["columns"]
        if [column["name"] for column in actual_columns] != [
            column["name"] for column in expected_columns
        ]:
            errors.append(f"{name}: column order differs")
            continue
        for actual_column, expected_column in zip(actual_columns, expected_columns):
            if _column_signature(actual_column) != _column_signature(expected_column):
                errors.append(
                    f"{name}.{expected_column['name']}: "
                    f"{_column_signature(actual_column)} != "
                    f"{_column_signature(expected_column)}"
                )
            if expected_column.get("collation") == "BINARY":
                if "COLLATE BINARY" not in actual[name]["sql"].upper():
                    errors.append(
                        f"{name}.{expected_column['name']}: missing COLLATE BINARY"
                    )
    return errors


def run_sql(
    suite_dir: Path,
    fixture: dict,
    sql: str,
    *,
    apply_twice: bool = False,
) -> dict:
    with fresh_copy(Path(suite_dir) / fixture["relativePath"]) as db:
        db.executescript(sql)
        if apply_twice:
            db.executescript(sql)
        return {
            "customers": read_customers(db),
            "unrelated": read_unrelated(db),
        }


def _typed_customers(rows) -> bool:
    return all(
        len(row) == 3
        and type(row[0]) is int
        and (row[1] is None or type(row[1]) is str)
        and type(row[2]) is str
        for row in rows
    )


def _typed_unrelated(rows) -> bool:
    return all(
        len(row) == 3
        and type(row[0]) is int
        and type(row[1]) is str
        and type(row[2]) is str
        for row in rows
    )


def compare_state(actual: dict, fixture: dict) -> tuple[list[str], dict]:
    expected_customers = rows_from_json(fixture["expected"]["rows"])
    expected_unrelated = rows_from_json(fixture["unrelated"]["expectedRows"])
    actual_customers = [tuple(row) for row in actual["customers"]]
    actual_unrelated = [tuple(row) for row in actual["unrelated"]]

    violations = []
    details: dict = {}
    if not _typed_customers(actual_customers):
        violations.append("customers.value-type-mismatch")
    if not _typed_unrelated(actual_unrelated):
        violations.append("unrelated.value-type-mismatch")

    missing = [row for row in expected_customers if row not in actual_customers]
    unexpected = [row for row in actual_customers if row not in expected_customers]
    if missing:
        violations.append("customers.expected-survivor-missing")
        details["missingIds"] = sorted({row[0] for row in missing})
    if unexpected:
        violations.append("customers.unexpected-survivor-present")
        details["unexpectedIds"] = sorted({row[0] for row in unexpected})
    if len(actual_customers) != len(expected_customers):
        violations.append("customers.row-count-mismatch")
        details["rowCount"] = len(actual_customers)
        details["expectedRowCount"] = len(expected_customers)
    expected_ids = {row[0] for row in expected_customers}
    actual_ids = {row[0] for row in actual_customers}
    if expected_ids == actual_ids and actual_customers != expected_customers:
        violations.append("customers.survivor-value-mismatch")

    remaining = duplicate_emails(actual_customers)
    if remaining:
        violations.append("customers.duplicate-email-group-remaining")
        details["duplicateEmails"] = remaining
    if actual_unrelated != expected_unrelated:
        violations.append("unrelated.rows-changed")
    return violations, details


def compute_coverage(fixtures: list[dict]) -> dict:
    coverage = {property_name: [] for property_name in REQUIRED_COVERAGE}
    for fixture in fixtures:
        for property_name in fixture.get("properties", []):
            coverage.setdefault(property_name, []).append(fixture["id"])
    return {
        property_name: sorted(fixture_ids)
        for property_name, fixture_ids in sorted(coverage.items())
    }


def compute_receipts(
    suite_dir: Path,
    fixtures: list[dict],
    references: list[dict],
    mutations: list[dict],
) -> dict:
    reference_receipts: dict[str, dict[str, dict]] = {}
    for reference in references:
        fixture_receipts = {}
        for fixture in fixtures:
            first = run_sql(suite_dir, fixture, reference["sql"])
            twice = run_sql(suite_dir, fixture, reference["sql"], apply_twice=True)
            first_violations, first_details = compare_state(first, fixture)
            twice_violations, _ = compare_state(twice, fixture)
            idempotent = first == twice
            violations = list(dict.fromkeys(first_violations + twice_violations))
            if not idempotent:
                violations.append("idempotency.final-state-changed")
            receipt = {
                "result": "pass" if not violations else "fail",
                "idempotent": idempotent,
            }
            if violations:
                receipt["violations"] = violations
                receipt.update(first_details)
            fixture_receipts[fixture["id"]] = receipt
        reference_receipts[reference["id"]] = fixture_receipts

    mutation_receipts: dict[str, dict[str, dict]] = {}
    for mutation in mutations:
        fixture_receipts = {}
        for fixture in fixtures:
            actual = run_sql(suite_dir, fixture, mutation["sql"])
            violations, details = compare_state(actual, fixture)
            receipt = {"result": "pass" if not violations else "fail"}
            if violations:
                receipt["violations"] = violations
                receipt.update(details)
            fixture_receipts[fixture["id"]] = receipt
        mutation_receipts[mutation["id"]] = fixture_receipts

    reference_checks = len(references) * len(fixtures)
    reference_passes = sum(
        1
        for reference in references
        for fixture in fixtures
        if reference_receipts[reference["id"]][fixture["id"]]["result"] == "pass"
        and reference_receipts[reference["id"]][fixture["id"]]["idempotent"]
    )
    rejected = [
        mutation["id"]
        for mutation in mutations
        if any(
            mutation_receipts[mutation["id"]][fixture["id"]]["result"] == "fail"
            for fixture in fixtures
        )
    ]
    undetected = [mutation["id"] for mutation in mutations if mutation["id"] not in rejected]
    summary = {
        "fixtures": len(fixtures),
        "referenceSolutions": len(references),
        "referenceChecks": reference_checks,
        "referencePasses": reference_passes,
        "mutationCases": len(mutations),
        "mutationChecks": len(mutations) * len(fixtures),
        "rejectedMutationCases": len(rejected),
        "rejectedMutations": rejected,
        "undetectedMutations": undetected,
    }
    return {
        "reference": reference_receipts,
        "mutation": mutation_receipts,
        "summary": summary,
    }


def _write_fixture(path: Path, spec: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    try:
        db.execute("PRAGMA page_size=4096")
        db.execute("PRAGMA journal_mode=DELETE")
        db.executescript(SCHEMA_SQL)
        db.executemany(
            "INSERT INTO customers(id, email, created_at) VALUES(?, ?, ?)",
            spec["customers"],
        )
        db.executemany(
            "INSERT INTO unrelated_records(id, code, note) VALUES(?, ?, ?)",
            spec["unrelated"],
        )
        db.commit()
        db.execute("VACUUM")
    finally:
        db.close()


def _fixture_entry(spec: dict, path: Path) -> dict:
    initial = sorted(spec["customers"], key=lambda row: row[0])
    expected = expected_survivors(initial)
    unrelated = sorted(spec["unrelated"], key=lambda row: row[0])
    data = path.read_bytes()
    return {
        "id": spec["id"],
        "label": spec["label"],
        "purpose": spec["purpose"],
        "properties": list(spec["properties"]),
        "generator": dict(spec["generator"]),
        "relativePath": f"fixtures/{path.name}",
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "insertionOrder": [row[0] for row in spec["customers"]],
        "initialRows": [list(row) for row in initial],
        "expected": {
            "table": "customers",
            "columns": [dict(column) for column in CUSTOMER_COLUMNS],
            "rowCount": len(expected),
            "rows": [list(row) for row in expected],
        },
        "unrelated": {
            "table": "unrelated_records",
            "columns": [dict(column) for column in UNRELATED_COLUMNS],
            "rowCount": len(unrelated),
            "initialRows": [list(row) for row in unrelated],
            "expectedRows": [list(row) for row in unrelated],
        },
    }


_WIRE_COLUMN_TYPES = {
    "INTEGER": "integer",
    "TEXT": "string",
}


def _wire_column_type(column: dict) -> str:
    declared = str(column.get("declaredType", ""))
    try:
        return _WIRE_COLUMN_TYPES[declared.upper()]
    except KeyError as exc:
        raise ValueError(f"unsupported fixture column type {declared!r}") from exc


def _typed_cell(value):
    """Encode one SQLite cell using the Core typed-value wire union."""
    if value is None:
        return {"type": "null", "value": None}
    if type(value) is int:
        # Integer cells are canonical decimal strings, not JSON numbers.
        return {"type": "integer", "value": str(value)}
    if type(value) is str:
        return {"type": "string", "value": value}
    raise TypeError(f"unsupported typed cell {value!r}")


def _expectation_columns(columns: list[dict]) -> list[dict]:
    return [
        {"name": column["name"], "type": _wire_column_type(column)}
        for column in columns
    ]


def _table_expectation(name: str, columns: list[dict], rows) -> dict:
    return {
        "name": name,
        "columns": _expectation_columns(columns),
        "rows": [[_typed_cell(value) for value in row] for row in rows],
    }


def _visible_column(column: dict) -> dict:
    visible = {"name": column["name"], "type": _wire_column_type(column)}
    if column.get("primaryKey"):
        visible["primaryKey"] = True
    if column.get("notNull"):
        visible["notNull"] = True
    if column.get("collation"):
        visible["collation"] = column["collation"]
    return visible


def _visible_schema() -> dict:
    return {
        "tables": [
            {
                "name": table["name"],
                "columns": [_visible_column(column) for column in table["columns"]],
            }
            for table in SCHEMA_TABLES
        ]
    }


def build_public_manifest(index: dict) -> dict:
    """Build the closed Core manifest from a verified internal suite index."""
    fixtures = index["fixtures"]
    cases = []
    for fixture in fixtures:
        cases.append(
            {
                "fixture": fixture["id"],
                "oracle": {
                    "kind": "final-state",
                    "tables": [
                        _table_expectation(
                            fixture["expected"]["table"],
                            fixture["expected"]["columns"],
                            fixture["expected"]["rows"],
                        ),
                        _table_expectation(
                            fixture["unrelated"]["table"],
                            fixture["unrelated"]["columns"],
                            fixture["unrelated"]["expectedRows"],
                        ),
                    ],
                    "invariants": [
                        {
                            **MANIFEST_INVARIANT,
                            "groupBy": list(MANIFEST_INVARIANT["groupBy"]),
                        }
                    ],
                },
            }
        )
    return {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "gradingVersion": MANIFEST_GRADING_VERSION,
        "challengeId": index["challengeId"],
        "revision": MANIFEST_REVISION,
        "title": MANIFEST_TITLE,
        "objective": MANIFEST_OBJECTIVE,
        "difficulty": MANIFEST_DIFFICULTY,
        "dialect": "sqlite",
        "allowedOperation": "write",
        "timing": MANIFEST_TIMING,
        "engine": dict(MANIFEST_ENGINE),
        "fixtureSuite": {
            "id": MANIFEST_FIXTURE_SUITE_ID,
            "fixtures": [
                {
                    "id": fixture["id"],
                    "label": fixture["label"],
                    "sha256": fixture["sha256"],
                    "bytes": fixture["bytes"],
                    "runs": 2,
                }
                for fixture in fixtures
            ],
        },
        "visibleSchema": _visible_schema(),
        "parts": [
            {
                "id": MANIFEST_PART_ID,
                "title": MANIFEST_PART_TITLE,
                "required": True,
                "answerKind": "sql",
                "sql": {"cases": cases},
            }
        ],
        "hints": [{**hint} for hint in MANIFEST_HINTS],
        "referenceSolutions": [
            {
                "partId": MANIFEST_PART_ID,
                "answer": {"sql": MANIFEST_REFERENCE_SQL},
            }
        ],
    }


def public_manifest_text(index: dict) -> str:
    """Canonical deterministic bytes for the checked public revision manifest."""
    return (
        json.dumps(
            build_public_manifest(index),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def _write_public_manifest(output_dir: Path, index: dict) -> Path:
    path = Path(output_dir) / MANIFEST_FILENAME
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(public_manifest_text(index), encoding="utf-8")
    os.replace(temporary, path)
    return path


def verify_public_manifest(suite_dir: Path, index: dict) -> list[str]:
    """Refuse a missing or changed checked manifest; never regenerate it here."""
    path = Path(suite_dir) / MANIFEST_FILENAME
    try:
        checked = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"cannot read checked public manifest {path}: {exc}"]
    try:
        expected = public_manifest_text(index)
    except Exception as exc:
        return [f"cannot build expected public manifest: {exc}"]
    if checked != expected:
        return [
            "checked public manifest differs from the trusted generator; "
            "run the explicit regenerate command instead of editing it by hand"
        ]
    return []


def _builder_metadata() -> dict:
    tool_path = Path(__file__).resolve()
    try:
        tool_name = tool_path.relative_to(ROOT).as_posix()
    except ValueError:
        tool_name = tool_path.name
    return {
        "tool": tool_name,
        "sha256": sha256_file(tool_path),
        "sqliteVersion": sqlite3.sqlite_version,
        "sqliteVersionInfo": list(sqlite3.sqlite_version_info),
        "pythonVersion": platform.python_version(),
        "regenerationCommand": "python3 scripts/delete-duplicates-fixtures.py regenerate",
        "verificationCommand": "python3 scripts/delete-duplicates-fixtures.py verify",
        "byteStabilityNote": (
            "Committed SQLite bytes are authoritative. SQLite embeds its library "
            "version in the database header, so normal verification checks committed "
            "SHA-256 and semantics instead of regenerating bytes. Run regenerate "
            "explicitly after an intentional fixture or builder change."
        ),
    }


def build_index(output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    fixtures_dir = output_dir / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    fixtures = []
    for spec in all_fixture_specs():
        path = fixtures_dir / spec["filename"]
        _write_fixture(path, spec)
        fixtures.append(_fixture_entry(spec, path))

    index = {
        "format": FORMAT,
        "kind": KIND,
        "challengeId": CHALLENGE_ID,
        "status": "internal-unpublished",
        "publicManifest": False,
        "publicManifestNote": (
            "Internal fixture-suite index only (publicManifest=false). The checked "
            "public revision is generated separately at 1.json using the accepted "
            "Core contract; this internal index is not itself a published manifest."
        ),
        "synthetic": True,
        "dataDeclaration": {
            "classification": "synthetic",
            "statement": (
                "All customer identities, email values, timestamps, IDs and unrelated "
                "records are synthetic and invented for this exercise. No real "
                "customer record, source database, log or production snapshot was "
                "sampled, copied or snapshotted."
            ),
            "license": "CC0-1.0",
            "sourceData": "none",
        },
        "retentionRule": {
            "statement": (
                "Keep the row with the lowest numeric id for each exact email value. "
                "NULL is one duplicate group. Case, leading/trailing whitespace and "
                "inner whitespace are significant. Unrelated tables must be unchanged."
            ),
            "grouping": "email using SQLite BINARY equality",
            "survivor": "MIN(id) per exact email group",
            "tieBreaker": "not applicable: id is the unique integer primary key",
            "oracleOrder": ["id", "email", "created_at"],
            "unrelatedTable": "unrelated_records",
            "idempotency": (
                "Applying a correct deduplication statement twice must leave the same "
                "once-correct final state."
            ),
        },
        "generatedSeed": GENERATED_SEED,
        "generatedVariantCount": GENERATED_VARIANTS,
        "schema": {
            "engine": "sqlite",
            "sql": SCHEMA_SQL,
            "tables": [
                {
                    "name": table["name"],
                    "columns": [dict(column) for column in table["columns"]],
                }
                for table in SCHEMA_TABLES
            ],
        },
        "builder": _builder_metadata(),
        "fixtures": fixtures,
        "references": [dict(reference) for reference in REFERENCE_SOLUTIONS],
        "mutations": [dict(mutation) for mutation in MUTATION_SOLUTIONS],
        "coverage": compute_coverage(fixtures),
        "verification": {
            "command": "python3 scripts/delete-duplicates-fixtures.py verify",
            "unittest": (
                "python3 -m unittest discover -s tests "
                "-p 'test_delete_duplicates_fixtures.py' -v"
            ),
        },
    }
    receipts = compute_receipts(
        output_dir, fixtures, index["references"], index["mutations"]
    )
    index["receipts"] = receipts
    summary = receipts["summary"]
    if summary["referencePasses"] != summary["referenceChecks"]:
        raise RuntimeError(f"reference solutions did not pass: {summary}")
    if summary["undetectedMutations"]:
        raise RuntimeError(f"mutations were not detected: {summary}")
    report = verify_index(output_dir, index)
    if not report["ok"]:
        raise RuntimeError(f"generated suite failed verification: {report['errors']}")
    return index


def _fixture_error(errors: list[str], fixture_id: str, message: str) -> None:
    errors.append(f"{fixture_id}: {message}")


def verify_index(suite_dir: Path, index: dict) -> dict:
    suite_dir = Path(suite_dir)
    errors: list[str] = []
    runtime = {
        "sqliteVersion": sqlite3.sqlite_version,
        "pythonVersion": platform.python_version(),
    }

    if index.get("format") != FORMAT:
        errors.append(f"unexpected format: {index.get('format')!r}")
    if index.get("kind") != KIND:
        errors.append(f"unexpected kind: {index.get('kind')!r}")
    if index.get("challengeId") != CHALLENGE_ID:
        errors.append(f"unexpected challengeId: {index.get('challengeId')!r}")
    if index.get("status") != "internal-unpublished":
        errors.append("suite status must be internal-unpublished")
    if index.get("publicManifest") is not False:
        errors.append("suite must declare publicManifest=false")
    if index.get("synthetic") is not True:
        errors.append("suite must declare synthetic=true")
    statement = str(index.get("dataDeclaration", {}).get("statement", ""))
    if "no real" not in statement.lower():
        errors.append("synthetic data declaration is missing")
    if index.get("schema", {}).get("tables") != [
        {
            "name": table["name"],
            "columns": [dict(column) for column in table["columns"]],
        }
        for table in SCHEMA_TABLES
    ]:
        errors.append("schema declaration differs from the expected schema")
    if index.get("references") != REFERENCE_SOLUTIONS:
        errors.append("reference solution definitions differ from the trusted tool")
    if index.get("mutations") != MUTATION_SOLUTIONS:
        errors.append("mutation definitions differ from the trusted tool")
    if index.get("builder", {}).get("sha256") != sha256_file(Path(__file__)):
        errors.append(
            "internal index was generated by a different tool build; "
            "run the explicit regenerate command"
        )

    fixtures = index.get("fixtures", [])
    expected_specs = all_fixture_specs()
    if [fixture.get("id") for fixture in fixtures] != [
        spec["id"] for spec in expected_specs
    ]:
        errors.append("fixture ids/order differ from the trusted tool")
    if index.get("coverage") != compute_coverage(fixtures):
        errors.append("coverage declaration differs from fixture properties")

    for spec, fixture in zip(expected_specs, fixtures):
        fixture_id = fixture.get("id", "<missing>")
        if fixture.get("label") != spec["label"]:
            _fixture_error(errors, fixture_id, "label differs")
        if fixture.get("purpose") != spec["purpose"]:
            _fixture_error(errors, fixture_id, "purpose differs")
        if fixture.get("properties") != spec["properties"]:
            _fixture_error(errors, fixture_id, "properties differ")
        if fixture.get("generator") != spec["generator"]:
            _fixture_error(errors, fixture_id, "generator metadata differs")
        relative = Path(str(fixture.get("relativePath", "")))
        if relative.is_absolute() or ".." in relative.parts:
            _fixture_error(errors, fixture_id, f"unsafe relative path {relative}")
            continue
        if relative != Path("fixtures") / spec["filename"]:
            _fixture_error(errors, fixture_id, f"unexpected relative path {relative}")
        path = suite_dir / relative
        if not path.is_file():
            _fixture_error(errors, fixture_id, f"missing fixture file {path}")
            continue
        before = path.read_bytes()
        if fixture.get("sha256") != sha256_bytes(before):
            _fixture_error(errors, fixture_id, "committed SHA-256 differs from index")
        if fixture.get("bytes") != len(before):
            _fixture_error(errors, fixture_id, "committed byte length differs from index")

        try:
            with fresh_copy(path) as db:
                schema_errors = _validate_schema(db, SCHEMA_TABLES)
                initial = read_customers(db)
                unrelated = read_unrelated(db)
        except Exception as exc:  # pragma: no cover - defensive report path
            _fixture_error(errors, fixture_id, f"cannot inspect fixture: {exc}")
            continue

        for schema_error in schema_errors:
            _fixture_error(errors, fixture_id, schema_error)
        expected_initial = rows_from_json(fixture.get("initialRows", []))
        if initial != expected_initial:
            _fixture_error(errors, fixture_id, "initial customer rows differ from index")
        expected_unrelated = rows_from_json(
            fixture.get("unrelated", {}).get("initialRows", [])
        )
        if unrelated != expected_unrelated:
            _fixture_error(errors, fixture_id, "unrelated rows differ from index")
        if fixture.get("unrelated", {}).get("expectedRows") != [
            list(row) for row in unrelated
        ]:
            _fixture_error(errors, fixture_id, "unrelated expected rows differ from index")
        if fixture.get("unrelated", {}).get("columns") != UNRELATED_COLUMNS:
            _fixture_error(errors, fixture_id, "unrelated column declaration differs")
        expected_rows = rows_from_json(fixture.get("expected", {}).get("rows", []))
        if expected_rows != expected_survivors(initial):
            _fixture_error(
                errors, fixture_id, "expected final rows differ from the Python oracle"
            )
        if fixture.get("expected", {}).get("columns") != CUSTOMER_COLUMNS:
            _fixture_error(errors, fixture_id, "customer column declaration differs")
        if fixture.get("expected", {}).get("rowCount") != len(expected_rows):
            _fixture_error(errors, fixture_id, "expected rowCount differs")
        if sorted(fixture.get("insertionOrder", [])) != sorted(
            row[0] for row in initial
        ):
            _fixture_error(errors, fixture_id, "insertionOrder does not cover the rows")
        after = path.read_bytes()
        if before != after:
            _fixture_error(errors, fixture_id, "source fixture bytes were modified")

    computed_receipts: dict = {"reference": {}, "mutation": {}, "summary": {}}
    try:
        computed_receipts = compute_receipts(
            suite_dir,
            fixtures,
            index.get("references", []),
            index.get("mutations", []),
        )
    except Exception as exc:  # pragma: no cover - defensive report path
        errors.append(f"could not compute solution receipts: {exc}")

    if computed_receipts != index.get("receipts"):
        errors.append("reference/mutation receipts differ from committed index")
    summary = computed_receipts.get("summary", {})
    if summary:
        if summary.get("referencePasses") != summary.get("referenceChecks"):
            errors.append(f"reference solutions failed: {summary}")
        if summary.get("undetectedMutations"):
            errors.append(f"mutations were not detected: {summary}")

    for fixture in fixtures:
        relative = Path(str(fixture.get("relativePath", "")))
        path = suite_dir / relative
        if path.is_file() and fixture.get("sha256") != sha256_file(path):
            errors.append(f"{fixture.get('id')}: source fixture bytes changed during verification")

    return {
        "ok": not errors,
        "errors": errors,
        "runtime": runtime,
        "fixtureCount": len(fixtures),
        "referenceCount": len(index.get("references", [])),
        "mutationCount": len(index.get("mutations", [])),
        "summary": summary,
        "referenceMatrix": computed_receipts.get("reference", {}),
        "mutationMatrix": computed_receipts.get("mutation", {}),
    }


def verify_suite(suite_dir: Path = DEFAULT_SUITE_DIR) -> dict:
    suite_dir = Path(suite_dir)
    index_path = suite_dir / INDEX_FILENAME
    try:
        index = json.loads(index_path.read_text())
    except Exception as exc:
        return {
            "ok": False,
            "errors": [f"cannot read {index_path}: {exc}"],
            "runtime": {
                "sqliteVersion": sqlite3.sqlite_version,
                "pythonVersion": platform.python_version(),
            },
            "fixtureCount": 0,
            "referenceCount": 0,
            "mutationCount": 0,
            "manifestPath": str(suite_dir / MANIFEST_FILENAME),
            "summary": {},
            "referenceMatrix": {},
            "mutationMatrix": {},
        }
    report = verify_index(suite_dir, index)
    manifest_errors = verify_public_manifest(suite_dir, index)
    report["errors"].extend(manifest_errors)
    report["manifestPath"] = str(suite_dir / MANIFEST_FILENAME)
    report["manifestOk"] = not manifest_errors
    report["ok"] = not report["errors"]
    return report


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def regenerate_suite(suite_dir: Path = DEFAULT_SUITE_DIR) -> dict:
    suite_dir = Path(suite_dir)
    suite_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="datatug-delete-duplicates-") as tmp:
        temporary = Path(tmp)
        index = build_index(temporary)
        fixtures_dir = suite_dir / "fixtures"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        expected_names = {
            Path(fixture["relativePath"]).name for fixture in index["fixtures"]
        }
        for existing in fixtures_dir.glob("*.db"):
            if existing.name not in expected_names:
                existing.unlink()
        for fixture in index["fixtures"]:
            source = temporary / fixture["relativePath"]
            destination = suite_dir / fixture["relativePath"]
            _atomic_copy(source, destination)
        index_text = json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        temporary_index = suite_dir / (INDEX_FILENAME + ".tmp")
        temporary_index.write_text(index_text)
        os.replace(temporary_index, suite_dir / INDEX_FILENAME)
        _write_public_manifest(suite_dir, index)
    report = verify_suite(suite_dir)
    if not report["ok"]:
        raise RuntimeError(
            "regenerated suite failed verification:\n"
            + json.dumps(report["errors"], indent=2)
        )
    return index


def _print_report(report: dict, *, regenerated: bool = False) -> None:
    status = "OK" if report["ok"] else "FAIL"
    action = "regenerated and verified" if regenerated else "verified"
    print(f"Delete-duplicates fixture suite {action}: {status}")
    print(f"  fixtures: {report['fixtureCount']}")
    print(f"  references: {report['referenceCount']}")
    print(f"  mutations: {report['mutationCount']}")
    summary = report.get("summary") or {}
    if summary:
        print(
            "  reference checks: "
            f"{summary.get('referencePasses')}/{summary.get('referenceChecks')}"
        )
        print(
            "  rejected mutation cases: "
            f"{summary.get('rejectedMutationCases')}/{summary.get('mutationCases')}"
        )
    if report.get("manifestPath"):
        print(f"  public manifest: {report['manifestPath']}")
    print(
        "  runtime: SQLite "
        f"{report['runtime']['sqliteVersion']} / Python "
        f"{report['runtime']['pythonVersion']}"
    )
    for error in report["errors"]:
        print(f"  - {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify or explicitly regenerate the internal delete-duplicates "
            "challenge fixture suite."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser(
        "verify", help="verify committed fixture hashes, semantics and receipts"
    )
    verify_parser.add_argument("--suite-dir", type=Path, default=DEFAULT_SUITE_DIR)
    verify_parser.add_argument("--json", action="store_true")
    regenerate_parser = subparsers.add_parser(
        "regenerate", help="explicitly regenerate fixture files and the internal index"
    )
    regenerate_parser.add_argument("--suite-dir", type=Path, default=DEFAULT_SUITE_DIR)
    regenerate_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "verify":
        report = verify_suite(args.suite_dir)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            _print_report(report)
        return 0 if report["ok"] else 1

    try:
        regenerate_suite(args.suite_dir)
        report = verify_suite(args.suite_dir)
    except Exception as exc:
        print(f"regeneration failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_report(report, regenerated=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
