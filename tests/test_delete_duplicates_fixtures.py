"""Trusted checks for the internal delete-duplicates challenge fixture suite.

The committed SQLite files are immutable inputs. Every solution and mutation is
executed on a fresh in-memory copy; the committed bytes are hashed before and
after the checks to prove they were not modified.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = ROOT / "demo-project-1/challenges/delete-duplicates"
INDEX_PATH = SUITE_DIR / "suite.json"
TOOL_PATH = ROOT / "scripts/delete-duplicates-fixtures.py"

_spec = importlib.util.spec_from_file_location("delete_duplicates_fixtures", TOOL_PATH)
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

EXPECTED_FINAL_IDS = {
    "basic": [2, 3, 5],
    "no-duplicates": [1, 2, 4, 6, 9],
    "multi-group": [2, 3, 5, 8, 25],
    "nonsequential-created-at": [2, 3, 7, 41],
    "null-empty": [1, 2, 4, 5],
    "case-whitespace": [2, 3, 5, 6, 11, 12, 13, 14],
}

MUTATION_EXPECTATIONS = {
    "delete-all": ("basic", {"customers.expected-survivor-missing"}),
    "keep-highest-id": (
        "basic",
        {"customers.expected-survivor-missing", "customers.unexpected-survivor-present"},
    ),
    "keep-earliest-created-at": (
        "nonsequential-created-at",
        {"customers.expected-survivor-missing", "customers.unexpected-survivor-present"},
    ),
    "ignore-null-group-equality": (
        "null-empty",
        {
            "customers.duplicate-email-group-remaining",
            "customers.unexpected-survivor-present",
        },
    ),
    "case-trim-collapse": ("case-whitespace", {"customers.expected-survivor-missing"}),
    "delete-one-duplicate": (
        "basic",
        {
            "customers.duplicate-email-group-remaining",
            "customers.unexpected-survivor-present",
        },
    ),
    "collateral-unrelated-delete": ("basic", {"unrelated.rows-changed"}),
}


def _groups(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row[1], []).append(row)
    return groups


class DeleteDuplicatesFixtureSuiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tool.verify_suite(SUITE_DIR)
        if not cls.report["ok"]:
            raise AssertionError(cls.report["errors"])
        cls.index = json.loads(INDEX_PATH.read_text())
        cls.fixtures = {fixture["id"]: fixture for fixture in cls.index["fixtures"]}

    def test_internal_index_pins_hashes_bytes_columns_and_synthetic_status(self):
        index = self.index
        self.assertTrue(index["synthetic"])
        self.assertFalse(index["publicManifest"])
        self.assertEqual("internal-unpublished", index["status"])
        self.assertIn("no real", index["dataDeclaration"]["statement"].lower())
        self.assertEqual(
            [
                "basic",
                "no-duplicates",
                "multi-group",
                "nonsequential-created-at",
                "null-empty",
                "case-whitespace",
                "generated-variant-01",
                "generated-variant-02",
                "generated-variant-03",
            ],
            [fixture["id"] for fixture in index["fixtures"]],
        )
        self.assertTrue(index["builder"]["sqliteVersion"])
        self.assertEqual(
            hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
            index["builder"]["sha256"],
        )
        self.assertEqual(
            {"customers", "unrelated_records"},
            {table["name"] for table in index["schema"]["tables"]},
        )
        for fixture in index["fixtures"]:
            with self.subTest(fixture=fixture["id"]):
                relative = Path(fixture["relativePath"])
                self.assertFalse(relative.is_absolute())
                self.assertEqual(("fixtures", relative.name), relative.parts)
                path = SUITE_DIR / relative
                data = path.read_bytes()
                self.assertEqual(fixture["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(fixture["bytes"], len(data))
                self.assertLess(len(data), 1024 * 1024)
                self.assertEqual(
                    ["id", "email", "created_at"],
                    [column["name"] for column in fixture["expected"]["columns"]],
                )
                self.assertEqual(
                    fixture["expected"]["rowCount"], len(fixture["expected"]["rows"])
                )
                for row in fixture["expected"]["rows"]:
                    self.assertIsInstance(row[0], int)
                    self.assertTrue(row[1] is None or isinstance(row[1], str))
                    self.assertIsInstance(row[2], str)

        self.assertEqual(
            set(tool.REQUIRED_COVERAGE),
            set(index["coverage"]),
        )
        for property_name, fixture_ids in index["coverage"].items():
            with self.subTest(property=property_name):
                self.assertTrue(fixture_ids)
                self.assertTrue(set(fixture_ids) <= set(self.fixtures))

    def test_fixture_semantics_and_required_coverage(self):
        for fixture in self.index["fixtures"]:
            with self.subTest(fixture=fixture["id"]):
                with tool.fresh_copy(SUITE_DIR / fixture["relativePath"]) as db:
                    schema = tool.inspect_schema(db)
                    initial = tool.read_customers(db)
                    unrelated = tool.read_unrelated(db)

                self.assertEqual(
                    ["id", "email", "created_at"],
                    [column["name"] for column in schema["customers"]["columns"]],
                )
                self.assertIn("COLLATE BINARY", schema["customers"]["sql"].upper())
                self.assertEqual(
                    ["id", "code", "note"],
                    [column["name"] for column in schema["unrelated_records"]["columns"]],
                )
                self.assertEqual(
                    [list(row) for row in initial], fixture["initialRows"]
                )
                self.assertEqual(
                    [list(row) for row in unrelated],
                    fixture["unrelated"]["initialRows"],
                )
                self.assertEqual(
                    [list(row) for row in tool.expected_survivors(initial)],
                    fixture["expected"]["rows"],
                )
                self.assertEqual(
                    fixture["unrelated"]["initialRows"],
                    fixture["unrelated"]["expectedRows"],
                )
                if fixture["id"] in EXPECTED_FINAL_IDS:
                    self.assertEqual(
                        EXPECTED_FINAL_IDS[fixture["id"]],
                        [row[0] for row in fixture["expected"]["rows"]],
                    )

        basic_groups = _groups(tool.rows_from_json(self.fixtures["basic"]["initialRows"]))
        self.assertTrue(any(len(rows) > 1 for rows in basic_groups.values()))

        no_duplicate_groups = _groups(
            tool.rows_from_json(self.fixtures["no-duplicates"]["initialRows"])
        )
        self.assertFalse(any(len(rows) > 1 for rows in no_duplicate_groups.values()))
        self.assertIn(None, no_duplicate_groups)
        self.assertIn("", no_duplicate_groups)

        multi_groups = _groups(
            tool.rows_from_json(self.fixtures["multi-group"]["initialRows"])
        )
        self.assertGreaterEqual(
            len([rows for rows in multi_groups.values() if len(rows) > 1]), 3
        )
        self.assertTrue(any(len(rows) >= 3 for rows in multi_groups.values()))

        nonsequential = self.fixtures["nonsequential-created-at"]
        self.assertNotEqual(
            nonsequential["insertionOrder"], sorted(nonsequential["insertionOrder"])
        )
        nonsequential_groups = _groups(
            tool.rows_from_json(nonsequential["initialRows"])
        )
        ambiguity = False
        for rows in nonsequential_groups.values():
            if len(rows) < 2:
                continue
            lowest_id = min(row[0] for row in rows)
            earliest = min(rows, key=lambda row: (row[2], row[0]))
            ambiguity = ambiguity or earliest[0] > lowest_id
        self.assertTrue(ambiguity)

        null_empty_groups = _groups(
            tool.rows_from_json(self.fixtures["null-empty"]["initialRows"])
        )
        self.assertGreaterEqual(len(null_empty_groups[None]), 2)
        self.assertGreaterEqual(len(null_empty_groups[""]), 2)
        self.assertNotIn(None, null_empty_groups[""])

        case_groups = _groups(
            tool.rows_from_json(self.fixtures["case-whitespace"]["initialRows"])
        )
        self.assertEqual(2, len(case_groups["case@example.com"]))
        self.assertEqual(1, len(case_groups["Case@Example.com"]))
        self.assertEqual(1, len(case_groups["CASE@example.com"]))
        self.assertEqual(2, len(case_groups["padded@example.com"]))
        self.assertEqual(1, len(case_groups[" padded@example.com"]))
        self.assertEqual(1, len(case_groups["padded@example.com "]))
        self.assertEqual(2, len(case_groups["two words@example.com"]))
        self.assertEqual(1, len(case_groups["two  words@example.com"]))

        for fixture_id in ("generated-variant-01", "generated-variant-02", "generated-variant-03"):
            fixture = self.fixtures[fixture_id]
            self.assertEqual(tool.GENERATED_SEED, fixture["generator"]["seed"])
            self.assertIn("generated-fixed-seed", fixture["properties"])
            groups = _groups(tool.rows_from_json(fixture["initialRows"]))
            self.assertTrue(any(len(rows) >= 3 for rows in groups.values()))
            self.assertGreaterEqual(len(groups[None]), 2)
            self.assertGreaterEqual(len(groups[""]), 2)
            self.assertNotEqual(
                fixture["insertionOrder"], sorted(fixture["insertionOrder"])
            )
            ambiguity = False
            for rows in groups.values():
                if len(rows) < 2:
                    continue
                lowest_id = min(row[0] for row in rows)
                earliest = min(rows, key=lambda row: (row[2], row[0]))
                ambiguity = ambiguity or earliest[0] > lowest_id
            self.assertTrue(ambiguity)
            self.assertIn("case-sensitive-email", fixture["properties"])
            self.assertIn("whitespace-sensitive-email", fixture["properties"])

    def test_reference_solutions_pass_every_fixture_twice_without_mutating_sources(self):
        before = {
            fixture["id"]: hashlib.sha256(
                (SUITE_DIR / fixture["relativePath"]).read_bytes()
            ).hexdigest()
            for fixture in self.index["fixtures"]
        }
        self.assertEqual(
            {
                "null-safe-exists-lowest-id",
                "grouped-min-lowest-id",
                "window-ranked-lowest-id",
            },
            {reference["id"] for reference in self.index["references"]},
        )
        for reference in self.index["references"]:
            for fixture in self.index["fixtures"]:
                with self.subTest(reference=reference["id"], fixture=fixture["id"]):
                    first = tool.run_sql(SUITE_DIR, fixture, reference["sql"])
                    second = tool.run_sql(
                        SUITE_DIR, fixture, reference["sql"], apply_twice=True
                    )
                    self.assertEqual(first, second)
                    self.assertEqual(
                        [list(row) for row in second["customers"]],
                        fixture["expected"]["rows"],
                    )
                    self.assertEqual(
                        [list(row) for row in second["unrelated"]],
                        fixture["unrelated"]["expectedRows"],
                    )
                    receipt = self.index["receipts"]["reference"][reference["id"]][
                        fixture["id"]
                    ]
                    self.assertEqual("pass", receipt["result"])
                    self.assertTrue(receipt["idempotent"])
        after = {
            fixture["id"]: hashlib.sha256(
                (SUITE_DIR / fixture["relativePath"]).read_bytes()
            ).hexdigest()
            for fixture in self.index["fixtures"]
        }
        self.assertEqual(before, after)

    def test_wrong_mutation_matrix_rejects_each_mutation_on_a_relevant_invariant(self):
        matrix = self.index["receipts"]["mutation"]
        fixture_ids = set(self.fixtures)
        self.assertEqual(set(MUTATION_EXPECTATIONS), {m["id"] for m in self.index["mutations"]})
        for mutation in self.index["mutations"]:
            results = matrix[mutation["id"]]
            self.assertEqual(fixture_ids, set(results))
            failures = [
                fixture_id
                for fixture_id, result in results.items()
                if result["result"] == "fail"
            ]
            self.assertTrue(failures, mutation["id"])
            for fixture_id in failures:
                self.assertTrue(results[fixture_id]["violations"])
            expected_fixture, expected_invariants = MUTATION_EXPECTATIONS[mutation["id"]]
            self.assertIn(expected_fixture, failures, mutation["id"])
            self.assertTrue(
                expected_invariants
                <= set(results[expected_fixture]["violations"]),
                (mutation["id"], results[expected_fixture]),
            )

        basic = self.fixtures["basic"]
        nonsequential = self.fixtures["nonsequential-created-at"]
        for mutation_id, fixture in (
            ("keep-highest-id", basic),
            ("keep-earliest-created-at", nonsequential),
        ):
            mutation = next(m for m in self.index["mutations"] if m["id"] == mutation_id)
            result = tool.run_sql(SUITE_DIR, fixture, mutation["sql"])
            self.assertEqual(
                len(fixture["expected"]["rows"]), len(result["customers"])
            )
            self.assertNotEqual(
                [list(row) for row in result["customers"]],
                fixture["expected"]["rows"],
            )

        earliest_failure = matrix["keep-earliest-created-at"]["nonsequential-created-at"]
        self.assertIn("customers.expected-survivor-missing", earliest_failure["violations"])
        self.assertIn("customers.unexpected-survivor-present", earliest_failure["violations"])
        self.assertIn(2, earliest_failure["missingIds"])
        self.assertIn(100, earliest_failure["unexpectedIds"])

        null_failure = matrix["ignore-null-group-equality"]["null-empty"]
        self.assertIn(None, null_failure["duplicateEmails"])
        self.assertIn(9, null_failure["unexpectedIds"])
        self.assertIn(12, null_failure["unexpectedIds"])

        case_failure = matrix["case-trim-collapse"]["case-whitespace"]
        for missing_id in (3, 6, 11, 12):
            self.assertIn(missing_id, case_failure["missingIds"])

        delete_all = tool.run_sql(
            SUITE_DIR,
            basic,
            next(m for m in self.index["mutations"] if m["id"] == "delete-all")["sql"],
        )
        self.assertEqual([], delete_all["customers"])

        collateral = tool.run_sql(
            SUITE_DIR,
            basic,
            next(
                m
                for m in self.index["mutations"]
                if m["id"] == "collateral-unrelated-delete"
            )["sql"],
        )
        self.assertEqual(
            [list(row) for row in collateral["customers"]],
            basic["expected"]["rows"],
        )
        self.assertNotEqual(
            [list(row) for row in collateral["unrelated"]],
            basic["unrelated"]["expectedRows"],
        )

        summary = self.index["receipts"]["summary"]
        self.assertEqual([], summary["undetectedMutations"])
        self.assertEqual(
            len(self.index["mutations"]), summary["rejectedMutationCases"]
        )

    def test_generator_is_deterministic_and_reproduces_committed_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            first_index = tool.build_index(first)
            second_index = tool.build_index(second)
            for left, right in zip(first_index["fixtures"], second_index["fixtures"]):
                self.assertEqual(
                    (first / left["relativePath"]).read_bytes(),
                    (second / right["relativePath"]).read_bytes(),
                    left["id"],
                )
                self.assertEqual(left["expected"], right["expected"])
                self.assertEqual(left["unrelated"], right["unrelated"])

            # Deliberately compare semantics, not bytes, with the committed
            # suite: SQLite embeds the library version in the file header.
            committed = self.fixtures
            for fixture in first_index["fixtures"]:
                expected = committed[fixture["id"]]
                self.assertEqual(fixture["initialRows"], expected["initialRows"])
                self.assertEqual(fixture["expected"], expected["expected"])
                self.assertEqual(fixture["unrelated"], expected["unrelated"])
                self.assertEqual(fixture["generator"], expected["generator"])
                self.assertEqual(fixture["insertionOrder"], expected["insertionOrder"])
            self.assertEqual(first_index["receipts"], self.index["receipts"])
            self.assertEqual(first_index["references"], self.index["references"])
            self.assertEqual(first_index["mutations"], self.index["mutations"])
            self.assertEqual(first_index["coverage"], self.index["coverage"])


if __name__ == "__main__":
    unittest.main()
