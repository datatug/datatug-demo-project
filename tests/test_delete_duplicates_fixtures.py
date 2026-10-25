"""Trusted checks for the internal delete-duplicates challenge fixture suite.

The committed SQLite files are immutable inputs. Every solution and mutation is
executed on a fresh in-memory copy; the committed bytes are hashed before and
after the checks to prove they were not modified.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = ROOT / "demo-project-1/challenges/delete-duplicates"
INDEX_PATH = SUITE_DIR / "suite.json"
MANIFEST_PATH = SUITE_DIR / "1.json"
TOOL_PATH = ROOT / "scripts/delete-duplicates-fixtures.py"

EXPECTED_FIXTURE_IDS = [
    "basic",
    "no-duplicates",
    "multi-group",
    "nonsequential-created-at",
    "null-empty",
    "case-whitespace",
    "generated-variant-01",
    "generated-variant-02",
    "generated-variant-03",
]

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


def _cell_value(cell):
    if cell["type"] == "null":
        assert cell["value"] is None
        return None
    if cell["type"] == "integer":
        assert isinstance(cell["value"], str)
        return int(cell["value"])
    assert cell["type"] == "string"
    assert isinstance(cell["value"], str)
    return cell["value"]


class DeleteDuplicatesFixtureSuiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tool.verify_suite(SUITE_DIR)
        if not cls.report["ok"]:
            raise AssertionError(cls.report["errors"])
        cls.index = json.loads(INDEX_PATH.read_text())
        cls.fixtures = {fixture["id"]: fixture for fixture in cls.index["fixtures"]}
        cls.manifest = json.loads(MANIFEST_PATH.read_text())
        cls.manifest_text = MANIFEST_PATH.read_text()

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

    def test_public_manifest_is_the_checked_closed_core_revision(self):
        manifest = self.manifest
        self.assertEqual(
            {
                "schemaVersion",
                "gradingVersion",
                "challengeId",
                "revision",
                "title",
                "objective",
                "difficulty",
                "dialect",
                "allowedOperation",
                "timing",
                "engine",
                "fixtureSuite",
                "visibleSchema",
                "parts",
                "hints",
                "referenceSolutions",
            },
            set(manifest),
        )
        self.assertEqual(1, manifest["schemaVersion"])
        self.assertEqual("challenge-grading-v1", manifest["gradingVersion"])
        self.assertEqual("delete-duplicates", manifest["challengeId"])
        self.assertEqual(1, manifest["revision"])
        self.assertEqual("Delete duplicate customers", manifest["title"])
        self.assertEqual("intro", manifest["difficulty"])
        self.assertEqual("sqlite", manifest["dialect"])
        self.assertEqual("write", manifest["allowedOperation"])
        self.assertEqual("optional", manifest["timing"])
        self.assertEqual(
            {
                "package": "@sqlite.org/sqlite-wasm",
                "version": "3.54.1-build1",
                "sqliteVersion": "3.54.1",
            },
            manifest["engine"],
        )
        self.assertEqual(
            ["customers", "unrelated_records"],
            [table["name"] for table in manifest["visibleSchema"]["tables"]],
        )
        self.assertEqual(9, len(manifest["fixtureSuite"]["fixtures"]))
        self.assertEqual(1, len(manifest["parts"]))
        self.assertEqual(
            tool.public_manifest_text(self.index), self.manifest_text
        )
        self.assertEqual(tool.build_public_manifest(self.index), manifest)

    def test_public_manifest_pins_every_case_and_typed_expected_table(self):
        manifest = self.manifest
        pins = manifest["fixtureSuite"]["fixtures"]
        self.assertEqual(
            EXPECTED_FIXTURE_IDS, [fixture["id"] for fixture in pins]
        )
        for pin in pins:
            with self.subTest(fixture=pin["id"]):
                self.assertEqual(
                    {"id", "label", "sha256", "bytes", "runs"}, set(pin)
                )
                self.assertEqual(2, pin["runs"])
                source = self.fixtures[pin["id"]]
                self.assertEqual(source["sha256"], pin["sha256"])
                self.assertEqual(source["bytes"], pin["bytes"])
                self.assertEqual(source["label"], pin["label"])

        part = manifest["parts"][0]
        self.assertEqual("delete-duplicates", part["id"])
        self.assertTrue(part["required"])
        self.assertEqual("sql", part["answerKind"])
        cases = part["sql"]["cases"]
        self.assertEqual(
            EXPECTED_FIXTURE_IDS, [case["fixture"] for case in cases]
        )
        self.assertEqual(len(EXPECTED_FIXTURE_IDS), len(cases))

        for case in cases:
            fixture = self.fixtures[case["fixture"]]
            with self.subTest(fixture=case["fixture"]):
                oracle = case["oracle"]
                self.assertEqual(
                    {"kind", "tables", "invariants"}, set(oracle)
                )
                self.assertEqual("final-state", oracle["kind"])
                self.assertEqual(
                    ["customers", "unrelated_records"],
                    [table["name"] for table in oracle["tables"]],
                )
                tables = {table["name"]: table for table in oracle["tables"]}
                self.assertEqual(
                    ["id", "email", "created_at"],
                    [column["name"] for column in tables["customers"]["columns"]],
                )
                self.assertEqual(
                    ["id", "code", "note"],
                    [
                        column["name"]
                        for column in tables["unrelated_records"]["columns"]
                    ],
                )
                for table in oracle["tables"]:
                    for row in table["rows"]:
                        for column, cell in zip(table["columns"], row):
                            if cell["type"] == "null":
                                self.assertIsNone(cell["value"])
                                continue
                            if cell["type"] == "integer":
                                self.assertEqual("integer", column["type"])
                                self.assertIs(type(cell["value"]), str)
                                self.assertRegex(
                                    cell["value"], r"^(0|-?[1-9][0-9]*)$"
                                )
                            elif cell["type"] == "string":
                                self.assertEqual("string", column["type"])
                                self.assertIs(type(cell["value"]), str)
                            else:
                                self.fail(cell["type"])

                self.assertEqual(
                    [tuple(row) for row in fixture["expected"]["rows"]],
                    [
                        tuple(_cell_value(cell) for cell in row)
                        for row in tables["customers"]["rows"]
                    ],
                )
                self.assertEqual(
                    [tuple(row) for row in fixture["unrelated"]["expectedRows"]],
                    [
                        tuple(_cell_value(cell) for cell in row)
                        for row in tables["unrelated_records"]["rows"]
                    ],
                )
                self.assertEqual(
                    [tool.MANIFEST_INVARIANT],
                    oracle["invariants"],
                )

    def test_public_manifest_hints_and_reference_are_assisted_only(self):
        manifest = self.manifest
        self.assertEqual(
            [hint["id"] for hint in tool.MANIFEST_HINTS],
            [hint["id"] for hint in manifest["hints"]],
        )
        self.assertEqual(
            [hint["text"] for hint in tool.MANIFEST_HINTS],
            [hint["text"] for hint in manifest["hints"]],
        )
        for hint in manifest["hints"]:
            self.assertLessEqual(len(hint["text"]), 1000)
            self.assertNotIn("DELETE FROM", hint["text"].upper())

        references = manifest["referenceSolutions"]
        self.assertEqual(1, len(references))
        self.assertEqual("delete-duplicates", references[0]["partId"])
        self.assertEqual({"sql"}, set(references[0]["answer"]))
        self.assertEqual(
            tool.MANIFEST_REFERENCE_SQL, references[0]["answer"]["sql"]
        )
        self.assertIn(
            "IS customers.email COLLATE BINARY",
            references[0]["answer"]["sql"],
        )
        self.assertIn("keeper.id < customers.id", references[0]["answer"]["sql"])

    def test_verify_refuses_changed_manifest_or_fixture_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "delete-duplicates"
            shutil.copytree(SUITE_DIR, copied)
            self.assertTrue(tool.verify_suite(copied)["ok"])

            manifest_path = copied / tool.MANIFEST_FILENAME
            original_manifest = manifest_path.read_text()
            manifest_path.write_text(
                original_manifest.replace(
                    '"revision": 1', '"revision": 2', 1
                )
            )
            report = tool.verify_suite(copied)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any(
                    "checked public manifest differs" in error
                    for error in report["errors"]
                ),
                report["errors"],
            )

            manifest_path.write_text(original_manifest)
            fixture_path = copied / self.fixtures["basic"]["relativePath"]
            fixture_bytes = fixture_path.read_bytes()
            fixture_path.write_bytes(fixture_bytes + b"\0")
            report = tool.verify_suite(copied)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("SHA-256" in error for error in report["errors"]),
                report["errors"],
            )
            self.assertEqual(fixture_bytes, fixture_path.read_bytes()[:-1])

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

            first_manifest = tool.build_public_manifest(first_index)
            second_manifest = tool.build_public_manifest(second_index)
            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual(first_manifest, self.manifest)
            self.assertEqual(
                tool.public_manifest_text(first_index),
                tool.public_manifest_text(second_index),
            )
            self.assertEqual(
                tool.public_manifest_text(first_index), self.manifest_text
            )


if __name__ == "__main__":
    unittest.main()
