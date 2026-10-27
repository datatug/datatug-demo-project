"""Tests for the six-case Phantom Orders training content package.

The tests import the trusted authoring tool, recompute every authored byte,
execute reference and alternate SQL against read-only in-memory copies of the
pinned SQLite fixtures, and prove the named wrong mutations fail. Core native
package/declaration/narrative admission is exercised separately with the
temporary Go helper documented in the lane report; these tests do not claim
browser/WASM execution.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts/phantom-orders.py"

_spec = importlib.util.spec_from_file_location("phantom_orders", TOOL_PATH)
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PhantomOrdersContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tool.verify(ROOT)
        if not cls.report["ok"]:
            raise AssertionError(cls.report["errors"])
        cls.assets = tool.build_assets()
        cls.package = json.loads(cls.assets["demo-project-1/training/phantom-orders/1/package.json"])
        cls.declaration = json.loads(
            cls.assets["demo-project-1/walkthroughs/phantom-orders/walkthrough.json"]
        )
        cls.sidecar = json.loads(
            cls.assets["demo-project-1/walkthroughs/phantom-orders/narrative.json"]
        )
        cls.catalogue = json.loads(
            cls.assets["demo-project-1/walkthroughs/phantom-orders/messages.en.json"]
        )

    def test_authored_assets_are_deterministic_and_committed(self):
        first = tool.build_assets()
        second = tool.build_assets()
        self.assertEqual(first, second)
        for relative, expected in first.items():
            with self.subTest(path=relative):
                self.assertEqual(expected, (ROOT / relative).read_bytes())
                self.assertEqual(_sha256(expected), _sha256((ROOT / relative).read_bytes()))

        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            tool.regenerate(temp_root)
            first_hashes = {
                path.relative_to(temp_root).as_posix(): _sha256(path.read_bytes())
                for path in sorted(temp_root.rglob("*"))
                if path.is_file()
            }
            tool.regenerate(temp_root)
            second_hashes = {
                path.relative_to(temp_root).as_posix(): _sha256(path.read_bytes())
                for path in sorted(temp_root.rglob("*"))
                if path.is_file()
            }
            committed_hashes = {
                relative: _sha256(data) for relative, data in first.items()
            }
            self.assertEqual(first_hashes, second_hashes)
            self.assertEqual(first_hashes, committed_hashes)

    def test_declaration_uses_the_real_loader_path_and_project_relative_pins(self):
        declaration_path = ROOT / "demo-project-1/walkthroughs/phantom-orders/walkthrough.json"
        self.assertTrue(declaration_path.is_file())
        self.assertEqual("datatug-walkthrough/2", self.declaration["schema"])
        self.assertEqual("phantom-orders", self.declaration["id"])
        self.assertEqual(1, self.declaration["version"])

        for reference in (
            self.declaration["trainingPackage"],
            self.declaration["narrative"],
        ):
            with self.subTest(path=reference["path"]):
                self.assertFalse(reference["path"].startswith("demo-project-1/"))
                self.assertTrue((ROOT / "demo-project-1" / reference["path"]).is_file())

        for asset in self.package["assets"]:
            with self.subTest(asset=asset["id"]):
                self.assertFalse(asset["path"].startswith("demo-project-1/"))
                self.assertTrue((ROOT / "demo-project-1" / asset["path"]).is_file())

        catalogue_ref = self.sidecar["messageCatalogues"][0]
        self.assertFalse(catalogue_ref["path"].startswith("demo-project-1/"))
        self.assertTrue((ROOT / "demo-project-1" / catalogue_ref["path"]).is_file())

    def test_six_ordered_chapters_and_native_engine_pin(self):
        chapter_ids = [chapter["id"] for chapter in self.declaration["chapters"]]
        self.assertEqual(
            [
                "duplicate-payments",
                "payment-impact",
                "failure-window",
                "retry-evidence",
                "root-cause",
                "prevention",
            ],
            chapter_ids,
        )
        self.assertEqual(len(self.package["challenges"]), 6)
        self.assertEqual(
            chapter_ids,
            [challenge["id"] for challenge in self.package["challenges"]],
        )
        for challenge in self.package["challenges"]:
            manifest_asset = next(
                asset
                for asset in self.package["assets"]
                if asset["id"] == challenge["manifestAssetId"]
            )
            manifest = json.loads(
                (ROOT / "demo-project-1" / manifest_asset["path"]).read_bytes()
            )
            with self.subTest(challenge=challenge["id"]):
                self.assertEqual(
                    {
                        "package": "@sqlite.org/sqlite-wasm",
                        "version": "3.54.1-build1",
                        "sqliteVersion": "3.54.1",
                    },
                    manifest["engine"],
                )
                self.assertEqual(challenge["id"], manifest["challengeId"])
                self.assertEqual(1, manifest["revision"])
                suite = {
                    fixture["id"]: (fixture["sha256"], fixture["bytes"])
                    for fixture in manifest["fixtureSuite"]["fixtures"]
                }
                mapped = {
                    fixture["fixtureId"]: fixture["assetId"]
                    for fixture in challenge["fixtures"]
                }
                self.assertEqual(set(suite), set(mapped))
                for fixture_id, asset_id in mapped.items():
                    asset = next(
                        asset for asset in self.package["assets"] if asset["id"] == asset_id
                    )
                    data = (ROOT / "demo-project-1" / asset["path"]).read_bytes()
                    self.assertEqual(suite[fixture_id], (_sha256(data), len(data)))

    def test_reference_and_alternate_sql_match_every_declared_case(self):
        manifests = tool.build_manifests()
        fixture_data = {}
        for asset in self.package["assets"]:
            if asset["kind"] == "challenge-fixture":
                fixture_data[asset["id"].removeprefix("fixture-")] = (
                    ROOT / "demo-project-1" / asset["path"]
                ).read_bytes()

        for challenge_id, manifest in manifests.items():
            for part in manifest["parts"]:
                if part["answerKind"] != "sql":
                    continue
                for case in part["sql"]["cases"]:
                    fixture = fixture_data[case["fixture"]]
                    with self.subTest(challenge=challenge_id, part=part["id"], fixture=case["fixture"]):
                        self.assertTrue(
                            tool._sql_matches(
                                fixture,
                                tool.REFERENCE_SQL[challenge_id],
                                case["oracle"],
                            )
                        )
                        self.assertTrue(
                            tool._sql_matches(
                                fixture,
                                tool.ALTERNATE_SQL[challenge_id],
                                case["oracle"],
                            )
                        )

    def test_named_wrong_sql_mutations_are_rejected(self):
        self.assertEqual(
            {
                "duplicate-payments": {"omit-status-filter": "rejected", "omit-having": "rejected"},
                "payment-impact": {
                    "sum-all-statuses": "rejected",
                    "subtract-per-payment": "rejected",
                    "include-1003": "rejected",
                    "cross-join": "rejected",
                },
                "failure-window": {
                    "min-all-successes": "rejected",
                    "group-failed-retries": "rejected",
                    "third-success": "rejected",
                },
                "retry-evidence": {
                    "all-retries": "rejected",
                    "join-by-amount": "rejected",
                    "only-r2": "rejected",
                },
                "root-cause": {"all-retry-groups": "rejected", "only-r2": "rejected"},
                "prevention": {"always-empty": "rejected", "only-1002": "rejected"},
            },
            self.report["wrongMutations"],
        )

    def test_prevention_check_broken_repaired_mutated_matrix(self):
        self.assertEqual(
            {"base": "fail", "repaired": "pass", "mutated": "fail"},
            self.report["preventionMatrix"],
        )
        check_asset = next(asset for asset in self.package["assets"] if asset["id"] == "check-prevention-definition")
        check = json.loads((ROOT / "demo-project-1" / check_asset["path"]).read_bytes())
        self.assertEqual("prevention-check", check["id"])
        self.assertEqual("prevention/affected-orders", check["steps"][0]["queryId"])
        self.assertEqual(
            {
                "id": "zero-affected-orders",
                "scope": "set",
                "kind": "row-count",
                "severity": "error",
                "expected": {"type": "integer", "value": "0"},
            },
            check["steps"][0]["validators"][0],
        )
        manifest_asset = next(
            asset
            for asset in self.package["assets"]
            if asset["id"] == "manifest-prevention"
        )
        manifest = json.loads((ROOT / "demo-project-1" / manifest_asset["path"]).read_bytes())
        check_part = next(part for part in manifest["parts"] if part["answerKind"] == "check-definition")
        self.assertEqual(
            [
                {"fixture": "base", "expectedOutcome": "fail"},
                {"fixture": "repaired", "expectedOutcome": "pass"},
                {"fixture": "mutated", "expectedOutcome": "fail"},
            ],
            check_part["checkDefinition"]["cases"],
        )

    def test_watch_stays_a_disabled_proposal(self):
        proposal = next(item for item in self.package["proposals"] if item["id"] == "watch-proposal")
        self.assertEqual("watch", proposal["kind"])
        self.assertEqual("watch-recommendation", proposal["definitionId"])
        watch_asset = next(asset for asset in self.package["assets"] if asset["id"] == "watch-recommendation")
        watch = json.loads((ROOT / "demo-project-1" / watch_asset["path"]).read_bytes())
        self.assertEqual("prevention-check", watch["checkId"])
        self.assertEqual("1", watch["checkVersion"])
        self.assertNotIn("enabled", watch)
        self.assertNotIn("owner", watch)
        self.assertNotIn("lifecycle", watch)
        self.assertNotIn("providers", watch)

    def test_absent_config_variant_is_insufficient_and_leak_free(self):
        self.assertEqual(["insufficient-evidence"], self.report["variantCause"])
        self.assertEqual(["unknown"], self.report["variantDeployment"])
        self.assertEqual(["trace-r2", "trace-r4"], self.report["variantCitations"])
        self.assertEqual(
            [("pay-16", None), ("pay-17", None)],
            self.report["variantFlags"],
        )

        variant_root = ROOT / "demo-project-1/training/phantom-orders/1/variants/absent-config"
        variant_package = json.loads((variant_root / "package.json").read_bytes())
        variant_manifest_asset = next(
            asset for asset in variant_package["assets"] if asset["kind"] == "challenge-manifest"
        )
        variant_manifest = json.loads(
            (ROOT / "demo-project-1" / variant_manifest_asset["path"]).read_bytes()
        )
        variant_text = json.dumps(variant_package, ensure_ascii=False)
        variant_text += json.dumps(variant_manifest, ensure_ascii=False)
        variant_text += (variant_root / "narrative.json").read_text()
        variant_text += (variant_root / "messages.en.json").read_text()
        for forbidden in (
            "config-pay-17",
            "idempotency_enabled=1",
            "idempotency_enabled=0",
            "omitted the idempotency header",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, variant_text)

        citations = next(part for part in variant_manifest["parts"] if part["id"] == "citations")
        self.assertNotIn(
            "config-pay-17",
            [option["id"] for option in citations["structured"]["fields"][0]["options"]],
        )

        # The causal answers remain explicitly wrong for the variant.
        cause = next(part for part in variant_manifest["parts"] if part["id"] == "cause")
        deployment = next(
            part for part in variant_manifest["parts"] if part["id"] == "deployment"
        )
        self.assertEqual(
            ["insufficient-evidence"],
            cause["structured"]["expected"]["selections"]["cause"],
        )
        self.assertEqual(
            ["unknown"],
            deployment["structured"]["expected"]["selections"]["deployment"],
        )
        self.assertNotIn(
            "missing-retry-idempotency",
            cause["structured"]["expected"]["selections"]["cause"],
        )
        self.assertNotIn(
            "pay-17",
            deployment["structured"]["expected"]["selections"]["deployment"],
        )

        root_cause = tool.build_manifests()["root-cause"]
        root_cause_values = next(
            part for part in root_cause["parts"] if part["id"] == "cause"
        )
        self.assertEqual(
            ["missing-retry-idempotency"],
            root_cause_values["structured"]["expected"]["selections"]["cause"],
        )
        self.assertNotIn(
            "provider-double-send",
            root_cause_values["structured"]["expected"]["selections"]["cause"],
        )

    def test_second_success_minute_recap_matches_reference_output(self):
        evidence = json.loads(
            (ROOT / "demo-project-1/training/phantom-orders/1/evidence/duplicate-minutes.json").read_bytes()
        )
        self.assertEqual(
            [
                [
                    {"type": "string", "value": "2026-01-12T10:01"},
                    {"type": "integer", "value": "1"},
                ],
                [
                    {"type": "string", "value": "2026-01-12T10:03"},
                    {"type": "integer", "value": "1"},
                ],
            ],
            evidence["rows"],
        )

    def test_structured_and_check_wrong_answers_are_rejected(self):
        manifests = tool.build_manifests()
        for challenge_id in ("failure-window", "retry-evidence", "root-cause", "prevention"):
            manifest = manifests[challenge_id]
            for part in manifest["parts"]:
                if part["answerKind"] != "structured":
                    continue
                for field in part["structured"]["fields"]:
                    expected = set(
                        part["structured"]["expected"]["selections"][field["id"]]
                    )
                    wrong = {
                        option["id"] for option in field["options"] if option["id"] not in expected
                    }
                    with self.subTest(challenge=challenge_id, part=part["id"]):
                        self.assertTrue(wrong)
                        self.assertNotEqual(expected, wrong)

        fixture_data = {}
        for asset in self.package["assets"]:
            if asset["kind"] == "challenge-fixture":
                fixture_data[asset["id"].removeprefix("fixture-")] = (
                    ROOT / "demo-project-1" / asset["path"]
                ).read_bytes()

        # An always-pass expectation (for example row-count 5) does not match
        # the repaired fixture's pass semantics and cannot detect the repaired
        # state correctly.
        outcomes = {
            name: tool._check_outcome(fixture_data[name], tool.REFERENCE_SQL["prevention"], 5)
            for name in ("base", "repaired", "mutated")
        }
        self.assertNotEqual(
            {"base": "fail", "repaired": "pass", "mutated": "fail"},
            outcomes,
        )
        # WHERE 1=0 hides the broken data: it passes the broken fixture, which
        # is not the declared prevention semantics.
        always_empty = tool.WRONG_SQL["prevention"]["always-empty"]
        always_empty_outcomes = {
            name: tool._check_outcome(fixture_data[name], always_empty, 0)
            for name in ("base", "repaired", "mutated")
        }
        self.assertEqual("pass", always_empty_outcomes["base"])
        self.assertNotEqual(
            {"base": "fail", "repaired": "pass", "mutated": "fail"},
            always_empty_outcomes,
        )

    def test_no_top_level_registration_or_project_catalogue_edit(self):
        datatug = (ROOT / ".datatug.yaml").read_text()
        self.assertIn("demo-project-1", datatug)
        self.assertNotIn("phantom-orders", datatug)
        project = json.loads((ROOT / "demo-project-1/datatug-project.json").read_text())
        self.assertEqual("datatug-demo-project", project["id"])
        self.assertNotIn("phantom-orders", json.dumps(project))

    def test_sidecar_binds_each_dialogue_step_and_waits_on_the_real_challenge(self):
        dialogue_steps = {
            step["segmentId"]: (chapter["id"], step["id"])
            for chapter in self.declaration["chapters"]
            for step in chapter["steps"]
            if step["kind"] == "scripted-dialogue"
        }
        self.assertEqual(
            [chapter["id"] for chapter in self.declaration["chapters"]],
            self.sidecar["chapterRefs"],
        )
        self.assertEqual(set(dialogue_steps), {segment["id"] for segment in self.sidecar["segments"]})
        for segment in self.sidecar["segments"]:
            with self.subTest(segment=segment["id"]):
                self.assertEqual(dialogue_steps[segment["id"]], (segment["chapterId"], segment["stepId"]))
                event_types = {
                    event["type"]
                    for event in self.sidecar["events"]
                    if event["id"] in segment["eventIds"]
                }
                self.assertIn("challenge.prompt", event_types)
                self.assertIn("challenge.await_validation", event_types)
        message_keys = {event["payload"]["messageKey"] for event in self.sidecar["events"] if event["type"] == "chat.message"}
        self.assertTrue(message_keys.issubset(self.catalogue["messages"].keys()))


if __name__ == "__main__":
    unittest.main()
