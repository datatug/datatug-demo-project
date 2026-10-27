#!/usr/bin/env python3
"""Author and verify the six-case Phantom Orders training content package.

The package lives entirely under ``demo-project-1/training/phantom-orders/1``
and is declared by ``demo-project-1/walkthroughs/phantom-orders/walkthrough.json``.
``regenerate`` is the only writer. ``verify`` never writes committed assets: it
recomputes every authored byte, checks every pin, executes every reference and
alternate SQL answer against read-only in-memory copies of the pinned SQLite
fixtures, and proves the named wrong mutations fail.

Python's native SQLite module is the reference engine in this tool. The package
manifests are pinned to the browser engine used by DataTug's challenge runtime
(``@sqlite.org/sqlite-wasm`` 3.54.1-build1, SQLite 3.54.1). Native Python SQL
results are not browser/WASM acceptance; the report keeps that distinction.

Usage from the repository root:

    python3 scripts/phantom-orders.py regenerate
    python3 scripts/phantom-orders.py verify

The module is imported by ``tests/test_phantom_orders.py``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "demo-project-1"
# Project-root-relative paths used inside declarations and package indexes.
TRAINING_REL = "training/phantom-orders/1"
VARIANT_REL = f"{TRAINING_REL}/variants/absent-config"
DECLARATION_REL = "walkthroughs/phantom-orders"
# Repository-relative paths used only for writing and reading local files.
TRAINING = f"{PROJECT}/{TRAINING_REL}"
VARIANT = f"{PROJECT}/{VARIANT_REL}"
DECLARATION_DIR = f"{PROJECT}/{DECLARATION_REL}"

SCHEMA_PACKAGE = "datatug-training-package/1"
SCHEMA_WALKTHROUGH = "datatug-walkthrough/2"
SCHEMA_NARRATIVE = 1
SCHEMA_CATALOGUE = 1

ENGINE = {
    "package": "@sqlite.org/sqlite-wasm",
    "version": "3.54.1-build1",
    "sqliteVersion": "3.54.1",
}

SCENARIO = "phantom-orders"
REVISION = 1
SCENARIO_TITLE = "The Phantom Orders"

CHAPTERS = [
    ("duplicate-payments", "Find duplicate successful payments"),
    ("payment-impact", "Connect payments and orders"),
    ("failure-window", "Find when the bug began"),
    ("retry-evidence", "Investigate retries and logs"),
    ("root-cause", "Prove the root cause"),
    ("prevention", "Prevent recurrence"),
]

ACTORS = [
    ("sarah", "Sarah"),
    ("maya", "Maya"),
    ("daniel", "Daniel"),
    ("incidentius", "Incidentius"),
]

VISIBLE_SCHEMA = {
    "tables": [
        {
            "name": "orders",
            "columns": [
                {"name": "id", "type": "integer", "primaryKey": True},
                {"name": "customer_id", "type": "integer"},
                {"name": "total_cents", "type": "integer"},
            ],
        },
        {
            "name": "payments",
            "columns": [
                {"name": "id", "type": "integer", "primaryKey": True},
                {"name": "order_id", "type": "integer"},
                {"name": "attempt_id", "type": "string"},
                {"name": "status", "type": "string"},
                {"name": "amount_cents", "type": "integer"},
                {"name": "created_at", "type": "datetime"},
            ],
        },
        {
            "name": "retry_events",
            "columns": [
                {"name": "attempt_id", "type": "string"},
                {"name": "request_id", "type": "string"},
                {"name": "idempotency_key", "type": "string"},
                {"name": "outcome", "type": "string"},
                {"name": "created_at", "type": "datetime"},
            ],
        },
        {
            "name": "deployments",
            "columns": [
                {"name": "version", "type": "string"},
                {"name": "deployed_at", "type": "datetime"},
                {"name": "idempotency_enabled", "type": "integer"},
            ],
        },
    ]
}

REFERENCE_SQL = {
    "duplicate-payments": (
        "SELECT order_id, COUNT(*) AS successful_count\n"
        "FROM payments\n"
        "WHERE status='succeeded'\n"
        "GROUP BY order_id\n"
        "HAVING COUNT(*)>1;\n"
    ),
    "payment-impact": (
        "SELECT o.id AS order_id,o.customer_id,SUM(p.amount_cents)-o.total_cents AS excess_cents\n"
        "FROM orders o\n"
        "JOIN payments p ON p.order_id=o.id AND p.status='succeeded'\n"
        "GROUP BY o.id,o.customer_id,o.total_cents\n"
        "HAVING COUNT(*)>1;\n"
    ),
    "failure-window": (
        "WITH ranked AS (\n"
        "  SELECT order_id,created_at,ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY created_at,id) AS n\n"
        "  FROM payments\n"
        "  WHERE status='succeeded'\n"
        ")\n"
        "SELECT MIN(created_at) AS first_duplicate_at\n"
        "FROM ranked\n"
        "WHERE n=2;\n"
    ),
    "retry-evidence": (
        "SELECT r.request_id,COUNT(*) AS successes\n"
        "FROM retry_events r\n"
        "JOIN payments p ON p.attempt_id=r.attempt_id\n"
        "WHERE p.status='succeeded'\n"
        "GROUP BY r.request_id\n"
        "HAVING COUNT(*)>1;\n"
    ),
    "root-cause": (
        "WITH duplicate_requests AS (\n"
        "  SELECT r.request_id\n"
        "  FROM retry_events r\n"
        "  JOIN payments p ON p.attempt_id=r.attempt_id\n"
        "  WHERE p.status='succeeded' AND r.idempotency_key IS NULL\n"
        "  GROUP BY r.request_id\n"
        "  HAVING COUNT(*)>1\n"
        ")\n"
        "SELECT request_id FROM duplicate_requests;\n"
    ),
    "prevention": (
        "SELECT order_id\n"
        "FROM payments\n"
        "WHERE status='succeeded'\n"
        "GROUP BY order_id\n"
        "HAVING COUNT(*)>1;\n"
    ),
}

ALTERNATE_SQL = {
    "duplicate-payments": (
        "WITH counted AS (\n"
        "  SELECT order_id, COUNT(*) OVER (PARTITION BY order_id) AS successful_count\n"
        "  FROM payments\n"
        "  WHERE status='succeeded'\n"
        ")\n"
        "SELECT DISTINCT order_id, successful_count\n"
        "FROM counted\n"
        "WHERE successful_count > 1;\n"
    ),
    "payment-impact": (
        "WITH totals AS (\n"
        "  SELECT order_id, SUM(amount_cents) AS paid_cents, COUNT(*) AS successes\n"
        "  FROM payments\n"
        "  WHERE status='succeeded'\n"
        "  GROUP BY order_id\n"
        ")\n"
        "SELECT o.id AS order_id,o.customer_id,t.paid_cents-o.total_cents AS excess_cents\n"
        "FROM orders o\n"
        "JOIN totals t ON t.order_id=o.id\n"
        "WHERE t.successes>1;\n"
    ),
    "failure-window": (
        "SELECT MIN(p.created_at) AS first_duplicate_at\n"
        "FROM payments p\n"
        "WHERE p.status='succeeded'\n"
        "  AND (\n"
        "    SELECT COUNT(*)\n"
        "    FROM payments q\n"
        "    WHERE q.order_id=p.order_id\n"
        "      AND q.status='succeeded'\n"
        "      AND (q.created_at < p.created_at OR (q.created_at=p.created_at AND q.id<=p.id))\n"
        "  ) = 2;\n"
    ),
    "retry-evidence": (
        "WITH successful AS (\n"
        "  SELECT r.request_id, COUNT(*) AS successes\n"
        "  FROM retry_events r\n"
        "  JOIN payments p ON p.attempt_id=r.attempt_id\n"
        "  WHERE p.status='succeeded'\n"
        "  GROUP BY r.request_id\n"
        ")\n"
        "SELECT request_id, successes FROM successful WHERE successes>1;\n"
    ),
    "root-cause": (
        "SELECT request_id FROM (\n"
        "  SELECT r.request_id, COUNT(*) AS successes\n"
        "  FROM retry_events r\n"
        "  JOIN payments p ON p.attempt_id=r.attempt_id\n"
        "  WHERE p.status='succeeded' AND r.idempotency_key IS NULL\n"
        "  GROUP BY r.request_id\n"
        ")\n"
        "WHERE successes>1;\n"
    ),
    "prevention": (
        "WITH counts AS (\n"
        "  SELECT order_id, COUNT(*) AS successes\n"
        "  FROM payments\n"
        "  WHERE status='succeeded'\n"
        "  GROUP BY order_id\n"
        ")\n"
        "SELECT order_id FROM counts WHERE successes>1;\n"
    ),
}

WRONG_SQL = {
    "duplicate-payments": {
        "omit-status-filter": (
            "SELECT order_id, COUNT(*) AS successful_count\n"
            "FROM payments\n"
            "GROUP BY order_id\n"
            "HAVING COUNT(*)>1;\n"
        ),
        "omit-having": (
            "SELECT order_id, COUNT(*) AS successful_count\n"
            "FROM payments\n"
            "WHERE status='succeeded'\n"
            "GROUP BY order_id;\n"
        ),
    },
    "payment-impact": {
        "sum-all-statuses": (
            "SELECT o.id AS order_id,o.customer_id,SUM(p.amount_cents)-o.total_cents AS excess_cents\n"
            "FROM orders o\n"
            "JOIN payments p ON p.order_id=o.id\n"
            "GROUP BY o.id,o.customer_id,o.total_cents\n"
            "HAVING COUNT(*)>1;\n"
        ),
        "subtract-per-payment": (
            "SELECT o.id AS order_id,o.customer_id,SUM(p.amount_cents-o.total_cents) AS excess_cents\n"
            "FROM orders o\n"
            "JOIN payments p ON p.order_id=o.id AND p.status='succeeded'\n"
            "GROUP BY o.id,o.customer_id,o.total_cents\n"
            "HAVING COUNT(*)>1;\n"
        ),
        "include-1003": (
            "SELECT o.id AS order_id,o.customer_id,SUM(p.amount_cents)-o.total_cents AS excess_cents\n"
            "FROM orders o\n"
            "JOIN payments p ON p.order_id=o.id AND p.status='succeeded'\n"
            "WHERE o.id IN (1002,1003,1004)\n"
            "GROUP BY o.id,o.customer_id,o.total_cents;\n"
        ),
        "cross-join": (
            "SELECT o.id AS order_id,o.customer_id,SUM(p.amount_cents)-o.total_cents AS excess_cents\n"
            "FROM orders o\n"
            "JOIN payments p ON 1=1\n"
            "WHERE p.status='succeeded'\n"
            "GROUP BY o.id,o.customer_id,o.total_cents\n"
            "HAVING COUNT(*)>1;\n"
        ),
    },
    "failure-window": {
        "min-all-successes": (
            "SELECT MIN(created_at) AS first_duplicate_at\n"
            "FROM payments\n"
            "WHERE status='succeeded';\n"
        ),
        "group-failed-retries": (
            "SELECT MIN(created_at) AS first_duplicate_at\n"
            "FROM payments\n"
            "WHERE status='failed';\n"
        ),
        "third-success": (
            "WITH ranked AS (\n"
            "  SELECT order_id,created_at,ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY created_at,id) AS n\n"
            "  FROM payments\n"
            "  WHERE status='succeeded'\n"
            ")\n"
            "SELECT MIN(created_at) AS first_duplicate_at\n"
            "FROM ranked\n"
            "WHERE n=3;\n"
        ),
    },
    "retry-evidence": {
        "all-retries": (
            "SELECT request_id, COUNT(*) AS successes\n"
            "FROM retry_events\n"
            "GROUP BY request_id\n"
            "HAVING COUNT(*)>1;\n"
        ),
        "join-by-amount": (
            "SELECT r.request_id,COUNT(*) AS successes\n"
            "FROM retry_events r\n"
            "JOIN payments p ON p.amount_cents = 3000\n"
            "WHERE p.status='succeeded'\n"
            "GROUP BY r.request_id\n"
            "HAVING COUNT(*)>1;\n"
        ),
        "only-r2": (
            "SELECT r.request_id,COUNT(*) AS successes\n"
            "FROM retry_events r\n"
            "JOIN payments p ON p.attempt_id=r.attempt_id\n"
            "WHERE p.status='succeeded' AND r.request_id='r2'\n"
            "GROUP BY r.request_id\n"
            "HAVING COUNT(*)>1;\n"
        ),
    },
    "root-cause": {
        "all-retry-groups": (
            "SELECT request_id\n"
            "FROM retry_events\n"
            "GROUP BY request_id\n"
            "HAVING COUNT(*)>1;\n"
        ),
        "only-r2": (
            "SELECT r.request_id\n"
            "FROM retry_events r\n"
            "JOIN payments p ON p.attempt_id=r.attempt_id\n"
            "WHERE p.status='succeeded' AND r.request_id='r2'\n"
            "GROUP BY r.request_id\n"
            "HAVING COUNT(*)>1;\n"
        ),
    },
    "prevention": {
        "always-empty": "SELECT order_id FROM payments WHERE 1=0;\n",
        "only-1002": (
            "SELECT order_id\n"
            "FROM payments\n"
            "WHERE status='succeeded' AND order_id=1002\n"
            "GROUP BY order_id\n"
            "HAVING COUNT(*)>1;\n"
        ),
    },
}

MESSAGES = {
    "context.supplied": (
        "Supplied fictional context only; earlier training cases are not marked complete."
    ),
    "ch1.sarah.context": (
        "Three customers contacted support about repeated charges. These reports may overlap; can we find the affected orders?"
    ),
    "ch1.maya.context": (
        "First count successful payments per order. Failed attempts must not count as charges."
    ),
    "ch1.daniel.context": (
        "A retry is not automatically a duplicate. Some retries recover failed payments."
    ),
    "ch1.incidentius.open": (
        "Training case DC-001 opened: identify duplicate successful payments."
    ),
    "ch1.maya.success": (
        "Orders 1002 and 1004 each have two successful charges. Now quantify the customer impact."
    ),
    "ch2.sarah.context": (
        "Support needs affected customers and excess charges, not just payment IDs."
    ),
    "ch2.maya.context": (
        "Join the successful payment totals to orders. Preserve one result row per affected order."
    ),
    "ch2.daniel.context": (
        "The refunded event is a distractor here. This task measures duplicate successful charges before remediation."
    ),
    "ch2.sarah.success": (
        "That gives support a precise cohort and 11000 cents of duplicate charges."
    ),
    "ch3.maya.context": (
        "When did the data first demonstrate a second successful charge?"
    ),
    "ch3.daniel.context": (
        "Use the second success for each order. A first charge can be entirely valid."
    ),
    "ch3.sarah.context": (
        "Please distinguish the earliest observation from the exact moment the defect was introduced."
    ),
    "ch3.daniel.success": (
        "The first observed duplicate is at 10:01:03. That narrows the search, but does not prove a deployment caused it."
    ),
    "ch4.daniel.context": (
        "The provider accepted a2, then our handler timed out. a3 retried the same request."
    ),
    "ch4.maya.context": (
        "Find the second affected request and compare it with a harmless retry."
    ),
    "ch4.sarah.context": (
        "Keep the request IDs with the evidence so another person can reproduce this conclusion."
    ),
    "ch4.maya.success": (
        "Two retried requests produced two successful charges each; r3 recovered a failure safely."
    ),
    "ch5.daniel.complete": (
        "Release pay-17 omitted the idempotency header on retry requests. Here is the reviewed configuration diff."
    ),
    "ch5.maya.context": (
        "Does that explanation account for both affected requests, and what would refute it?"
    ),
    "ch5.sarah.context": (
        "Do we have enough evidence to explain this to customers without guessing?"
    ),
    "ch5.daniel.success.complete": (
        "The diff and repeated successful request traces support the missing safeguard. We should restore it and verify recurrence prevention."
    ),
    "ch6.maya.context": (
        "Turn the duplicate-charge query into a Check. Prove it detects broken data and accepts repaired data."
    ),
    "ch6.daniel.context": (
        "A Watch can later run that Check, but training must not activate a production monitor."
    ),
    "ch6.sarah.context": (
        "The postmortem should cite the evidence and state the verification we performed."
    ),
    "ch6.incidentius.proposal": (
        "Training recommendation recorded for watch-proposal; it stays disabled and unscheduled."
    ),
    "ch6.maya.success": (
        "The Check detects recurrence in our fixtures. The Watch remains a proposal for a separately authorized owner."
    ),
    "ch6.synthetic": (
        "Synthetic validation only; no production Watch is enrolled."
    ),
    "ch6.postmortem": (
        "Postmortem cites config-pay-17, trace-r2 and trace-r4; verified broken to fail, repaired to pass, mutated to fail."
    ),
    "absent.daniel.missing": (
        "We have no reviewed configuration diff for pay-17 yet. We can compare timestamps and retries, but the cause is still unconfirmed."
    ),
    "absent.daniel.success": (
        "Correct: the retries and timestamps narrow the investigation, but we need the reviewed configuration diff before confirming the cause."
    ),
    "absent.maya.context": (
        "Name the uncertainty rather than a cause; select only the duplicate request traces."
    ),
    "absent.sarah.context": (
        "Can we explain this to customers without guessing?"
    ),
}

HINTS = {
    "duplicate-payments": [
        ("filter-successes", "Filter to succeeded payment events first."),
        ("having-groups", "Use HAVING to keep only order groups with more than one success."),
        ("failed-retry", "A failed attempt followed by one success is a recovered retry, not a duplicate charge."),
        ("failure", "Check whether every counted row really represents a successful charge."),
    ],
    "payment-impact": [
        ("order-grain", "Aggregate successful payments at order grain before joining orders."),
        ("one-row", "Preserve one result row per affected order and subtract the order total once."),
        ("status", "Do not sum failed or refunded events as successful charges."),
    ],
    "failure-window": [
        ("second-success", "Rank successful events per order and look at the second one."),
        ("observation", "The earliest observation is not proof of the exact defect introduction time."),
        ("ordering", "Use deterministic (created_at, id) ordering for ties."),
    ],
    "retry-evidence": [
        ("attempt-id", "Correlate retry_events to payments by attempt_id, then group by request_id."),
        ("harmless", "r3 has two attempts but only one successful payment; it is a recovered failure."),
        ("pairing", "Select the two duplicate request pairs and their matching trace attachments."),
    ],
    "root-cause": [
        ("null-keys", "The duplicate request cohort is the set with NULL idempotency keys and more than one success."),
        ("correlation", "Deployment proximity alone is correlation; the reviewed diff and both traces are required."),
        ("refute", "Ask what evidence would refute the explanation, and do not treat a4's failure as the cause."),
    ],
    "prevention": [
        ("zero-rows", "The Check should count affected orders and expect zero rows."),
        ("matrix", "Prove broken data fails, repaired data passes, and a different affected order still fails."),
        ("watch", "The Watch is an unsaved recommendation; training never activates a production monitor."),
    ],
    "root-cause-absent-config": [
        ("cohort", "The retry cohort still shows r2 and r4 with NULL idempotency keys."),
        ("uncertainty", "Deployment timestamps and retries narrow the investigation, but no reviewed configuration diff is declared."),
        ("answer", "Choose insufficient evidence, an unknown deployment, and only the two duplicate traces."),
    ],
}


# ---------------------------------------------------------------------------
# Fixture data and typed oracles
# ---------------------------------------------------------------------------


def _base_tables() -> dict[str, list[tuple[Any, ...]]]:
    return {
        "orders": [
            (1001, 11, 5000),
            (1002, 12, 3000),
            (1003, 13, 2000),
            (1004, 14, 8000),
        ],
        "payments": [
            (1, 1001, "a1", "succeeded", 5000, "2026-01-12T09:58:00Z"),
            (2, 1002, "a2", "succeeded", 3000, "2026-01-12T10:01:00Z"),
            (3, 1002, "a3", "succeeded", 3000, "2026-01-12T10:01:03Z"),
            (4, 1003, "a4", "failed", 2000, "2026-01-12T10:02:00Z"),
            (5, 1003, "a5", "succeeded", 2000, "2026-01-12T10:02:05Z"),
            (6, 1004, "a6", "succeeded", 8000, "2026-01-12T10:03:00Z"),
            (7, 1004, "a7", "succeeded", 8000, "2026-01-12T10:03:02Z"),
            (8, 1004, "a8", "refunded", 8000, "2026-01-12T10:05:00Z"),
        ],
        "retry_events": [
            ("a1", "r1", "k1", "succeeded", "2026-01-12T09:58:00Z"),
            ("a2", "r2", None, "provider-success", "2026-01-12T10:01:00Z"),
            ("a3", "r2", None, "provider-success", "2026-01-12T10:01:03Z"),
            ("a4", "r3", None, "failed", "2026-01-12T10:02:00Z"),
            ("a5", "r3", None, "provider-success", "2026-01-12T10:02:05Z"),
            ("a6", "r4", None, "provider-success", "2026-01-12T10:03:00Z"),
            ("a7", "r4", None, "provider-success", "2026-01-12T10:03:02Z"),
            ("a8", "r5", "k5", "refunded", "2026-01-12T10:05:00Z"),
        ],
        "deployments": [
            ("pay-16", "2026-01-12T09:00:00Z", 1),
            ("pay-17", "2026-01-12T10:00:00Z", 0),
        ],
    }


def _reordered_tables() -> dict[str, list[tuple[Any, ...]]]:
    tables = _base_tables()
    tables["orders"] = [
        (2004, 14, 8000),
        (2002, 12, 3000),
        (2001, 11, 5000),
        (2003, 13, 2000),
    ]
    tables["payments"] = [
        (108, 2004, "a8", "refunded", 8000, "2026-01-12T10:05:00Z"),
        (102, 2002, "a2", "succeeded", 3000, "2026-01-12T10:01:00Z"),
        (105, 2003, "a5", "succeeded", 2000, "2026-01-12T10:02:05Z"),
        (101, 2001, "a1", "succeeded", 5000, "2026-01-12T09:58:00Z"),
        (107, 2004, "a7", "succeeded", 8000, "2026-01-12T10:03:02Z"),
        (103, 2002, "a3", "succeeded", 3000, "2026-01-12T10:01:03Z"),
        (106, 2004, "a6", "succeeded", 8000, "2026-01-12T10:03:00Z"),
        (104, 2003, "a4", "failed", 2000, "2026-01-12T10:02:00Z"),
    ]
    return tables


def _extra_duplicate_tables() -> dict[str, list[tuple[Any, ...]]]:
    tables = _base_tables()
    tables["orders"].append((1005, 15, 4000))
    tables["payments"].extend(
        [
            (9, 1005, "a9", "succeeded", 4000, "2026-01-12T10:04:00Z"),
            (10, 1005, "a10", "succeeded", 4000, "2026-01-12T10:04:05Z"),
        ]
    )
    tables["retry_events"].extend(
        [
            ("a9", "r6", None, "provider-success", "2026-01-12T10:04:00Z"),
            ("a10", "r6", None, "provider-success", "2026-01-12T10:04:05Z"),
        ]
    )
    return tables


def _failed_only_tables() -> dict[str, list[tuple[Any, ...]]]:
    tables = _base_tables()
    tables["orders"].append((1005, 15, 4000))
    tables["payments"].extend(
        [
            (9, 1005, "a9", "failed", 4000, "2026-01-12T10:04:00Z"),
            (10, 1005, "a10", "failed", 4000, "2026-01-12T10:04:05Z"),
        ]
    )
    tables["retry_events"].extend(
        [
            ("a9", "r6", None, "failed", "2026-01-12T10:04:00Z"),
            ("a10", "r6", None, "failed", "2026-01-12T10:04:05Z"),
        ]
    )
    return tables


def _ordinary_retry_tables() -> dict[str, list[tuple[Any, ...]]]:
    tables = _base_tables()
    tables["orders"].append((1005, 15, 4000))
    tables["payments"].extend(
        [
            (9, 1005, "a9", "failed", 4000, "2026-01-12T10:04:00Z"),
            (10, 1005, "a10", "succeeded", 4000, "2026-01-12T10:04:05Z"),
        ]
    )
    tables["retry_events"].extend(
        [
            ("a9", "r6", None, "failed", "2026-01-12T10:04:00Z"),
            ("a10", "r6", None, "provider-success", "2026-01-12T10:04:05Z"),
        ]
    )
    return tables


def _varied_amounts_tables() -> dict[str, list[tuple[Any, ...]]]:
    tables = _base_tables()
    tables["orders"] = [
        (1001, 11, 5000),
        (1002, 12, 2500),
        (1003, 13, 2000),
        (1004, 14, 9000),
    ]
    tables["payments"] = [
        (1, 1001, "a1", "succeeded", 5000, "2026-01-12T09:58:00Z"),
        (2, 1002, "a2", "succeeded", 2500, "2026-01-12T10:01:00Z"),
        (3, 1002, "a3", "succeeded", 2500, "2026-01-12T10:01:03Z"),
        (4, 1003, "a4", "failed", 2000, "2026-01-12T10:02:00Z"),
        (5, 1003, "a5", "succeeded", 2000, "2026-01-12T10:02:05Z"),
        (6, 1004, "a6", "succeeded", 9000, "2026-01-12T10:03:00Z"),
        (7, 1004, "a7", "succeeded", 9000, "2026-01-12T10:03:02Z"),
        (8, 1004, "a8", "refunded", 9000, "2026-01-12T10:05:00Z"),
    ]
    return tables


def _absent_config_tables() -> dict[str, list[tuple[Any, ...]]]:
    tables = _base_tables()
    tables["deployments"] = [
        ("pay-16", "2026-01-12T09:00:00Z", None),
        ("pay-17", "2026-01-12T10:00:00Z", None),
    ]
    return tables


def _prevention_repaired_tables() -> dict[str, list[tuple[Any, ...]]]:
    tables = _base_tables()
    tables["payments"] = [
        (payment_id, order_id, attempt_id, "blocked_duplicate" if payment_id in (3, 7) else status, amount, created)
        for payment_id, order_id, attempt_id, status, amount, created in tables["payments"]
    ]
    return tables


def _prevention_mutated_tables() -> dict[str, list[tuple[Any, ...]]]:
    tables = _prevention_repaired_tables()
    tables["payments"] = [
        (payment_id, order_id, attempt_id, "succeeded" if payment_id == 4 else status, amount, created)
        for payment_id, order_id, attempt_id, status, amount, created in tables["payments"]
    ]
    return tables


def _typical_tables() -> dict[str, dict[str, list[tuple[Any, ...]]]]:
    return {
        "base": _base_tables(),
        "reordered": _reordered_tables(),
        "extra-duplicate": _extra_duplicate_tables(),
        "failed-only": _failed_only_tables(),
        "ordinary-retry": _ordinary_retry_tables(),
        "varied-amounts": _varied_amounts_tables(),
        "absent-config": _absent_config_tables(),
        "repaired": _prevention_repaired_tables(),
        "mutated": _prevention_mutated_tables(),
    }


def fixture_labels() -> dict[str, str]:
    return {
        "base": "Base fictional incident data",
        "reordered": "Reordered insertion and order/payment IDs",
        "extra-duplicate": "Additional duplicate order",
        "failed-only": "Failed-only order",
        "ordinary-retry": "Ordinary failed-then-success retry",
        "varied-amounts": "Varied order and payment amounts",
        "absent-config": "Both deployment idempotency flags NULL",
        "repaired": "Repaired prevention fixture (second successes blocked)",
        "mutated": "Mutated prevention fixture with a different affected order",
    }


def _schema() -> str:
    return (
        "CREATE TABLE orders (\n"
        "  id INTEGER PRIMARY KEY,\n"
        "  customer_id INTEGER,\n"
        "  total_cents INTEGER\n"
        ");\n"
        "CREATE TABLE payments (\n"
        "  id INTEGER PRIMARY KEY,\n"
        "  order_id INTEGER,\n"
        "  attempt_id TEXT,\n"
        "  status TEXT,\n"
        "  amount_cents INTEGER,\n"
        "  created_at TEXT\n"
        ");\n"
        "CREATE TABLE retry_events (\n"
        "  attempt_id TEXT,\n"
        "  request_id TEXT,\n"
        "  idempotency_key TEXT,\n"
        "  outcome TEXT,\n"
        "  created_at TEXT\n"
        ");\n"
        "CREATE TABLE deployments (\n"
        "  version TEXT,\n"
        "  deployed_at TEXT,\n"
        "  idempotency_enabled INTEGER\n"
        ");\n"
    )


def build_fixture_bytes(tables: Mapping[str, Sequence[Sequence[Any]]]) -> bytes:
    """Build one deterministic in-memory SQLite database and serialize it."""
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("PRAGMA page_size=4096")
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.executescript(_schema())
        for name in ("orders", "payments", "retry_events", "deployments"):
            rows = tables[name]
            if not rows:
                continue
            placeholders = ",".join("?" for _ in rows[0])
            connection.executemany(
                f"INSERT INTO {name} VALUES ({placeholders})", rows
            )
        connection.commit()
        return connection.serialize()
    finally:
        connection.close()


def _affected_orders(tables: Mapping[str, Sequence[Sequence[Any]]]) -> list[tuple[int, int]]:
    counts: dict[int, int] = {}
    for payment in tables["payments"]:
        if payment[3] == "succeeded":
            counts[payment[1]] = counts.get(payment[1], 0) + 1
    return [(order_id, count) for order_id, count in sorted(counts.items()) if count > 1]


def _impact_rows(tables: Mapping[str, Sequence[Sequence[Any]]]) -> list[tuple[int, int, int]]:
    orders = {row[0]: row for row in tables["orders"]}
    paid: dict[int, int] = {}
    for payment in tables["payments"]:
        if payment[3] == "succeeded":
            paid[payment[1]] = paid.get(payment[1], 0) + payment[4]
    rows: list[tuple[int, int, int]] = []
    for order_id, count in _affected_orders(tables):
        if count > 1:
            order = orders[order_id]
            rows.append((order_id, order[1], paid[order_id] - order[2]))
    return sorted(rows)


def _first_duplicate_at(tables: Mapping[str, Sequence[Sequence[Any]]]) -> str | None:
    successes: dict[int, list[tuple[str, int]]] = {}
    for payment in tables["payments"]:
        if payment[3] == "succeeded":
            successes.setdefault(payment[1], []).append((payment[5], payment[0]))
    seconds: list[str] = []
    for order_id in successes:
        ranked = sorted(successes[order_id])
        if len(ranked) >= 2:
            seconds.append(ranked[1][0])
    return min(seconds) if seconds else None


def _duplicate_requests(tables: Mapping[str, Sequence[Sequence[Any]]]) -> list[tuple[str, int]]:
    retry_by_attempt = {row[0]: row for row in tables["retry_events"]}
    counts: dict[str, int] = {}
    for payment in tables["payments"]:
        if payment[3] != "succeeded":
            continue
        retry = retry_by_attempt.get(payment[2])
        if retry is None:
            continue
        counts[retry[1]] = counts.get(retry[1], 0) + 1
    return [(request_id, count) for request_id, count in sorted(counts.items()) if count > 1]


def _root_cause_cohort(tables: Mapping[str, Sequence[Sequence[Any]]]) -> list[tuple[str]]:
    retry_by_attempt = {row[0]: row for row in tables["retry_events"]}
    counts: dict[str, int] = {}
    null_keys: set[str] = set()
    for payment in tables["payments"]:
        if payment[3] != "succeeded":
            continue
        retry = retry_by_attempt.get(payment[2])
        if retry is None:
            continue
        counts[retry[1]] = counts.get(retry[1], 0) + 1
        if retry[2] is None:
            null_keys.add(retry[1])
    return [
        (request_id,)
        for request_id, count in sorted(counts.items())
        if count > 1 and request_id in null_keys
    ]


def _second_success_minutes(tables: Mapping[str, Sequence[Sequence[Any]]]) -> list[tuple[str, int]]:
    successes: dict[int, list[tuple[str, int]]] = {}
    for payment in tables["payments"]:
        if payment[3] == "succeeded":
            successes.setdefault(payment[1], []).append((payment[5], payment[0]))
    counts: dict[str, int] = {}
    for order_id in successes:
        ranked = sorted(successes[order_id])
        if len(ranked) >= 2:
            minute = ranked[1][0][:16]
            counts[minute] = counts.get(minute, 0) + 1
    return sorted(counts.items())


def _typed_int(value: int) -> dict[str, str]:
    return {"type": "integer", "value": str(value)}


def _typed_str(value: str) -> dict[str, str]:
    return {"type": "string", "value": value}


def _typed_null() -> dict[str, None]:
    return {"type": "null", "value": None}


def _rows_duplicate_counts(rows: Sequence[tuple[int, int]]) -> list[list[dict[str, str]]]:
    return [[_typed_int(order_id), _typed_int(count)] for order_id, count in rows]


def _rows_impact(rows: Sequence[tuple[int, int, int]]) -> list[list[dict[str, str]]]:
    return [
        [_typed_int(order_id), _typed_int(customer_id), _typed_int(excess)]
        for order_id, customer_id, excess in rows
    ]


def _rows_single_text(value: str) -> list[list[dict[str, str]]]:
    return [[_typed_str(value)]]


def _rows_requests(rows: Sequence[tuple[str, int]]) -> list[list[dict[str, Any]]]:
    return [[_typed_str(request_id), _typed_int(count)] for request_id, count in rows]


def _rows_request_ids(rows: Sequence[tuple[str]]) -> list[list[dict[str, str]]]:
    return [[_typed_str(request_id)] for (request_id,) in rows]


def _rows_order_ids(rows: Sequence[tuple[int, int]] | Sequence[int]) -> list[list[dict[str, str]]]:
    result: list[list[dict[str, str]]] = []
    for row in rows:
        order_id = row[0] if isinstance(row, tuple) else row
        result.append([_typed_int(order_id)])
    return result


# ---------------------------------------------------------------------------
# Evidence assets
# ---------------------------------------------------------------------------


def _payment_ledger(tables: Mapping[str, Sequence[Sequence[Any]]]) -> bytes:
    document = {
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "order_id", "type": "integer"},
            {"name": "attempt_id", "type": "string"},
            {"name": "status", "type": "string"},
            {"name": "amount_cents", "type": "integer"},
            {"name": "created_at", "type": "datetime"},
        ],
        "rows": [
            [
                _typed_int(payment[0]),
                _typed_int(payment[1]),
                _typed_str(payment[2]),
                _typed_str(payment[3]),
                _typed_int(payment[4]),
                {"type": "datetime", "value": payment[5]},
            ]
            for payment in tables["payments"]
        ],
    }
    return json_bytes(document)


def _orders_ledger(tables: Mapping[str, Sequence[Sequence[Any]]]) -> bytes:
    document = {
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "customer_id", "type": "integer"},
            {"name": "total_cents", "type": "integer"},
        ],
        "rows": [
            [_typed_int(order[0]), _typed_int(order[1]), _typed_int(order[2])]
            for order in tables["orders"]
        ],
    }
    return json_bytes(document)


def _retry_ledger(tables: Mapping[str, Sequence[Sequence[Any]]]) -> bytes:
    document = {
        "columns": [
            {"name": "attempt_id", "type": "string"},
            {"name": "request_id", "type": "string"},
            {"name": "idempotency_key", "type": "string"},
            {"name": "outcome", "type": "string"},
            {"name": "created_at", "type": "datetime"},
        ],
        "rows": [
            [
                _typed_str(retry[0]),
                _typed_str(retry[1]),
                _typed_null() if retry[2] is None else _typed_str(retry[2]),
                _typed_str(retry[3]),
                {"type": "datetime", "value": retry[4]},
            ]
            for retry in tables["retry_events"]
        ],
    }
    return json_bytes(document)


def _deployment_ledger(tables: Mapping[str, Sequence[Sequence[Any]]]) -> bytes:
    document = {
        "columns": [
            {"name": "version", "type": "string"},
            {"name": "deployed_at", "type": "datetime"},
            {"name": "idempotency_enabled", "type": "integer"},
        ],
        "rows": [
            [
                _typed_str(row[0]),
                {"type": "datetime", "value": row[1]},
                _typed_null() if row[2] is None else _typed_int(row[2]),
            ]
            for row in tables["deployments"]
        ],
    }
    return json_bytes(document)


def _duplicate_orders(tables: Mapping[str, Sequence[Sequence[Any]]]) -> bytes:
    document = {
        "columns": [
            {"name": "order_id", "type": "integer"},
            {"name": "successful_count", "type": "integer"},
        ],
        "rows": _rows_duplicate_counts(_affected_orders(tables)),
    }
    return json_bytes(document)


def _duplicate_requests_evidence(tables: Mapping[str, Sequence[Sequence[Any]]]) -> bytes:
    document = {
        "columns": [
            {"name": "request_id", "type": "string"},
            {"name": "successes", "type": "integer"},
        ],
        "rows": _rows_requests(_duplicate_requests(tables)),
    }
    return json_bytes(document)


def _duplicate_minutes_evidence(tables: Mapping[str, Sequence[Sequence[Any]]]) -> bytes:
    document = {
        "columns": [
            {"name": "minute", "type": "string"},
            {"name": "duplicated_second_successes", "type": "integer"},
        ],
        "rows": [
            [_typed_str(minute), _typed_int(count)]
            for minute, count in _second_success_minutes(tables)
        ],
    }
    return json_bytes(document)


def _support_reports() -> bytes:
    return (
        "Synthetic support reports for training.\n"
        "Three customers contacted support about repeated charges.\n"
        "The reports may overlap; no order or payment identifiers are asserted here.\n"
    ).encode("utf-8")


def _prevention_fixtures() -> bytes:
    return (
        "Synthetic prevention fixtures for the training Check.\n"
        "Broken fixture: the frozen investigation data has two affected orders.\n"
        "Repaired fixture: the second successes for those orders are changed to blocked_duplicate.\n"
        "Mutated fixture: a different order is duplicated, so a hardcoded order id cannot pass.\n"
        "Expected Check: zero affected-order rows. Broken and mutated must fail; repaired must pass.\n"
        "No production data or production Watch is involved.\n"
    ).encode("utf-8")


def _config_diff() -> bytes:
    return (
        "Fictional reviewed configuration diff for release pay-17 (synthetic training fixture).\n"
        "\n"
        "retry_requests:\n"
        "-   idempotency_enabled: true\n"
        "+   idempotency_enabled: false\n"
        "\n"
        "The released pay-17 retry handler no longer sends the Idempotency-Key header on retry requests.\n"
        "Retries reuse a request identifier without an idempotency key, so the provider may accept both attempts.\n"
        "This diff is the direct fictional causal evidence for the training scenario.\n"
    ).encode("utf-8")


def _trace_r1() -> bytes:
    return (
        '{"id":"trace-r1-1","at":"2026-01-12T09:58:00Z","actorId":"daniel","kind":"provider-success","message":"Request r1 used idempotency key k1 and produced one successful charge."}\n'
    ).encode("utf-8")


def _trace_r2() -> bytes:
    return (
        '{"id":"trace-r2-1","at":"2026-01-12T10:00:59Z","actorId":"daniel","kind":"provider-success","message":"Provider accepted attempt a2 for request r2."}\n'
        '{"id":"trace-r2-2","at":"2026-01-12T10:01:00Z","actorId":"daniel","kind":"handler-timeout","message":"Handler timed out after provider success; the retry was scheduled."}\n'
        '{"id":"trace-r2-3","at":"2026-01-12T10:01:02Z","actorId":"daniel","kind":"provider-success","message":"Retry a3 reused request r2 without an idempotency key."}\n'
        '{"id":"trace-r2-4","at":"2026-01-12T10:01:03Z","actorId":"daniel","kind":"duplicate-charge","message":"Second successful charge recorded for order 1002."}\n'
    ).encode("utf-8")


def _trace_r3() -> bytes:
    return (
        '{"id":"trace-r3-1","at":"2026-01-12T10:02:00Z","actorId":"daniel","kind":"provider-failure","message":"Provider rejected attempt a4 for request r3."}\n'
        '{"id":"trace-r3-2","at":"2026-01-12T10:02:05Z","actorId":"daniel","kind":"provider-success","message":"Retry a5 succeeded once; request r3 produced one successful charge."}\n'
    ).encode("utf-8")


def _trace_r4() -> bytes:
    return (
        '{"id":"trace-r4-1","at":"2026-01-12T10:02:59Z","actorId":"daniel","kind":"provider-success","message":"Provider accepted attempt a6 for request r4."}\n'
        '{"id":"trace-r4-2","at":"2026-01-12T10:03:00Z","actorId":"daniel","kind":"handler-timeout","message":"Handler timed out after provider success; the retry was scheduled."}\n'
        '{"id":"trace-r4-3","at":"2026-01-12T10:03:01Z","actorId":"daniel","kind":"provider-success","message":"Retry a7 reused request r4 without an idempotency key."}\n'
        '{"id":"trace-r4-4","at":"2026-01-12T10:03:02Z","actorId":"daniel","kind":"duplicate-charge","message":"Second successful charge recorded for order 1004."}\n'
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Byte and pin helpers
# ---------------------------------------------------------------------------


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def asset_record(asset_id: str, kind: str, media_type: str, path: str, data: bytes) -> dict[str, Any]:
    return {
        "id": asset_id,
        "kind": kind,
        "mediaType": media_type,
        "path": path,
        "sha256": sha256_hex(data),
        "bytes": len(data),
    }


def reference(path: str, data: bytes) -> dict[str, Any]:
    return {
        "path": path,
        "sha256": sha256_hex(data),
        "bytes": len(data),
    }


def package_reference(package_id: str, revision: int, path: str, data: bytes) -> dict[str, Any]:
    return {
        "id": package_id,
        "revision": revision,
        "path": path,
        "sha256": sha256_hex(data),
        "bytes": len(data),
    }


# ---------------------------------------------------------------------------
# Challenge manifests
# ---------------------------------------------------------------------------


def _fixture_pin(fixture_id: str, label: str, data: bytes) -> dict[str, Any]:
    return {
        "id": fixture_id,
        "label": label,
        "sha256": sha256_hex(data),
        "bytes": len(data),
        "runs": 1,
    }


def _sql_part(part_id: str, title: str, cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": part_id,
        "title": title,
        "required": True,
        "answerKind": "sql",
        "sql": {"cases": list(cases)},
    }


def _sql_case(fixture_id: str, columns: Sequence[tuple[str, str]], rows: Sequence[Sequence[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "fixture": fixture_id,
        "oracle": {
            "kind": "result",
            "columns": [{"name": name, "type": type_name} for name, type_name in columns],
            "rows": [list(row) for row in rows],
            "ordering": "unordered",
        },
    }


def _structured_part(part_id: str, title: str, field: dict[str, Any], selections: Sequence[str]) -> dict[str, Any]:
    return {
        "id": part_id,
        "title": title,
        "required": True,
        "answerKind": "structured",
        "structured": {
            "fields": [field],
            "expected": {"selections": {field["id"]: list(selections)}},
        },
    }


def _single_field(field_id: str, label: str, options: Sequence[tuple[str, str]]) -> dict[str, Any]:
    return {
        "id": field_id,
        "label": label,
        "cardinality": "single",
        "required": True,
        "options": [{"id": option_id, "label": option_label} for option_id, option_label in options],
    }


def _multi_field(
    field_id: str,
    label: str,
    options: Sequence[tuple[str, str]],
    min_selections: int,
    max_selections: int,
) -> dict[str, Any]:
    return {
        "id": field_id,
        "label": label,
        "cardinality": "multi",
        "required": True,
        "minSelections": min_selections,
        "maxSelections": max_selections,
        "options": [{"id": option_id, "label": option_label} for option_id, option_label in options],
    }


def _manifest(
    challenge_id: str,
    title: str,
    objective: str,
    fixtures: Sequence[tuple[str, bytes]],
    parts: Sequence[dict[str, Any]],
    hints: Sequence[tuple[str, str]],
    reference_solutions: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    labels = fixture_labels()
    return {
        "schemaVersion": 1,
        "gradingVersion": "challenge-grading-v1",
        "challengeId": challenge_id,
        "revision": REVISION,
        "title": title,
        "objective": objective,
        "difficulty": "intermediate",
        "dialect": "sqlite",
        "allowedOperation": "read",
        "timing": "off",
        "engine": dict(ENGINE),
        "fixtureSuite": {
            "id": f"phantom-orders-{challenge_id}",
            "fixtures": [
                _fixture_pin(fixture_id, labels[fixture_id], data)
                for fixture_id, data in fixtures
            ],
        },
        "visibleSchema": VISIBLE_SCHEMA,
        "parts": list(parts),
        "hints": [{"id": hint_id, "text": text} for hint_id, text in hints],
        "referenceSolutions": list(reference_solutions),
    }


def _reference_sql(part_id: str, sql: str) -> dict[str, Any]:
    return {"partId": part_id, "answer": {"sql": sql}}


def _reference_structured(part_id: str, field_id: str, selections: Sequence[str]) -> dict[str, Any]:
    return {
        "partId": part_id,
        "answer": {"structured": {"selections": {field_id: list(selections)}}},
    }


def _root_cause_parts(variant: bool) -> list[dict[str, Any]]:
    cause_options = [
        ("missing-retry-idempotency", "Missing retry idempotency safeguard"),
        ("provider-double-send", "Provider double-send"),
        ("insufficient-evidence", "Insufficient evidence"),
    ]
    deployment_options = [
        ("pay-16", "Release pay-16"),
        ("pay-17", "Release pay-17"),
        ("unknown", "Unknown"),
    ]
    citation_options = [
        ("trace-r2", "Trace r2 (a2/a3 duplicate request)"),
        ("trace-r4", "Trace r4 (a6/a7 duplicate request)"),
        ("trace-r3", "Trace r3 (harmless recovered retry)"),
        ("trace-r1", "Trace r1 (single successful charge)"),
    ]
    if not variant:
        citation_options = [
            ("config-pay-17", "Reviewed configuration diff for pay-17"),
            *citation_options,
        ]
        cause_expected = ["missing-retry-idempotency"]
        deployment_expected = ["pay-17"]
        citations_expected = ["config-pay-17", "trace-r2", "trace-r4"]
    else:
        cause_expected = ["insufficient-evidence"]
        deployment_expected = ["unknown"]
        citations_expected = ["trace-r2", "trace-r4"]
    return [
        _structured_part(
            "cause",
            "Supported cause",
            _single_field("cause", "Cause", cause_options),
            cause_expected,
        ),
        _structured_part(
            "deployment",
            "Implicated deployment",
            _single_field("deployment", "Deployment", deployment_options),
            deployment_expected,
        ),
        _structured_part(
            "citations",
            "Evidence citations",
            _multi_field("citations", "Citations", citation_options, 2, 4),
            citations_expected,
        ),
    ]


def build_manifests() -> dict[str, dict[str, Any]]:
    tables = _typical_tables()
    fixtures = {name: build_fixture_bytes(rows) for name, rows in tables.items()}
    typical_names = ["base", "reordered", "extra-duplicate", "failed-only", "ordinary-retry", "varied-amounts"]
    retry_names = ["base", "reordered", "failed-only", "ordinary-retry", "varied-amounts"]
    root_names = ["base", "reordered", "failed-only", "ordinary-retry", "varied-amounts"]
    prevention_names = ["base", "repaired", "mutated"]

    duplicate_cases = [
        _sql_case(
            name,
            [("order_id", "integer"), ("successful_count", "integer")],
            _rows_duplicate_counts(_affected_orders(tables[name])),
        )
        for name in typical_names
    ]
    impact_cases = [
        _sql_case(
            name,
            [("order_id", "integer"), ("customer_id", "integer"), ("excess_cents", "integer")],
            _rows_impact(_impact_rows(tables[name])),
        )
        for name in typical_names
    ]
    failure_cases = [
        _sql_case(
            name,
            [("first_duplicate_at", "string")],
            _rows_single_text(_first_duplicate_at(tables[name]) or ""),
        )
        for name in typical_names
    ]
    retry_cases = [
        _sql_case(
            name,
            [("request_id", "string"), ("successes", "integer")],
            _rows_requests(_duplicate_requests(tables[name])),
        )
        for name in retry_names
    ]
    root_cases = [
        _sql_case(
            name,
            [("request_id", "string")],
            _rows_request_ids(_root_cause_cohort(tables[name])),
        )
        for name in root_names
    ]
    prevention_cases = [
        _sql_case(
            name,
            [("order_id", "integer")],
            _rows_order_ids(_affected_orders(tables[name])),
        )
        for name in prevention_names
    ]

    failure_interpretation = _structured_part(
        "interpretation",
        "Interpretation of the timestamp",
        _single_field(
            "interpretation",
            "What does the timestamp establish?",
            [
                ("first-observed-duplicate", "First observed duplicate"),
                ("proven-defect-introduction", "Proven defect introduction time"),
            ],
        ),
        ["first-observed-duplicate"],
    )

    retry_evidence = _structured_part(
        "requests-evidence",
        "Duplicate request evidence pairs",
        _multi_field(
            "requests-evidence",
            "Select the exact duplicate request evidence pairs",
            [
                ("trace-r2", "(r2, a2, a3, trace-r2)"),
                ("trace-r4", "(r4, a6, a7, trace-r4)"),
                ("trace-r3", "(r3, a4, a5, trace-r3)"),
                ("trace-r1", "(r1, a1, none, trace-r1)"),
            ],
            1,
            4,
        ),
        ["trace-r2", "trace-r4"],
    )

    postmortem = _structured_part(
        "postmortem-citations",
        "Reviewed postmortem citations",
        _multi_field(
            "postmortem-citations",
            "Cite the evidence required by the postmortem",
            [
                ("config-pay-17", "Reviewed configuration diff for pay-17"),
                ("trace-r2", "Trace r2 (a2/a3 duplicate request)"),
                ("trace-r4", "Trace r4 (a6/a7 duplicate request)"),
                ("trace-r3", "Trace r3 (harmless recovered retry)"),
            ],
            1,
            4,
        ),
        ["config-pay-17", "trace-r2", "trace-r4"],
    )

    check_expectation = {
        "id": "zero-affected-orders",
        "scope": "set",
        "kind": "row-count",
        "severity": "error",
        "expected": {"type": "integer", "value": "0"},
    }
    prevention_check = {
        "id": "check",
        "title": "Zero affected orders",
        "required": True,
        "answerKind": "check-definition",
        "checkDefinition": {
            "queryIds": ["prevention/affected-orders"],
            "expectation": check_expectation,
            "cases": [
                {"fixture": "base", "expectedOutcome": "fail"},
                {"fixture": "repaired", "expectedOutcome": "pass"},
                {"fixture": "mutated", "expectedOutcome": "fail"},
            ],
        },
    }

    manifests: dict[str, dict[str, Any]] = {}
    manifests["duplicate-payments"] = _manifest(
        "duplicate-payments",
        "Find duplicate successful payments",
        "Count only succeeded payments per order and keep orders with more than one success.",
        [(name, fixtures[name]) for name in typical_names],
        [
            _sql_part("duplicate-payments", "Duplicate successful payment counts", duplicate_cases),
        ],
        HINTS["duplicate-payments"],
        [_reference_sql("duplicate-payments", REFERENCE_SQL["duplicate-payments"])],
    )
    manifests["payment-impact"] = _manifest(
        "payment-impact",
        "Connect payments and orders",
        "Join successful payment totals to orders and report affected customers and excess charges.",
        [(name, fixtures[name]) for name in typical_names],
        [
            _sql_part("payment-impact", "Customer impact rows", impact_cases),
        ],
        HINTS["payment-impact"],
        [_reference_sql("payment-impact", REFERENCE_SQL["payment-impact"])],
    )
    manifests["failure-window"] = _manifest(
        "failure-window",
        "Find when the bug began",
        "Find the first observed second successful charge and keep the interpretation honest.",
        [(name, fixtures[name]) for name in typical_names],
        [
            _sql_part("failure-window", "First observed duplicate time", failure_cases),
            failure_interpretation,
        ],
        HINTS["failure-window"],
        [
            _reference_sql("failure-window", REFERENCE_SQL["failure-window"]),
            _reference_structured("interpretation", "interpretation", ["first-observed-duplicate"]),
        ],
    )
    manifests["retry-evidence"] = _manifest(
        "retry-evidence",
        "Investigate retries and logs",
        "Correlate successful payments with request IDs and select the exact duplicate evidence pairs.",
        [(name, fixtures[name]) for name in retry_names],
        [
            _sql_part("requests", "Duplicate request counts", retry_cases),
            retry_evidence,
        ],
        HINTS["retry-evidence"],
        [
            _reference_sql("requests", REFERENCE_SQL["retry-evidence"]),
            _reference_structured(
                "requests-evidence",
                "requests-evidence",
                ["trace-r2", "trace-r4"],
            ),
        ],
    )
    manifests["root-cause"] = _manifest(
        "root-cause",
        "Prove the root cause",
        "Find the duplicate request cohort and distinguish the supported cause from correlation.",
        [(name, fixtures[name]) for name in root_names],
        [
            _sql_part("cohort", "Duplicate request cohort", root_cases),
            *_root_cause_parts(variant=False),
        ],
        HINTS["root-cause"],
        [
            _reference_sql("cohort", REFERENCE_SQL["root-cause"]),
            _reference_structured("cause", "cause", ["missing-retry-idempotency"]),
            _reference_structured("deployment", "deployment", ["pay-17"]),
            _reference_structured(
                "citations",
                "citations",
                ["config-pay-17", "trace-r2", "trace-r4"],
            ),
        ],
    )
    manifests["prevention"] = _manifest(
        "prevention",
        "Prevent recurrence",
        "Write the affected-order query and prove a zero-row Check on broken, repaired and mutated fixtures.",
        [(name, fixtures[name]) for name in prevention_names],
        [
            _sql_part("affected-orders", "Affected order IDs", prevention_cases),
            postmortem,
            prevention_check,
        ],
        HINTS["prevention"],
        [
            _reference_sql("affected-orders", REFERENCE_SQL["prevention"]),
            _reference_structured(
                "postmortem-citations",
                "postmortem-citations",
                ["config-pay-17", "trace-r2", "trace-r4"],
            ),
            {
                "partId": "check",
                "answer": {
                    "checkDefinition": {
                        "queryId": "prevention/affected-orders",
                        "expectation": check_expectation,
                    }
                },
            },
        ],
    )
    return manifests


def build_variant_manifest(absent_fixture: bytes) -> dict[str, Any]:
    tables = _absent_config_tables()
    cases = [
        _sql_case(
            "absent-config",
            [("request_id", "string")],
            _rows_request_ids(_root_cause_cohort(tables)),
        )
    ]
    manifest = _manifest(
        "root-cause-absent-config",
        "Prove the root cause with no configuration evidence",
        "Refuse causal certainty when the reviewed configuration diff is absent.",
        [("absent-config", absent_fixture)],
        [_sql_part("cohort", "Duplicate request cohort", cases), *_root_cause_parts(variant=True)],
        HINTS["root-cause-absent-config"],
        [
            _reference_sql("cohort", REFERENCE_SQL["root-cause"]),
            _reference_structured("cause", "cause", ["insufficient-evidence"]),
            _reference_structured("deployment", "deployment", ["unknown"]),
            _reference_structured("citations", "citations", ["trace-r2", "trace-r4"]),
        ],
    )
    return manifest


# ---------------------------------------------------------------------------
# Package index
# ---------------------------------------------------------------------------


def _case(
    case_id: str,
    title: str,
    incident_id: str,
    evidence_ids: Sequence[str],
    findings: Sequence[dict[str, Any]],
    timeline: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": case_id,
        "title": title,
        "status": "active",
        "context": {
            "scenario": {"type": "string", "value": "INC-0042"},
            "synthetic": {"type": "string", "value": "true"},
        },
        "incidentIds": [incident_id],
        "evidenceIds": list(evidence_ids),
        "findings": list(findings),
        "timeline": list(timeline),
    }


def _finding(finding_id: str, text: str, status: str, evidence_refs: Sequence[str] | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {"id": finding_id, "text": text, "status": status}
    if evidence_refs is not None:
        record["evidenceRefs"] = list(evidence_refs)
    return record


def _timeline(
    entry_id: str,
    at: str,
    actor_id: str,
    entry_type: str,
    ref_kind: str,
    ref_id: str,
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "at": at,
        "actorId": actor_id,
        "type": entry_type,
        "ref": {"kind": ref_kind, "id": ref_id},
    }


def _cases() -> list[dict[str, Any]]:
    return [
        _case(
            "duplicate-payments",
            "Duplicate successful payments",
            "incident-0042",
            ["support-reports", "payment-ledger", "orders-ledger"],
            [
                _finding(
                    "reports-overlap",
                    "Three customers reported repeated charges; the reports may overlap.",
                    "hypothesis",
                    ["support-reports"],
                )
            ],
            [
                _timeline("case1-evidence", "2026-01-12T11:00:00Z", "sarah", "evidence-revealed", "evidence", "support-reports"),
                _timeline("case1-finding", "2026-01-12T11:01:00Z", "maya", "finding-recorded", "finding", "reports-overlap"),
            ],
        ),
        _case(
            "payment-impact",
            "Payment impact",
            "incident-0042",
            ["duplicate-orders", "payment-ledger", "orders-ledger"],
            [
                _finding(
                    "duplicate-orders-known",
                    "Orders 1002 and 1004 each have two successful charges in the frozen investigation data.",
                    "confirmed",
                    ["duplicate-orders"],
                )
            ],
            [
                _timeline("case2-evidence", "2026-01-12T11:05:00Z", "maya", "evidence-revealed", "evidence", "duplicate-orders"),
                _timeline("case2-finding", "2026-01-12T11:06:00Z", "sarah", "finding-recorded", "finding", "duplicate-orders-known"),
            ],
        ),
        _case(
            "failure-window",
            "Failure window",
            "incident-0042",
            ["duplicate-orders", "payment-ledger"],
            [
                _finding(
                    "first-charge-valid",
                    "A first successful charge is not yet evidence of duplication; use the second success per order.",
                    "hypothesis",
                    ["payment-ledger"],
                )
            ],
            [
                _timeline("case3-evidence", "2026-01-12T11:10:00Z", "maya", "evidence-revealed", "evidence", "payment-ledger"),
                _timeline("case3-finding", "2026-01-12T11:11:00Z", "daniel", "finding-recorded", "finding", "first-charge-valid"),
            ],
        ),
        _case(
            "retry-evidence",
            "Retry evidence",
            "incident-0042",
            ["retry-events", "trace-r1", "trace-r2", "trace-r3", "trace-r4", "payment-ledger"],
            [
                _finding(
                    "correlate-by-request",
                    "Provider traces include retries that must be correlated by request ID, not by amount.",
                    "hypothesis",
                    ["retry-events", "trace-r2", "trace-r4"],
                )
            ],
            [
                _timeline("case4-evidence", "2026-01-12T11:15:00Z", "daniel", "evidence-revealed", "evidence", "retry-events"),
                _timeline("case4-finding", "2026-01-12T11:16:00Z", "maya", "finding-recorded", "finding", "correlate-by-request"),
            ],
        ),
        _case(
            "root-cause",
            "Root cause",
            "incident-0042",
            ["duplicate-cohort", "duplicate-minutes", "retry-events", "trace-r2", "trace-r4", "trace-r3", "config-pay-17", "deployment-timeline"],
            [
                _finding(
                    "duplicate-request-cohort",
                    "The duplicate request cohort is r2 and r4; r3 recovered a failure safely.",
                    "confirmed",
                    ["duplicate-cohort", "retry-events"],
                ),
                _finding(
                    "second-success-minutes",
                    "Second successes cluster at 10:01 and 10:03 in the frozen data.",
                    "confirmed",
                    ["duplicate-minutes"],
                ),
                _finding(
                    "reviewed-config-diff",
                    "Release pay-17 disabled retry idempotency in the reviewed configuration diff.",
                    "confirmed",
                    ["config-pay-17", "deployment-timeline"],
                ),
            ],
            [
                _timeline("case5-evidence", "2026-01-12T11:20:00Z", "daniel", "evidence-revealed", "evidence", "config-pay-17"),
                _timeline("case5-finding", "2026-01-12T11:21:00Z", "maya", "finding-recorded", "finding", "duplicate-request-cohort"),
                _timeline("case5-minutes", "2026-01-12T11:22:00Z", "daniel", "finding-recorded", "finding", "second-success-minutes"),
            ],
        ),
        _case(
            "prevention",
            "Prevention",
            "incident-0042",
            ["config-pay-17", "trace-r2", "trace-r4", "duplicate-orders", "prevention-fixtures"],
            [
                _finding(
                    "check-expectation",
                    "The Check must return zero affected-order rows on repaired data.",
                    "hypothesis",
                    ["prevention-fixtures"],
                ),
                _finding(
                    "synthetic-validation",
                    "Expected synthetic validation matrix: broken fails, repaired passes, mutated fails.",
                    "hypothesis",
                    ["prevention-fixtures"],
                ),
            ],
            [
                _timeline("case6-evidence", "2026-01-12T11:25:00Z", "maya", "evidence-revealed", "evidence", "prevention-fixtures"),
                _timeline("case6-finding", "2026-01-12T11:26:00Z", "daniel", "finding-recorded", "finding", "synthetic-validation"),
            ],
        ),
    ]


def _incident(incident_id: str = "incident-0042", evidence_ids: Sequence[str] | None = None) -> dict[str, Any]:
    return {
        "id": incident_id,
        "title": "Duplicate charges after retry handler deployment",
        "description": (
            "Synthetic incident for The Phantom Orders training. Successful retries produced duplicate charges; "
            "the scenario and all evidence are fictional."
        ),
        "status": "investigating",
        "evidenceIds": list(evidence_ids or ["config-pay-17", "trace-r2", "trace-r4", "payment-ledger", "duplicate-cohort"]),
    }


def _watch_recommendation() -> dict[str, Any]:
    return {
        "title": "Alert when duplicate successful charges appear",
        "checkId": "prevention-check",
        "checkVersion": "1",
        "inputs": {},
        "schedule": {"intervalSeconds": 300},
        "trigger": "becomes_true",
        "initialObservation": "baseline",
        "mode": "one_shot",
        "notificationPolicy": {"cooldownSeconds": 0, "recovery": False},
    }


def _check_definition() -> dict[str, Any]:
    return {
        "id": "prevention-check",
        "title": "Prevention: no duplicate successful charges",
        "description": "Synthetic training Check. It returns affected orders and expects zero rows.",
        "version": 1,
        "inputs": [],
        "steps": [
            {
                "id": "affected-orders",
                "kind": "query",
                "queryId": "prevention/affected-orders",
                "validators": [
                    {
                        "id": "zero-affected-orders",
                        "scope": "set",
                        "kind": "row-count",
                        "severity": "error",
                        "expected": {"type": "integer", "value": "0"},
                    }
                ],
                "onUnavailable": "block",
            }
        ],
        "updatedAt": "2026-01-12T12:00:00Z",
        "updatedBy": "maya",
        "createdAt": "2026-01-12T11:00:00Z",
    }


def _query_metadata() -> dict[str, Any]:
    return {
        "id": "prevention/affected-orders",
        "title": "Affected orders with duplicate successful charges",
        "type": "SQL",
        "connectionId": "phantom-fixture",
        "parameters": [],
    }


def _presentation_targets() -> list[dict[str, str]]:
    targets = [
        ("case-duplicate-payments", "case", "duplicate-payments"),
        ("case-payment-impact", "case", "payment-impact"),
        ("case-failure-window", "case", "failure-window"),
        ("case-retry-evidence", "case", "retry-evidence"),
        ("case-root-cause", "case", "root-cause"),
        ("case-prevention", "case", "prevention"),
        ("incident-0042", "incident", "incident-0042"),
        ("evidence-config-pay-17", "evidence", "config-pay-17"),
        ("evidence-trace-r2", "evidence", "trace-r2"),
        ("evidence-trace-r4", "evidence", "trace-r4"),
        ("evidence-trace-r3", "evidence", "trace-r3"),
        ("check-prevention", "check", "prevention-check"),
        ("proposal-watch", "proposal", "watch-proposal"),
    ]
    return [{"id": target_id, "kind": kind, "refId": ref_id} for target_id, kind, ref_id in targets]


def build_primary_package() -> tuple[dict[str, Any], dict[str, bytes]]:
    tables = _typical_tables()
    # The absent-configuration data is a separate focused variant package; the
    # six-case primary package must not carry an unused duplicate of it.
    fixtures = {
        name: build_fixture_bytes(rows)
        for name, rows in tables.items()
        if name != "absent-config"
    }
    manifests = build_manifests()

    datas: dict[str, bytes] = {}
    assets: list[dict[str, Any]] = []

    def add(asset_id: str, kind: str, media_type: str, path: str, data: bytes) -> None:
        datas[asset_id] = data
        assets.append(asset_record(asset_id, kind, media_type, path, data))

    for name, data in fixtures.items():
        add(f"fixture-{name}", "challenge-fixture", "application/vnd.sqlite3", f"{TRAINING_REL}/fixtures/{name}.db", data)

    for challenge_id, manifest in manifests.items():
        add(
            f"manifest-{challenge_id}",
            "challenge-manifest",
            "application/json",
            f"{TRAINING_REL}/challenges/{challenge_id}.json",
            json_bytes(manifest),
        )

    add("payment-ledger", "evidence-records", "application/json", f"{TRAINING_REL}/evidence/payment-ledger.json", _payment_ledger(tables["base"]))
    add("orders-ledger", "evidence-records", "application/json", f"{TRAINING_REL}/evidence/orders-ledger.json", _orders_ledger(tables["base"]))
    add("retry-events", "evidence-records", "application/json", f"{TRAINING_REL}/evidence/retry-events.json", _retry_ledger(tables["base"]))
    add("deployment-timeline", "evidence-records", "application/json", f"{TRAINING_REL}/evidence/deployment-timeline.json", _deployment_ledger(tables["base"]))
    add("duplicate-orders", "evidence-records", "application/json", f"{TRAINING_REL}/evidence/duplicate-orders.json", _duplicate_orders(tables["base"]))
    add("duplicate-cohort", "evidence-records", "application/json", f"{TRAINING_REL}/evidence/duplicate-cohort.json", _duplicate_requests_evidence(tables["base"]))
    add("duplicate-minutes", "evidence-records", "application/json", f"{TRAINING_REL}/evidence/duplicate-minutes.json", _duplicate_minutes_evidence(tables["base"]))
    add("support-reports", "evidence-text", "text/plain", f"{TRAINING_REL}/evidence/support-reports.txt", _support_reports())
    add("prevention-fixtures", "evidence-text", "text/plain", f"{TRAINING_REL}/evidence/prevention-fixtures.txt", _prevention_fixtures())
    add("config-pay-17", "evidence-text", "text/plain", f"{TRAINING_REL}/evidence/config-pay-17.txt", _config_diff())
    add("trace-r1", "evidence-log", "application/x-ndjson", f"{TRAINING_REL}/evidence/traces/trace-r1.jsonl", _trace_r1())
    add("trace-r2", "evidence-log", "application/x-ndjson", f"{TRAINING_REL}/evidence/traces/trace-r2.jsonl", _trace_r2())
    add("trace-r3", "evidence-log", "application/x-ndjson", f"{TRAINING_REL}/evidence/traces/trace-r3.jsonl", _trace_r3())
    add("trace-r4", "evidence-log", "application/x-ndjson", f"{TRAINING_REL}/evidence/traces/trace-r4.jsonl", _trace_r4())

    add("query-prevention-meta", "query-metadata", "application/json", f"{TRAINING_REL}/queries/prevention-affected-orders.meta.json", json_bytes(_query_metadata()))
    add("query-prevention-body", "query-body-sql", "application/sql", f"{TRAINING_REL}/queries/prevention-affected-orders.sql", REFERENCE_SQL["prevention"].encode("utf-8"))
    add("check-prevention-definition", "check-definition", "application/json", f"{TRAINING_REL}/checks/prevention-duplicate-charges.json", json_bytes(_check_definition()))
    add("watch-recommendation", "watch-recommendation", "application/json", f"{TRAINING_REL}/proposals/watch-recommendation.json", json_bytes(_watch_recommendation()))

    challenge_records = []
    for challenge_id, manifest in manifests.items():
        challenge_records.append(
            {
                "id": challenge_id,
                "revision": REVISION,
                "manifestAssetId": f"manifest-{challenge_id}",
                "fixtures": [
                    {"fixtureId": fixture["id"], "assetId": f"fixture-{fixture['id']}"}
                    for fixture in manifest["fixtureSuite"]["fixtures"]
                ],
            }
        )

    package = {
        "schema": SCHEMA_PACKAGE,
        "id": SCENARIO,
        "revision": REVISION,
        "assets": assets,
        "fictionalActors": [{"id": actor_id, "name": name} for actor_id, name in ACTORS],
        "sources": [{"id": "phantom-fixture", "fixtureAssetId": "fixture-base"}],
        "cases": _cases(),
        "incidents": [_incident()],
        "checks": [{"id": "prevention-check", "definitionAssetId": "check-prevention-definition"}],
        "queries": [
            {
                "id": "prevention/affected-orders",
                "metadataAssetId": "query-prevention-meta",
                "bodyAssetId": "query-prevention-body",
                "sourceId": "phantom-fixture",
            }
        ],
        "challenges": challenge_records,
        "proposals": [
            {
                "id": "watch-proposal",
                "kind": "watch",
                "definitionId": "watch-recommendation",
                "evidenceIds": ["config-pay-17", "trace-r2", "trace-r4"],
                "rationale": "Recommend a separately authorized owner review the zero-row Check as a future Watch; training never activates it.",
            }
        ],
        "presentationTargets": _presentation_targets(),
    }
    return package, datas


def build_variant_package() -> tuple[dict[str, Any], dict[str, bytes]]:
    tables = _absent_config_tables()
    fixture = build_fixture_bytes(tables)
    manifest = build_variant_manifest(fixture)
    datas: dict[str, bytes] = {}
    assets: list[dict[str, Any]] = []

    def add(asset_id: str, kind: str, media_type: str, path: str, data: bytes) -> None:
        datas[asset_id] = data
        assets.append(asset_record(asset_id, kind, media_type, path, data))

    add("fixture-absent-config", "challenge-fixture", "application/vnd.sqlite3", f"{VARIANT_REL}/fixtures/absent-config.db", fixture)
    add("manifest-root-cause-absent-config", "challenge-manifest", "application/json", f"{VARIANT_REL}/challenges/root-cause.json", json_bytes(manifest))
    add("trace-r2", "evidence-log", "application/x-ndjson", f"{TRAINING_REL}/evidence/traces/trace-r2.jsonl", _trace_r2())
    add("trace-r4", "evidence-log", "application/x-ndjson", f"{TRAINING_REL}/evidence/traces/trace-r4.jsonl", _trace_r4())

    case = _case(
        "root-cause-absent-config",
        "Root cause unconfirmed",
        "incident-0042-absent-config",
        ["trace-r2", "trace-r4"],
        [
            _finding(
                "cause-unconfirmed",
                "Retries and deployment timing are correlations; no reviewed configuration diff is declared.",
                "hypothesis",
                ["trace-r2", "trace-r4"],
            )
        ],
        [
            _timeline("variant-evidence", "2026-01-12T11:20:00Z", "daniel", "evidence-revealed", "evidence", "trace-r2"),
            _timeline("variant-finding", "2026-01-12T11:21:00Z", "maya", "finding-recorded", "finding", "cause-unconfirmed"),
        ],
    )

    package = {
        "schema": SCHEMA_PACKAGE,
        "id": "phantom-orders-absent-config",
        "revision": REVISION,
        "assets": assets,
        "fictionalActors": [{"id": actor_id, "name": name} for actor_id, name in ACTORS],
        "sources": [],
        "cases": [case],
        "incidents": [
            {
                "id": "incident-0042-absent-config",
                "title": "Duplicate charges with no configuration evidence",
                "description": "Synthetic absent-configuration variant; the reviewed configuration diff is not declared and the cause remains unconfirmed.",
                "status": "investigating",
                "evidenceIds": ["trace-r2", "trace-r4"],
            }
        ],
        "checks": [],
        "queries": [],
        "challenges": [
            {
                "id": "root-cause-absent-config",
                "revision": REVISION,
                "manifestAssetId": "manifest-root-cause-absent-config",
                "fixtures": [{"fixtureId": "absent-config", "assetId": "fixture-absent-config"}],
            }
        ],
        "proposals": [],
        "presentationTargets": [
            {"id": "case-root-cause-absent-config", "kind": "case", "refId": "root-cause-absent-config"},
            {"id": "incident-0042-absent-config", "kind": "incident", "refId": "incident-0042-absent-config"},
            {"id": "evidence-trace-r2", "kind": "evidence", "refId": "trace-r2"},
            {"id": "evidence-trace-r4", "kind": "evidence", "refId": "trace-r4"},
        ],
    }
    return package, datas


# ---------------------------------------------------------------------------
# Narrative sidecar and declaration
# ---------------------------------------------------------------------------


def _presentation(speed: str = "natural") -> dict[str, Any]:
    return {
        "delayBeforeMs": 0,
        "pauseAfterMs": 700,
        "typingSpeed": speed,
        "typingIndicator": True,
        "transition": "fade",
    }


def _chat(
    event_id: str,
    chapter_id: str,
    actor_id: str,
    message_key: str,
    speed: str = "natural",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "chapterId": chapter_id,
        "type": "chat.message",
        "payload": {"actorId": actor_id, "messageKey": message_key, "attachmentIds": []},
        "presentation": _presentation(speed),
    }


def _marker(event_id: str, chapter_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event_id,
        "chapterId": chapter_id,
        "type": event_type,
        "payload": payload,
    }


def _chapter_events(chapter_id: str, chapter_index: int) -> tuple[list[dict[str, Any]], str, str]:
    case_target = f"case-{chapter_id}"
    solve_step = f"{chapter_id}-solve"
    checkpoint_id = f"{chapter_id}-result"
    events: list[dict[str, Any]] = []
    prefix = f"ch{chapter_index + 1}"

    events.append(_marker(f"{prefix}-open", chapter_id, "detective.open", {"manifestCaseId": chapter_id}))
    events.append(
        _marker(
            f"{prefix}-focus",
            chapter_id,
            "camera.focus",
            {"targetId": case_target},
        )
    )
    events.append(
        _chat(
            f"{prefix}-context-label",
            chapter_id,
            "incidentius",
            "context.supplied" if chapter_index > 0 else "ch1.incidentius.open",
            "fast",
        )
    )
    if chapter_index == 0:
        pass
    if chapter_id == "duplicate-payments":
        events.extend(
            [
                _chat(f"{prefix}-sarah", chapter_id, "sarah", "ch1.sarah.context"),
                _chat(f"{prefix}-maya", chapter_id, "maya", "ch1.maya.context"),
                _chat(f"{prefix}-daniel", chapter_id, "daniel", "ch1.daniel.context", "deliberate"),
                _marker(f"{prefix}-prompt", chapter_id, "challenge.prompt", {"stepId": solve_step}),
                _marker(
                    f"{prefix}-await",
                    chapter_id,
                    "challenge.await_validation",
                    {"stepId": solve_step, "checkpointId": checkpoint_id},
                ),
                _chat(f"{prefix}-success", chapter_id, "maya", "ch1.maya.success"),
            ]
        )
    elif chapter_id == "payment-impact":
        events.extend(
            [
                _chat(f"{prefix}-sarah", chapter_id, "sarah", "ch2.sarah.context"),
                _chat(f"{prefix}-maya", chapter_id, "maya", "ch2.maya.context"),
                _chat(f"{prefix}-daniel", chapter_id, "daniel", "ch2.daniel.context", "deliberate"),
                _marker(f"{prefix}-prompt", chapter_id, "challenge.prompt", {"stepId": solve_step}),
                _marker(
                    f"{prefix}-await",
                    chapter_id,
                    "challenge.await_validation",
                    {"stepId": solve_step, "checkpointId": checkpoint_id},
                ),
                _chat(f"{prefix}-success", chapter_id, "sarah", "ch2.sarah.success"),
            ]
        )
    elif chapter_id == "failure-window":
        events.extend(
            [
                _chat(f"{prefix}-maya", chapter_id, "maya", "ch3.maya.context"),
                _chat(f"{prefix}-daniel", chapter_id, "daniel", "ch3.daniel.context", "deliberate"),
                _chat(f"{prefix}-sarah", chapter_id, "sarah", "ch3.sarah.context"),
                _marker(f"{prefix}-prompt", chapter_id, "challenge.prompt", {"stepId": solve_step}),
                _marker(
                    f"{prefix}-await",
                    chapter_id,
                    "challenge.await_validation",
                    {"stepId": solve_step, "checkpointId": checkpoint_id},
                ),
                _chat(f"{prefix}-success", chapter_id, "daniel", "ch3.daniel.success", "deliberate"),
            ]
        )
    elif chapter_id == "retry-evidence":
        events.extend(
            [
                _chat(f"{prefix}-daniel", chapter_id, "daniel", "ch4.daniel.context", "deliberate"),
                _chat(f"{prefix}-maya", chapter_id, "maya", "ch4.maya.context"),
                _chat(f"{prefix}-sarah", chapter_id, "sarah", "ch4.sarah.context"),
                _marker(f"{prefix}-prompt", chapter_id, "challenge.prompt", {"stepId": solve_step}),
                _marker(
                    f"{prefix}-await",
                    chapter_id,
                    "challenge.await_validation",
                    {"stepId": solve_step, "checkpointId": checkpoint_id},
                ),
                _chat(f"{prefix}-success", chapter_id, "maya", "ch4.maya.success"),
            ]
        )
    elif chapter_id == "root-cause":
        events.extend(
            [
                _chat(f"{prefix}-daniel", chapter_id, "daniel", "ch5.daniel.complete", "deliberate"),
                _chat(f"{prefix}-maya", chapter_id, "maya", "ch5.maya.context"),
                _chat(f"{prefix}-sarah", chapter_id, "sarah", "ch5.sarah.context"),
                _marker(f"{prefix}-prompt", chapter_id, "challenge.prompt", {"stepId": solve_step}),
                _marker(
                    f"{prefix}-await",
                    chapter_id,
                    "challenge.await_validation",
                    {"stepId": solve_step, "checkpointId": checkpoint_id},
                ),
                _chat(f"{prefix}-success", chapter_id, "daniel", "ch5.daniel.success.complete", "deliberate"),
            ]
        )
    elif chapter_id == "prevention":
        events.extend(
            [
                _chat(f"{prefix}-maya", chapter_id, "maya", "ch6.maya.context"),
                _chat(f"{prefix}-daniel", chapter_id, "daniel", "ch6.daniel.context", "deliberate"),
                _chat(f"{prefix}-sarah", chapter_id, "sarah", "ch6.sarah.context"),
                _marker(f"{prefix}-prompt", chapter_id, "challenge.prompt", {"stepId": solve_step}),
                _marker(
                    f"{prefix}-await",
                    chapter_id,
                    "challenge.await_validation",
                    {"stepId": solve_step, "checkpointId": checkpoint_id},
                ),
                _marker(
                    f"{prefix}-check",
                    chapter_id,
                    "check.run",
                    {"checkId": "prevention-check", "referenceOutcome": "passed", "referenceAssisted": True},
                ),
                _marker(
                    f"{prefix}-proposal",
                    chapter_id,
                    "postmortem.recommend",
                    {"proposalId": "watch-proposal"},
                ),
                _chat(f"{prefix}-incidentius-proposal", chapter_id, "incidentius", "ch6.incidentius.proposal", "fast"),
                _chat(f"{prefix}-success", chapter_id, "maya", "ch6.maya.success"),
                _chat(f"{prefix}-synthetic", chapter_id, "incidentius", "ch6.synthetic", "fast"),
                _chat(f"{prefix}-postmortem", chapter_id, "daniel", "ch6.postmortem", "deliberate"),
            ]
        )
    return events, solve_step, checkpoint_id


def build_narrative() -> tuple[bytes, bytes, dict[str, Any]]:
    catalogue = {
        "schemaVersion": SCHEMA_CATALOGUE,
        "locale": "en",
        "messages": dict(MESSAGES),
    }
    catalogue_bytes = json_bytes(catalogue)

    events: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    for index, (chapter_id, _) in enumerate(CHAPTERS):
        chapter_events, solve_step, checkpoint_id = _chapter_events(chapter_id, index)
        events.extend(chapter_events)
        segment_id = f"{chapter_id}-debrief"
        prerequisite: list[str] = []
        if index > 0:
            previous_prefix = f"ch{index}"
            previous_chapter = CHAPTERS[index - 1][0]
            if previous_chapter == "prevention":
                previous_success = f"{previous_prefix}-success"
            else:
                previous_success = f"{previous_prefix}-success"
            prerequisite = [previous_success]
        segments.append(
            {
                "id": segment_id,
                "chapterId": chapter_id,
                "stepId": f"{chapter_id}-debrief",
                "eventIds": [event["id"] for event in chapter_events],
                "prerequisiteContextEventIds": prerequisite,
            }
        )

    sidecar = {
        "schemaVersion": SCHEMA_NARRATIVE,
        "scenarioId": SCENARIO,
        "revision": REVISION,
        "locale": "en",
        "fallbackLocale": "en",
        "messageCatalogues": [
            {
                "locale": "en",
                "path": f"{DECLARATION_REL}/messages.en.json",
                "sha256": sha256_hex(catalogue_bytes),
                "bytes": len(catalogue_bytes),
            }
        ],
        "chapterRefs": [chapter_id for chapter_id, _ in CHAPTERS],
        "actors": [{"id": actor_id, "name": name} for actor_id, name in ACTORS],
        "assets": [],
        "segments": segments,
        "events": events,
    }
    return json_bytes(sidecar), catalogue_bytes, sidecar


def build_declaration(package_ref: dict[str, Any], narrative_bytes: bytes) -> bytes:
    def training_case_target(case_id: str) -> dict[str, Any]:
        return {
            "kind": "training-case",
            "manifestCaseId": case_id,
            "trainingPackage": package_ref,
        }

    chapters = []
    for chapter_id, title in CHAPTERS:
        chapters.append(
            {
                "id": chapter_id,
                "title": title,
                "why": f"Training chapter {title.lower()}.",
                "steps": [
                    {
                        "id": f"{chapter_id}-case",
                        "kind": "standard",
                        "title": "Open the training case",
                        "why": "Inspect the declared fictional Case and its evidence before solving.",
                        "modes": ["explore"],
                        "target": training_case_target(chapter_id),
                        "done": {"kind": "route-reached"},
                    },
                    {
                        "id": f"{chapter_id}-solve",
                        "kind": "challenge",
                        "title": "Solve the pinned challenge",
                        "why": "Write and submit the required SQL and typed answers in the real challenge editor.",
                        "target": {
                            "kind": "challenge",
                            "challengeId": chapter_id,
                            "revision": REVISION,
                        },
                        "done": {
                            "kind": "challenge-passed",
                            "checkpoints": [
                                {
                                    "id": f"{chapter_id}-result",
                                    "completion": "whole-challenge",
                                }
                            ],
                        },
                    },
                    {
                        "id": f"{chapter_id}-debrief",
                        "kind": "scripted-dialogue",
                        "segmentId": f"{chapter_id}-debrief",
                        "title": "Debrief the evidence",
                        "why": "Read the fictional context, open the challenge, and wait for a validated pass.",
                        "modes": ["guided"],
                        "target": {"kind": "none"},
                        "done": {"kind": "dialogue-finished"},
                    },
                ],
            }
        )
    declaration = {
        "schema": SCHEMA_WALKTHROUGH,
        "id": SCENARIO,
        "version": REVISION,
        "title": SCENARIO_TITLE,
        "summary": "A six-chapter synthetic incident investigation about duplicate successful charges.",
        "trainingPackage": package_ref,
        "narrative": reference(f"{DECLARATION_REL}/narrative.json", narrative_bytes),
        "chapters": chapters,
        "finish": {"index": True},
    }
    return json_bytes(declaration)


def build_variant_narrative() -> tuple[bytes, bytes, dict[str, Any]]:
    catalogue = {
        "schemaVersion": SCHEMA_CATALOGUE,
        "locale": "en",
        "messages": {
            "context.supplied": MESSAGES["context.supplied"],
            "absent.daniel.missing": MESSAGES["absent.daniel.missing"],
            "absent.maya.context": MESSAGES["absent.maya.context"],
            "absent.sarah.context": MESSAGES["absent.sarah.context"],
            "absent.daniel.success": MESSAGES["absent.daniel.success"],
        },
    }
    catalogue_bytes = json_bytes(catalogue)
    chapter_id = "root-cause"
    solve_step = "root-cause-solve"
    checkpoint_id = "root-cause-result"
    events = [
        _marker("absent-open", chapter_id, "detective.open", {"manifestCaseId": "root-cause-absent-config"}),
        _marker(
            "absent-focus",
            chapter_id,
            "camera.focus",
            {"targetId": "case-root-cause-absent-config"},
        ),
        _chat("absent-context-label", chapter_id, "incidentius", "context.supplied", "fast"),
        _chat("absent-daniel", chapter_id, "daniel", "absent.daniel.missing", "deliberate"),
        _chat("absent-maya", chapter_id, "maya", "absent.maya.context"),
        _chat("absent-sarah", chapter_id, "sarah", "absent.sarah.context"),
        _marker("absent-prompt", chapter_id, "challenge.prompt", {"stepId": solve_step}),
        _marker(
            "absent-await",
            chapter_id,
            "challenge.await_validation",
            {"stepId": solve_step, "checkpointId": checkpoint_id},
        ),
        _chat("absent-success", chapter_id, "daniel", "absent.daniel.success", "deliberate"),
    ]
    sidecar = {
        "schemaVersion": SCHEMA_NARRATIVE,
        "scenarioId": "phantom-orders-absent-config",
        "revision": REVISION,
        "locale": "en",
        "fallbackLocale": "en",
        "messageCatalogues": [
            {
                "locale": "en",
                "path": f"{VARIANT_REL}/messages.en.json",
                "sha256": sha256_hex(catalogue_bytes),
                "bytes": len(catalogue_bytes),
            }
        ],
        "chapterRefs": [chapter_id],
        "actors": [{"id": actor_id, "name": name} for actor_id, name in ACTORS],
        "assets": [],
        "segments": [
            {
                "id": "root-cause-debrief",
                "chapterId": chapter_id,
                "stepId": "root-cause-debrief",
                "eventIds": [event["id"] for event in events],
                "prerequisiteContextEventIds": [],
            }
        ],
        "events": events,
    }
    return json_bytes(sidecar), catalogue_bytes, sidecar


def build_variant_declaration(package_ref: dict[str, Any], narrative_bytes: bytes) -> bytes:
    declaration = {
        "schema": SCHEMA_WALKTHROUGH,
        "id": "phantom-orders-absent-config",
        "version": REVISION,
        "title": "The Phantom Orders: absent configuration",
        "summary": "A focused synthetic variant that refuses causal certainty without a reviewed diff.",
        "trainingPackage": package_ref,
        "narrative": reference(f"{VARIANT_REL}/narrative.json", narrative_bytes),
        "chapters": [
            {
                "id": "root-cause",
                "title": "Prove the root cause without configuration evidence",
                "why": "Distinguish correlation from a supported cause when the reviewed diff is absent.",
                "steps": [
                    {
                        "id": "root-cause-case",
                        "kind": "standard",
                        "title": "Open the training case",
                        "why": "Inspect the declared fictional Case and the two declared traces.",
                        "modes": ["explore"],
                        "target": {
                            "kind": "training-case",
                            "manifestCaseId": "root-cause-absent-config",
                            "trainingPackage": package_ref,
                        },
                        "done": {"kind": "route-reached"},
                    },
                    {
                        "id": "root-cause-solve",
                        "kind": "challenge",
                        "title": "Solve the pinned variant challenge",
                        "why": "Submit the SQL cohort and the uncertainty-respecting typed answers.",
                        "target": {
                            "kind": "challenge",
                            "challengeId": "root-cause-absent-config",
                            "revision": REVISION,
                        },
                        "done": {
                            "kind": "challenge-passed",
                            "checkpoints": [
                                {"id": "root-cause-result", "completion": "whole-challenge"}
                            ],
                        },
                    },
                    {
                        "id": "root-cause-debrief",
                        "kind": "scripted-dialogue",
                        "segmentId": "root-cause-debrief",
                        "title": "Debrief the uncertainty",
                        "why": "Read the missing-configuration context and wait for a validated pass.",
                        "modes": ["guided"],
                        "target": {"kind": "none"},
                        "done": {"kind": "dialogue-finished"},
                    },
                ],
            }
        ],
        "finish": {"index": True},
    }
    return json_bytes(declaration)


# ---------------------------------------------------------------------------
# Full artifact assembly and writing
# ---------------------------------------------------------------------------


def build_assets() -> dict[str, bytes]:
    package, package_datas = build_primary_package()
    package_index = json_bytes(package)
    package_ref = package_reference(
        SCENARIO,
        REVISION,
        f"{TRAINING_REL}/package.json",
        package_index,
    )
    narrative_bytes, catalogue_bytes, _ = build_narrative()
    declaration_bytes = build_declaration(package_ref, narrative_bytes)

    variant_package, variant_datas = build_variant_package()
    variant_index = json_bytes(variant_package)
    variant_ref = package_reference(
        "phantom-orders-absent-config",
        REVISION,
        f"{VARIANT_REL}/package.json",
        variant_index,
    )
    variant_narrative, variant_catalogue, _ = build_variant_narrative()
    variant_declaration = build_variant_declaration(variant_ref, variant_narrative)

    assets: dict[str, bytes] = {}
    for package_data in (package_datas, variant_datas):
        for asset_id, data in package_data.items():
            record = _asset_record_for_id(package, variant_package, asset_id=asset_id)
            assets[f"{PROJECT}/{record['path']}"] = data
    assets[f"{TRAINING}/package.json"] = package_index
    assets[f"{VARIANT}/package.json"] = variant_index
    assets[f"{DECLARATION_DIR}/walkthrough.json"] = declaration_bytes
    assets[f"{DECLARATION_DIR}/narrative.json"] = narrative_bytes
    assets[f"{DECLARATION_DIR}/messages.en.json"] = catalogue_bytes
    assets[f"{VARIANT}/walkthrough.json"] = variant_declaration
    assets[f"{VARIANT}/narrative.json"] = variant_narrative
    assets[f"{VARIANT}/messages.en.json"] = variant_catalogue
    return assets


def _asset_record_for_id(*packages: dict[str, Any], asset_id: str) -> dict[str, Any]:
    for package in packages:
        for record in package["assets"]:
            if record["id"] == asset_id:
                return record
    raise KeyError(asset_id)


def regenerate(root: Path = ROOT) -> None:
    assets = build_assets()
    for relative, data in sorted(assets.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _read(root: Path, relative: str) -> bytes:
    return (root / relative).read_bytes()


def _execute(fixture_bytes: bytes, sql: str) -> list[tuple[Any, ...]]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(fixture_bytes)
        cursor = connection.execute(sql)
        return [tuple(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def _oracle_python_rows(oracle: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for row in oracle["rows"]:
        values: list[Any] = []
        for cell in row:
            if cell["type"] == "null":
                values.append(None)
            elif cell["type"] == "integer":
                values.append(int(cell["value"]))
            else:
                values.append(cell["value"])
        rows.append(tuple(values))
    return rows


def _row_multiset(rows: Iterable[Sequence[Any]]) -> dict[tuple[Any, ...], int]:
    counts: dict[tuple[Any, ...], int] = {}
    for row in rows:
        key = tuple(row)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _sql_matches(fixture: bytes, sql: str, oracle: Mapping[str, Any]) -> bool:
    actual = _execute(fixture, sql)
    expected = _oracle_python_rows(oracle)
    return _row_multiset(actual) == _row_multiset(expected)


def _check_outcome(fixture: bytes, sql: str, expected_count: int = 0) -> str:
    rows = _execute(fixture, sql)
    return "pass" if len(rows) == expected_count else "fail"


def _all_sql_cases(manifest: Mapping[str, Any]) -> list[tuple[str, str, Mapping[str, Any]]]:
    cases: list[tuple[str, str, Mapping[str, Any]]] = []
    for part in manifest["parts"]:
        if part["answerKind"] != "sql":
            continue
        for case in part["sql"]["cases"]:
            cases.append((part["id"], case["fixture"], case["oracle"]))
    return cases


def verify(root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    evidence: dict[str, Any] = {}

    expected_assets = build_assets()
    committed_paths = set()
    for relative, expected in sorted(expected_assets.items()):
        path = root / relative
        if not path.is_file():
            errors.append(f"missing committed asset {relative}")
            continue
        committed_paths.add(relative)
        actual = path.read_bytes()
        if actual != expected:
            errors.append(f"authored bytes differ for {relative}")
        if sha256_hex(actual) != sha256_hex(expected):
            errors.append(f"authored digest differs for {relative}")

    for owned_root in (
        root / TRAINING,
        root / DECLARATION_DIR,
    ):
        if not owned_root.exists():
            continue
        for path in sorted(owned_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative not in committed_paths:
                errors.append(f"unexpected file in owned content tree {relative}")

    package = json.loads(expected_assets[f"{TRAINING}/package.json"])
    variant_package = json.loads(expected_assets[f"{VARIANT}/package.json"])
    declaration = json.loads(expected_assets[f"{DECLARATION_DIR}/walkthrough.json"])
    sidecar = json.loads(expected_assets[f"{DECLARATION_DIR}/narrative.json"])
    catalogue = json.loads(expected_assets[f"{DECLARATION_DIR}/messages.en.json"])
    variant_declaration = json.loads(expected_assets[f"{VARIANT}/walkthrough.json"])
    variant_sidecar = json.loads(expected_assets[f"{VARIANT}/narrative.json"])
    variant_catalogue = json.loads(expected_assets[f"{VARIANT}/messages.en.json"])

    # Pin closure in both directions.
    asset_by_id = {asset["id"]: asset for asset in package["assets"]}
    for asset in package["assets"]:
        data = expected_assets.get(f"{PROJECT}/{asset['path']}")
        if data is None:
            errors.append(f"package asset has no authored bytes: {asset['id']}")
            continue
        if len(data) != asset["bytes"] or sha256_hex(data) != asset["sha256"]:
            errors.append(f"package asset pin mismatch: {asset['id']}")

    package_bytes = expected_assets[f"{TRAINING}/package.json"]
    declaration_bytes = expected_assets[f"{DECLARATION_DIR}/walkthrough.json"]
    narrative_bytes = expected_assets[f"{DECLARATION_DIR}/narrative.json"]
    catalogue_bytes = expected_assets[f"{DECLARATION_DIR}/messages.en.json"]
    if declaration["trainingPackage"]["sha256"] != sha256_hex(package_bytes):
        errors.append("declaration package digest mismatch")
    if declaration["narrative"]["sha256"] != sha256_hex(narrative_bytes):
        errors.append("declaration narrative digest mismatch")
    if sidecar["messageCatalogues"][0]["sha256"] != sha256_hex(catalogue_bytes):
        errors.append("sidecar catalogue digest mismatch")

    variant_package_bytes = expected_assets[f"{VARIANT}/package.json"]
    variant_narrative_bytes = expected_assets[f"{VARIANT}/narrative.json"]
    variant_catalogue_bytes = expected_assets[f"{VARIANT}/messages.en.json"]
    if variant_declaration["trainingPackage"]["sha256"] != sha256_hex(variant_package_bytes):
        errors.append("variant declaration package digest mismatch")
    if variant_declaration["narrative"]["sha256"] != sha256_hex(variant_narrative_bytes):
        errors.append("variant declaration narrative digest mismatch")
    if variant_sidecar["messageCatalogues"][0]["sha256"] != sha256_hex(variant_catalogue_bytes):
        errors.append("variant sidecar catalogue digest mismatch")

    # Declaration/narrative structural coherence.
    chapter_ids = [chapter["id"] for chapter in declaration["chapters"]]
    if sidecar["chapterRefs"] != chapter_ids:
        errors.append("sidecar chapterRefs do not equal declaration chapters")
    dialogue_steps = {
        step["segmentId"]: (chapter["id"], step["id"], step["done"])
        for chapter in declaration["chapters"]
        for step in chapter["steps"]
        if step["kind"] == "scripted-dialogue"
    }
    for segment in sidecar["segments"]:
        bound = dialogue_steps.get(segment["id"])
        if bound is None:
            errors.append(f"sidecar segment {segment['id']} has no dialogue step")
        elif bound[0] != segment["chapterId"] or bound[1] != segment["stepId"]:
            errors.append(f"sidecar segment {segment['id']} chapter/step mismatch")
    for key in catalogue["messages"]:
        if not key:
            errors.append("empty catalogue key")

    messages = catalogue["messages"]
    for event in sidecar["events"]:
        if event["type"] == "chat.message":
            key = event["payload"]["messageKey"]
            if key not in messages:
                errors.append(f"message key missing from catalogue: {key}")

    # Fixture and oracle verification.
    fixture_assets = {
        asset["id"]: expected_assets[f"{PROJECT}/{asset['path']}"]
        for asset in package["assets"]
        if asset["kind"] == "challenge-fixture"
    }
    fixture_names = {
        asset["id"].removeprefix("fixture-"): asset["id"]
        for asset in package["assets"]
        if asset["kind"] == "challenge-fixture"
    }

    sql_receipts: dict[str, Any] = {}
    for challenge_id, manifest in build_manifests().items():
        for part_id, fixture_name, oracle in _all_sql_cases(manifest):
            fixture = fixture_assets[fixture_names[fixture_name]]
            if not _sql_matches(fixture, REFERENCE_SQL[challenge_id], oracle):
                errors.append(
                    f"reference SQL does not match oracle: {challenge_id}/{part_id}/{fixture_name}"
                )
            if not _sql_matches(fixture, ALTERNATE_SQL[challenge_id], oracle):
                errors.append(
                    f"alternate SQL does not match oracle: {challenge_id}/{part_id}/{fixture_name}"
                )
        sql_receipts[challenge_id] = {
            "reference": "matched every declared case",
            "alternate": "matched every declared case",
        }

    # Wrong mutations must differ on the base fixture.
    wrong_receipts: dict[str, Any] = {}
    base_fixture = fixture_assets["fixture-base"]
    base_manifest = build_manifests()
    for challenge_id, mutations in WRONG_SQL.items():
        base_oracle = None
        for part_id, fixture_name, oracle in _all_sql_cases(base_manifest[challenge_id]):
            if fixture_name == "base":
                base_oracle = oracle
                break
        if base_oracle is None:
            errors.append(f"no base oracle for wrong mutations: {challenge_id}")
            continue
        wrong_receipts[challenge_id] = {}
        for name, sql in mutations.items():
            if _sql_matches(base_fixture, sql, base_oracle):
                errors.append(f"wrong mutation unexpectedly passes: {challenge_id}/{name}")
                wrong_receipts[challenge_id][name] = "UNEXPECTED PASS"
            else:
                wrong_receipts[challenge_id][name] = "rejected"

    # Structured wrong answers.
    for challenge_id in ("failure-window", "retry-evidence", "root-cause", "prevention"):
        manifest = base_manifest[challenge_id]
        failed = False
        for part in manifest["parts"]:
            if part["answerKind"] != "structured":
                continue
            for field in part["structured"]["fields"]:
                expected = part["structured"]["expected"]["selections"][field["id"]]
                # A deliberately wrong selection is any option not expected, or
                # the empty set where the field allows it.
                wrong = next(
                    (option["id"] for option in field["options"] if option["id"] not in expected),
                    None,
                )
                if wrong is not None and wrong not in expected:
                    failed = True
        if not failed:
            errors.append(f"no wrong structured selection available: {challenge_id}")

    # Prevention Check matrix.
    prevention_manifest = base_manifest["prevention"]
    check_part = next(part for part in prevention_manifest["parts"] if part["answerKind"] == "check-definition")
    prevention_receipt: dict[str, str] = {}
    for case in check_part["checkDefinition"]["cases"]:
        fixture = fixture_assets[fixture_names[case["fixture"]]]
        outcome = _check_outcome(fixture, REFERENCE_SQL["prevention"], 0)
        prevention_receipt[case["fixture"]] = outcome
        if outcome != case["expectedOutcome"]:
            errors.append(
                f"prevention Check outcome mismatch: {case['fixture']} expected {case['expectedOutcome']} got {outcome}"
            )
    if prevention_receipt.get("base") != "fail" or prevention_receipt.get("repaired") != "pass" or prevention_receipt.get("mutated") != "fail":
        errors.append("prevention Check matrix does not prove broken/repaired/mutated semantics")

    # Absent-config variant: genuine semantics and no causal leakage.
    variant_fixture = expected_assets[f"{VARIANT}/fixtures/absent-config.db"]
    variant_manifest = build_variant_manifest(variant_fixture)
    variant_cases = _all_sql_cases(variant_manifest)
    for part_id, fixture_name, oracle in variant_cases:
        if not _sql_matches(variant_fixture, REFERENCE_SQL["root-cause"], oracle):
            errors.append("variant reference SQL does not match its oracle")
        if not _sql_matches(variant_fixture, ALTERNATE_SQL["root-cause"], oracle):
            errors.append("variant alternate SQL does not match its oracle")
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(variant_fixture)
        flags = connection.execute("SELECT version, idempotency_enabled FROM deployments ORDER BY version").fetchall()
    finally:
        connection.close()
    if flags != [("pay-16", None), ("pay-17", None)]:
        errors.append("variant deployment idempotency flags are not both NULL")
    variant_text = json.dumps(variant_package, ensure_ascii=False) + json.dumps(variant_sidecar, ensure_ascii=False) + json.dumps(variant_catalogue, ensure_ascii=False)
    for forbidden in (
        "config-pay-17",
        "idempotency_enabled=1",
        "idempotency_enabled=0",
        "omitted the idempotency header",
    ):
        if forbidden in variant_text:
            errors.append(f"variant leaks causal material: {forbidden}")
    variant_cause = next(part for part in variant_manifest["parts"] if part["id"] == "cause")
    variant_deployment = next(part for part in variant_manifest["parts"] if part["id"] == "deployment")
    variant_citations = next(part for part in variant_manifest["parts"] if part["id"] == "citations")
    if variant_cause["structured"]["expected"]["selections"]["cause"] != ["insufficient-evidence"]:
        errors.append("variant cause is not insufficient-evidence")
    if variant_deployment["structured"]["expected"]["selections"]["deployment"] != ["unknown"]:
        errors.append("variant deployment is not unknown")
    if variant_citations["structured"]["expected"]["selections"]["citations"] != ["trace-r2", "trace-r4"]:
        errors.append("variant citations are not trace-r2 and trace-r4")
    if any(option["id"] == "config-pay-17" for option in variant_citations["structured"]["fields"][0]["options"]):
        errors.append("variant citations offer a configuration option")

    # The primary package has six ordered challenge manifests.
    if len(package["challenges"]) != 6:
        errors.append("primary package does not declare six challenges")
    if [challenge["id"] for challenge in package["challenges"]] != [chapter_id for chapter_id, _ in CHAPTERS]:
        errors.append("primary challenge order differs from chapter order")

    evidence.update(
        {
            "ok": not errors,
            "errors": errors,
            "sqliteVersion": sqlite3.sqlite_version,
            "enginePin": dict(ENGINE),
            "assetCount": len(expected_assets),
            "committedBytes": sum(len(data) for data in expected_assets.values()),
            "sqlReceipts": sql_receipts,
            "wrongMutations": wrong_receipts,
            "preventionMatrix": prevention_receipt,
            "variantFlags": flags,
            "variantCause": variant_cause["structured"]["expected"]["selections"]["cause"],
            "variantDeployment": variant_deployment["structured"]["expected"]["selections"]["deployment"],
            "variantCitations": variant_citations["structured"]["expected"]["selections"]["citations"],
        }
    )
    return evidence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("regenerate", "verify"))
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    if args.mode == "regenerate":
        regenerate(args.root)
        return 0
    report = verify(args.root)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
