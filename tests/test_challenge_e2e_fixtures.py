"""Tests for the QA challenge end-to-end fixture project.

The tests import the trusted authoring tool, recompute every authored byte, and
execute the reference answers against read-only in-memory copies of the pinned
fixtures. When a sibling datatug-core worktree is available, the tool also runs
the real Core `Open` and grading functions through a temporary Go helper.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "testdata/challenge-e2e-project"
TOOL_PATH = ROOT / "scripts/challenge-e2e-fixtures.py"

_spec = importlib.util.spec_from_file_location("challenge_e2e_fixtures", TOOL_PATH)
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ChallengeE2EFixtureProjectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tool.verify(PROJECT_DIR, require_core=False)
        if not cls.report["ok"]:
            raise AssertionError(cls.report["errors"])
        cls.manifests = {
            challenge_id: json.loads(
                (PROJECT_DIR / "challenges" / challenge_id / "1.json").read_text()
            )
            for challenge_id in tool.build_manifests()
        }

    def test_authored_assets_are_deterministic_and_committed(self):
        first = tool.build_assets(PROJECT_DIR)
        second = tool.build_assets(PROJECT_DIR)
        self.assertEqual(first, second)
        for path, expected in first.items():
            with self.subTest(path=path.relative_to(PROJECT_DIR).as_posix()):
                self.assertEqual(expected, path.read_bytes())
                self.assertEqual(_sha256(expected), _sha256(path.read_bytes()))

        with tempfile.TemporaryDirectory() as temporary:
            temp_project = Path(temporary)
            tool.regenerate(temp_project)
            first_hashes = {
                path.relative_to(temp_project).as_posix(): _sha256(path.read_bytes())
                for path in sorted(temp_project.rglob("*"))
                if path.is_file()
            }
            tool.regenerate(temp_project)
            second_hashes = {
                path.relative_to(temp_project).as_posix(): _sha256(path.read_bytes())
                for path in sorted(temp_project.rglob("*"))
                if path.is_file()
            }
            committed_hashes = {
                path.relative_to(PROJECT_DIR).as_posix(): _sha256(data)
                for path, data in first.items()
            }
            self.assertEqual(first_hashes, second_hashes)
            self.assertEqual(first_hashes, committed_hashes)

    def test_project_is_minimal_qa_and_not_registered_publicly(self):
        project = json.loads((PROJECT_DIR / "datatug-project.json").read_text())
        self.assertEqual("challenge-e2e-project", project["id"])
        self.assertEqual("private", project["access"])
        self.assertIn("QA", project["title"])
        for relative in [".datatug.yaml", "demo-project-1/datatug-project.json", "README.md"]:
            self.assertNotIn("challenge-e2e-project", (ROOT / relative).read_text())

    def test_original_public_revision_and_nine_fixtures_are_unchanged(self):
        manifest_path = ROOT / "demo-project-1/challenges/delete-duplicates/1.json"
        self.assertEqual(
            "6d533e46569eddde4566f0215e20e548bf8c744da3bbfb86518a6a197bb89ebb",
            _sha256(manifest_path.read_bytes()),
        )
        fixture_dir = ROOT / "demo-project-1/challenges/delete-duplicates/fixtures"
        fixture_files = sorted(fixture_dir.glob("*.db"))
        self.assertEqual(9, len(fixture_files))
        for fixture_id, expected in tool.ORIGINAL_FIXTURE_SHA256.items():
            path = fixture_dir / (fixture_id + ".db")
            with self.subTest(fixture=fixture_id):
                self.assertEqual(expected, _sha256(path.read_bytes()))
                self.assertEqual(tool.ORIGINAL_FIXTURE_BYTES[fixture_id], path.stat().st_size)

    def test_manifest_timing_and_answer_kind_matrix(self):
        off = self.manifests["qa-timing-off-select1"]
        required = self.manifests["qa-timing-required-select1"]
        optional = self.manifests["qa-timing-optional-shared-sql"]
        mixed = self.manifests["qa-mixed-answer-kinds"]

        self.assertEqual("off", off["timing"])
        self.assertEqual("required", required["timing"])
        self.assertEqual("optional", optional["timing"])
        self.assertEqual("required", mixed["timing"])
        for manifest in [off, required, optional, mixed]:
            self.assertEqual("read", manifest["allowedOperation"])
            self.assertEqual(tool.ENGINE, manifest["engine"])
            self.assertTrue(all(part["required"] for part in manifest["parts"]))

        self.assertEqual(["sql"], [part["answerKind"] for part in off["parts"]])
        self.assertEqual(["sql"], [part["answerKind"] for part in required["parts"]])
        self.assertEqual(
            ["sql", "sql"], [part["answerKind"] for part in optional["parts"]]
        )
        self.assertEqual(
            ["sql", "structured", "check-definition"],
            [part["answerKind"] for part in mixed["parts"]],
        )
        self.assertEqual(["value-one", "value-two"], [p["id"] for p in optional["parts"]])
        self.assertEqual(
            ["duplicate-groups", "diagnosis", "recurrence-check"],
            [p["id"] for p in mixed["parts"]],
        )

    def test_fixture_paths_and_hashes_follow_the_core_convention(self):
        for challenge_id, manifest in self.manifests.items():
            self.assertEqual(
                f"challenges/{challenge_id}/1.json",
                (PROJECT_DIR / "challenges" / challenge_id / "1.json")
                .relative_to(PROJECT_DIR)
                .as_posix(),
            )
            for fixture in manifest["fixtureSuite"]["fixtures"]:
                path = (
                    PROJECT_DIR
                    / "challenges"
                    / challenge_id
                    / "fixtures"
                    / (fixture["id"] + ".db")
                )
                self.assertEqual(
                    f"challenges/{challenge_id}/fixtures/{fixture['id']}.db",
                    path.relative_to(PROJECT_DIR).as_posix(),
                )
                data = path.read_bytes()
                self.assertEqual(fixture["sha256"], _sha256(data))
                self.assertEqual(fixture["bytes"], len(data))
                self.assertLess(len(data), 10 * 1024 * 1024)

    def test_reference_sql_oracles_execute_on_real_sqlite(self):
        for challenge_id, manifest in self.manifests.items():
            errors = []
            tool.verify_manifest_semantics(manifest, PROJECT_DIR, errors)
            with self.subTest(challenge=challenge_id):
                self.assertEqual([], errors)

    def test_optional_shared_sql_cannot_pass_both_parts(self):
        manifest = self.manifests["qa-timing-optional-shared-sql"]
        connection = tool.sqlite3.connect(":memory:")
        try:
            connection.deserialize(
                (PROJECT_DIR / "challenges" / manifest["challengeId"] / "fixtures/basic.db").read_bytes()
            )
            rows, _ = tool.execute_query(connection, tool.SELECT_ONE_SQL)
        finally:
            connection.close()
        first = manifest["parts"][0]["sql"]["cases"][0]["oracle"]
        second = manifest["parts"][1]["sql"]["cases"][0]["oracle"]
        self.assertTrue(tool._compare_oracle(first, rows))
        self.assertFalse(tool._compare_oracle(second, rows))

        core = self.report.get("core") or {}
        if core.get("status") == "ok":
            receipt = core["receipts"]["qa-timing-optional-shared-sql"]["sharedSql"]
            self.assertEqual("pass", receipt["value-one"]["outcome"])
            self.assertEqual("fail", receipt["value-two"]["outcome"])

    def test_check_definition_outcome_matrix_and_control_query(self):
        manifest = self.manifests["qa-mixed-answer-kinds"]
        check_part = next(
            part for part in manifest["parts"] if part["answerKind"] == "check-definition"
        )
        cases = {
            case["fixture"]: case["expectedOutcome"]
            for case in check_part["checkDefinition"]["cases"]
        }
        self.assertEqual({"broken": "fail", "repaired": "pass"}, cases)

        def row_count(query_ref, fixture_id):
            connection = tool.sqlite3.connect(":memory:")
            try:
                connection.deserialize(
                    (
                        PROJECT_DIR
                        / "challenges"
                        / manifest["challengeId"]
                        / "fixtures"
                        / (fixture_id + ".db")
                    ).read_bytes()
                )
                rows, columns = tool.execute_query(
                    connection, tool.QUERY_ASSETS[query_ref]["sql"]
                )
            finally:
                connection.close()
            self.assertEqual(["email"], columns)
            return len(rows)

        for fixture_id, expected in cases.items():
            observed = "pass" if row_count("check/duplicate-emails", fixture_id) == 0 else "fail"
            self.assertEqual(expected, observed)
        self.assertEqual("pass", "pass" if row_count("check/always-empty", "broken") == 0 else "fail")

        core = self.report.get("core") or {}
        if core.get("status") == "ok":
            receipt = core["receipts"]["qa-mixed-answer-kinds"]
            self.assertEqual("pass", receipt["correct"]["check"]["outcome"])
            self.assertEqual("fail", receipt["wrongQuery"]["outcome"])
            self.assertEqual("fail", receipt["wrongExpectation"]["outcome"])
            self.assertEqual("unknown", receipt["missingExpectation"]["outcome"])
            self.assertEqual("error", receipt["missingExpectation"]["executionStatus"])

    def test_structured_answer_is_closed_and_required(self):
        manifest = self.manifests["qa-mixed-answer-kinds"]
        structured = next(
            part for part in manifest["parts"] if part["answerKind"] == "structured"
        )["structured"]
        fields = {field["id"]: field for field in structured["fields"]}
        self.assertEqual("single", fields["root-cause"]["cardinality"])
        self.assertEqual("multi", fields["remediation"]["cardinality"])
        self.assertTrue(fields["root-cause"]["required"])
        self.assertTrue(fields["remediation"]["required"])
        self.assertEqual(
            {
                "root-cause": ["duplicate-email-rows"],
                "remediation": ["deduplicate-then-constrain"],
            },
            structured["expected"]["selections"],
        )

        save_expectations = {
            "queryIds": ["check/duplicate-emails", "check/always-empty"],
            "expectation": tool.CHECK_EXPECTATION,
        }
        check_part = next(
            part for part in manifest["parts"] if part["answerKind"] == "check-definition"
        )
        self.assertEqual(save_expectations["queryIds"], check_part["checkDefinition"]["queryIds"])
        self.assertEqual(save_expectations["expectation"], check_part["checkDefinition"]["expectation"])

    def test_core_open_and_grading_when_sibling_worktree_is_available(self):
        core = self.report.get("core") or {}
        if core.get("status") == "unavailable":
            self.skipTest("sibling datatug-core worktree is not available")
        self.assertEqual("ok", core.get("status"), core)
        self.assertEqual([], core.get("errors") or [])
        self.assertTrue(core.get("coreRevision"))
        self.assertTrue(core.get("coreOpenSchemaClean"), core.get("coreOpenSchemaStatus"))
        receipts = core["receipts"]
        self.assertEqual("off", receipts["qa-timing-off-select1"]["timing"])
        self.assertEqual("required", receipts["qa-timing-required-select1"]["timing"])
        self.assertEqual("optional", receipts["qa-timing-optional-shared-sql"]["timing"])
        self.assertEqual("required", receipts["qa-mixed-answer-kinds"]["timing"])
        mixed = receipts["qa-mixed-answer-kinds"]
        self.assertEqual("pass", mixed["correct"]["sql"]["outcome"])
        self.assertEqual("pass", mixed["correct"]["structured"]["outcome"])
        self.assertEqual("pass", mixed["correct"]["check"]["outcome"])
        self.assertEqual("fail", mixed["wrongStructured"]["outcome"])
        self.assertEqual("unknown", mixed["unknownStructured"]["outcome"])
        self.assertEqual("fail", mixed["wrongSql"]["outcome"])
        self.assertEqual("fail", mixed["wrongQuery"]["outcome"])
        self.assertEqual("fail", mixed["wrongExpectation"]["outcome"])
        self.assertEqual("unknown", mixed["missingExpectation"]["outcome"])
        self.assertTrue(mixed["missingStructuredRefused"])
        self.assertTrue(mixed["missingCheckRefused"])


if __name__ == "__main__":
    unittest.main()
