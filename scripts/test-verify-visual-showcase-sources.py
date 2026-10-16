#!/usr/bin/env python3
"""Local shape/failure tests; synthetic responses are not live receipts."""

import importlib.util
import json
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("verify-visual-showcase-sources.py")
SPEC = importlib.util.spec_from_file_location("verify_visual_showcase_sources", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def response(database="northwind", collection="Orders", complete=True):
    return {
        "records": [
            {"data": {"ShipCountry": f"Country{i:02d}", "orders": i + 1}}
            for i in range(21)
        ],
        "complete": complete,
        "execution": {
            "rowsReturned": 21,
            "sources": [{"database": database, "collection": collection}],
        },
    }


class VerifierTests(unittest.TestCase):
    def verify(self, value, database="northwind", collection="Orders"):
        return MODULE.verify(json.dumps(value).encode(), "test", database, collection)

    def test_valid_response_emits_source_and_digests(self):
        rows, receipt = self.verify(response())
        self.assertEqual(len(rows), 21)
        self.assertEqual(receipt["database"], "northwind")
        self.assertEqual(receipt["collection"], "Orders")
        self.assertEqual(len(receipt["mappedRowsSha256"]), 64)

    def test_incomplete_response_fails(self):
        with self.assertRaisesRegex(ValueError, "complete=true"):
            self.verify(response(complete=False))

    def test_source_identity_mismatch_fails(self):
        with self.assertRaisesRegex(ValueError, "source database mismatch"):
            self.verify(response(database="other"))

    def test_collection_identity_requires_exact_match(self):
        with self.assertRaisesRegex(ValueError, "source collection mismatch"):
            self.verify(response(collection="OrdersExtra"))
        pg = response(database="northwind-postgresql", collection=MODULE.PG_COLLECTION + "Extra")
        with self.assertRaisesRegex(ValueError, "source collection mismatch"):
            self.verify(pg, "northwind-postgresql", MODULE.PG_COLLECTION)
        _, receipt = self.verify(
            response(database="northwind-postgresql", collection=MODULE.PG_COLLECTION),
            "northwind-postgresql", MODULE.PG_COLLECTION,
        )
        self.assertEqual(receipt["collection"], MODULE.PG_COLLECTION)

    def test_wrong_rows_and_duplicate_country_fail(self):
        value = response()
        value["records"].pop()
        with self.assertRaisesRegex(ValueError, "exactly 21 records"):
            self.verify(value)
        value = response()
        value["records"][1]["data"]["ShipCountry"] = "Country00"
        with self.assertRaisesRegex(ValueError, "not unique"):
            self.verify(value)

    def test_wrong_count_type_fails(self):
        value = response()
        value["records"][0]["data"]["orders"] = "1"
        with self.assertRaisesRegex(ValueError, "invalid orders count"):
            self.verify(value)

    def test_race_requires_complete_bounded_result(self):
        with self.assertRaisesRegex(ValueError, "complete=true"):
            MODULE.verify_race(json.dumps({"complete": False}).encode())
        with self.assertRaisesRegex(ValueError, "exactly 830 records"):
            MODULE.verify_race(json.dumps({"complete": True, "records": []}).encode())


if __name__ == "__main__":
    unittest.main()
