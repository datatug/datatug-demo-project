#!/usr/bin/env python3
"""Extend the existing 11045 fixture in an isolated operator-owned copy.

No daemon, port, credential or shared project is created by this helper.
The DataTug daemon executes the existing shipping-carrier-assignment Check.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "demo-project-1"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def prepare(destination, endpoint, namespace, local_owner_fixture=False):
    destination = Path(destination).resolve()
    if destination.exists() or destination == SOURCE or SOURCE in destination.parents:
        raise ValueError("choose a new directory outside the public project")
    from urllib.parse import urlsplit
    address = urlsplit(endpoint)
    if address.username or address.password or address.query or address.fragment:
        raise ValueError("coordinator endpoint must not contain credentials")
    if not address.hostname or (address.scheme != "https" and not (address.scheme == "http" and address.hostname in ["localhost", "127.0.0.1", "::1"])):
        raise ValueError("coordinator requires HTTPS or loopback HTTP")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", namespace):
        raise ValueError("invalid namespace")
    shutil.copytree(SOURCE, destination)
    manifest_path = destination / "datatug-project.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["coordination"] = {"endpoint": endpoint, "namespace": namespace}
    manifest["environments"] = [{"id": "training"}]
    manifest["environmentOrder"] = ["training"]
    write_json(manifest_path, manifest)
    # This is the existing application fixture, copied as a mutable training DB.
    # Original direct logs and manifest artifacts remain immutable and are not
    # ingested into a separate log database.
    working = destination / ".watch-demo" / "shipping.sqlite"
    working.parent.mkdir(mode=0o700)
    shutil.copyfile(destination / "fixtures/shipping/base.sqlite", working)
    working.chmod(0o600)
    # This private synthetic training copy runs in explicit local-owner mode.
    # Preserve the unrelated Customer/Invoice policies as archived provenance;
    # the shared project and its policy enforcement are never changed.
    policies = destination / "policies"
    if local_owner_fixture and policies.exists():
        shutil.move(str(policies), working.parent / "archived-policies")
        policies.mkdir()
    write_json(working.parent / "owner.json", {"format":"datatug-watch-demo/v1", "localOwnerFixture":local_owner_fixture, "projectCopy":str(destination), "sourceDatabaseSHA256":hashlib.sha256((SOURCE / "fixtures/shipping/base.sqlite").read_bytes()).hexdigest()})
    write_json(destination / "environments/training/training.env.json", {
        "id": "training", "dbServers": [{"driver": "sqlite3", "catalogs": ["shipping-working-copy"]}]
    })
    write_json(destination / "environments/training/catalogs/shipping-working-copy/shipping-working-copy.db.json", {
        "driver": "sqlite3", "path": ".watch-demo/shipping.sqlite"
    })
    # These definitions are API input examples, not runtime registrations or
    # private subscriber records in the shared project.
    for name, mode, trigger, initial in [
        ("order-11045-assignment", "one_shot", "becomes_true", "baseline"),
        ("order-11045-continuous", "continuous", "becomes_false", "notify"),
    ]:
        write_json(destination / ".watch-demo" / (name + ".definition.json"), {
            "id": name, "version": 0, "title": "Order 11045 carrier assignment",
            "namespace": namespace, "project": manifest["id"], "environment": "training",
            "visibility": "personal", "checkId": "shipping-carrier-assignment", "checkVersion": "1",
            "inputs": {"order_id": {"type": "integer", "value": "11045"}},
            "schedule": {"intervalSeconds": 10}, "trigger": trigger,
            "initialObservation": initial, "mode": mode,
            "notificationPolicy": {"recovery": True, "cooldownSeconds": 0}
        })
    return destination


def mutate(destination, operation):
    destination = Path(destination).resolve()
    working = destination / ".watch-demo/shipping.sqlite"
    if destination == SOURCE or SOURCE in destination.parents or working.is_symlink() or working.parent.is_symlink() or not working.is_file():
        raise ValueError("prepare a private Watch demo copy first")
    marker = json.loads((working.parent / "owner.json").read_text())
    if marker.get("format") != "datatug-watch-demo/v1" or marker.get("projectCopy") != str(destination):
        raise ValueError("the private Watch demo ownership marker does not match")
    # Reuse exactly the existing correction/replay helper and immutable recovery
    # artifact. A correction alone cannot invent an accepted carrier assignment.
    spec = importlib.util.spec_from_file_location("shipping_fixture", ROOT / "scripts/build-shipping-fixture.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    with sqlite3.connect(working) as database:
        if operation == "correct":
            helper.correct(database)
        elif operation == "replay":
            manifest = json.loads((destination / "fixtures/shipping/manifest.json").read_text())
            recovery = next(item for item in manifest["logs"] if item["path"] == "logs/recovery-11045.jsonl")
            helper.replay(database, 11045, recovery)
        elif operation == "fail-again":
            # A deliberate later application-state change, restricted to this
            # private fixture, lets a continuous Watch fail after recovery.
            database.execute("DELETE FROM assignments WHERE deduplication_key = ?", ("request-11045:assignment",))
        else:
            raise ValueError("unknown fixture operation")
    return hashlib.sha256(working.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare", "correct", "replay", "fail-again"])
    parser.add_argument("destination", type=Path)
    parser.add_argument("--coordinator", default="http://127.0.0.1:8988")
    parser.add_argument("--namespace", default="northwind")
    parser.add_argument("--local-owner-fixture", action="store_true", help="Archive policies only in the private synthetic copy for explicit local-owner execution")
    args = parser.parse_args()
    if args.operation == "prepare":
        print(prepare(args.destination, args.coordinator, args.namespace, args.local_owner_fixture))
    else:
        print(json.dumps({"operation": args.operation, "databaseSHA256": mutate(args.destination, args.operation), "synthetic": True}))


if __name__ == "__main__":
    main()
