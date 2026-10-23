#!/usr/bin/env python3
"""Run real DataTug daemon processes against the existing 11045 SQLite Check.

The process owns its Coordinator listener and three Runners. A finally block
terminates only those child PIDs. Every token is random and held in child process
environments; artifacts contain no tokens or monitored-source credentials.
"""
import argparse
import hashlib
import copy
import importlib.util
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import tempfile
import re
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("watch_demo", HERE / "watch-shipping-demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")
    path.chmod(0o600)


def run(binary, runtime, local_owner_fixture=False, ui_worktree=None):
    if not local_owner_fixture:
        raise ValueError("the synthetic native demo requires explicit --local-owner-fixture opt-in")
    runtime.mkdir(mode=0o700, parents=True, exist_ok=False)
    with socket.socket() as check:
        check.bind(("127.0.0.1", 0))
        port = check.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    users = ["alice", "bob", "carol"]
    env = dict(os.environ)
    for name in users + ["runner1", "runner2", "runner3"]:
        env["WATCH_TEST_" + name.upper()] = secrets.token_urlsafe(36)
    env["WATCH_TEST_DB"] = str(runtime / "coordinator.sqlite")
    projects = [demo.prepare(runtime / f"project-{i}", endpoint, "northwind", local_owner_fixture=True) for i in range(1, 4)]
    database = projects[0] / ".watch-demo/shipping.sqlite"
    for project in projects[1:]:
        write_json(project / "environments/training/catalogs/shipping-working-copy/shipping-working-copy.db.json", {"driver": "sqlite3", "path": str(database)})
    project_id = json.loads((projects[0] / "datatug-project.json").read_text())["id"]
    credentials = [{"kind": "user", "id": name, "accountId": name, "tier": "free", "namespace": "northwind", "project": project_id, "environment": "training", "sharedEditor": True, "email": name + "@example.test", "tokenEnv": "WATCH_TEST_" + name.upper()} for name in users]
    credentials += [{"kind": "runner", "id": name, "namespace": "northwind", "project": project_id, "environment": "training", "tokenEnv": "WATCH_TEST_" + name.upper()} for name in ["runner1", "runner2", "runner3"]]
    base = {"namespace": "northwind", "listen": f"127.0.0.1:{port}", "storage": {"dalgoConnectionEnv": "WATCH_TEST_DB"}, "credentials": credentials, "projectUIURLs": {project_id: f"https://datatug.app/store/http-localhost:8989/project/{project_id}"}, "notifications": {"emailSink": str(runtime / "mail")}}
    if ui_worktree:
        base["allowedOrigins"] = ["http://datatug.localhost:18843"]
    children = []
    retired_children = []
    log_threads = []
    logs = []
    runtime.joinpath("OWNER.md").write_text(f"Owner: watch-shipping-integration.py PID {os.getpid()}\nListener: {endpoint}\nTeardown: the owning script sends SIGTERM to its recorded child PIDs in finally; Ctrl-C invokes the same cleanup. No launchd jobs.\n")

    def call(user, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(endpoint + "/v1/watch/" + path, data=body, headers={"Authorization": "Bearer " + env["WATCH_TEST_" + user.upper()], "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"coordinator {path.split('?')[0]} HTTP {error.code}: {error.read(2048).decode()}") from None

    def wait(label, predicate, timeout=45):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            for process in children:
                if process.poll() is not None:
                    raise RuntimeError(f"owned daemon PID {process.pid} exited {process.returncode}")
            try:
                last = predicate()
                if last:
                    print(label, flush=True)
                    return last
            except OSError:
                pass
            time.sleep(0.2)
        raise RuntimeError(f"timed out: {label}; last={last}")

    def status(user="alice"):
        return call(user, "status")

    def observation(user):
        observations = status(user)["observations"]
        return next((o for o in observations if o["watchId"] == user + "-order-11045"), {})

    def observed(user, value):
        return observation(user).get("value") == value

    phases = []
    def phase(label):
        phases.append({"phase":label,"observations":{user:observation(user) for user in users}})

    try:
        for i, project in enumerate(projects, 1):
            config = copy.deepcopy(base)
            config["runner"] = {"tokenEnv": f"WATCH_TEST_RUNNER{i}", "coordinatorEndpoint": endpoint, "projectDir": str(project), "environment": "training", "principal": "local-watch-owner", "evidenceDir": str(runtime / f"evidence-{i}"), "allowOpaqueSQL": True}
            path = runtime / f"daemon-{i}.json"
            write_json(path, config)
            log = open(runtime / f"daemon-{i}.log", "wb")
            logs.append(log)
            command = [str(binary), "daemon", "--run", "--watch-config", str(path)]
            if i == 1:
                command.insert(2, "--coordinate")
            children.append(subprocess.Popen(command, env=env, stdout=log, stderr=log))
            write_json(runtime / "pids.json", [p.pid for p in children])
        wait("Three real DataTug Runners registered", lambda: len(status()["runners"]) == 3)
        definitions = {}
        for user in users:
            source = projects[0] / ".watch-demo" / ("order-11045-assignment.definition.json" if user == "alice" else "order-11045-continuous.definition.json")
            definition = json.loads(source.read_text())
            definition.update(id=user + "-order-11045", title=user.title() + " order 11045 carrier assignment", lifecycle="paused", enabled=False)
            created = call(user, "definition", {"definition": definition, "operationId": user + "-create", "expectedVersion": 0})["definition"]
            assert created["lifecycle"] == "paused"
            call(user, "subscription", {"watchId": created["id"], "channels": ["in_app", "email"]})
            definitions[user] = call(user, "lifecycle", {"id": created["id"], "lifecycle": "enabled", "operationId": user + "-enable", "expectedVersion": created["version"]})["definition"]
        wait("Actual saved Check observes the existing missing assignment", lambda: all(observed(user, "false") for user in users))
        for user in users:
            assert [d["owner"] for d in call(user, "definitions")["definitions"]] == [user], "personal Watch leaked"
        phase("missing-assignment")
        initial_runs = {user: observation(user)["lastRunId"] for user in users}
        demo.mutate(projects[0], "correct")
        wait("Correction alone remains false on a fresh scheduled Check", lambda: all(observed(user, "false") and observation(user).get("lastRunId") != initial_runs[user] for user in users))
        phase("correction-alone")
        demo.mutate(projects[0], "replay")
        wait("Replay produces true through the actual Check executor", lambda: all(observed(user, "true") for user in users))
        phase("replayed-assignment")
        wait("One-shot completes after its durable notification", lambda: call("alice", "definition?id=" + definitions["alice"]["id"])["definition"]["lifecycle"] == "completed")
        wait("In-app and email recovery delivery persist", lambda: len(call("alice", "inbox")["notifications"]) == 1 and any(item["state"] == "delivered" and item["channel"] == "email" for item in call("alice", "deliveries?watchId=" + definitions["alice"]["id"])["deliveries"]))
        before = len(call("bob", "inbox")["notifications"])
        time.sleep(11)
        assert len(call("bob", "inbox")["notifications"]) == before, "unchanged true observation re-notified"
        demo.mutate(projects[0], "fail-again")
        wait("Continuous Watch alerts again on the deliberate later failure", lambda: observed("bob", "false") and len(call("bob", "inbox")["notifications"]) == before + 1)
        wait("Both continuous users receive the later failure", lambda: all(observed(user,"false") and len(call(user,"inbox")["notifications"]) == before + 1 for user in ["bob","carol"]))
        wait("All seven expected email deliveries are drained", lambda: sum(1 for user in users for item in call(user,"deliveries?watchId="+definitions[user]["id"])["deliveries"] if item["channel"] == "email" and item["state"] == "delivered") == 7)
        phase("later-failure")
        assert len(call("alice", "inbox")["notifications"]) == 1, "completed one-shot re-notified"
        # Restart the combined Coordinator/Runner process on its existing DALGO
        # database. Other outbound runners retain their registered identities.
        coordinator = children[0]
        coordinator.terminate()
        coordinator.wait(timeout=12)
        retired_children.append(coordinator)
        restart_log = open(runtime / "daemon-1-restarted.log", "wb")
        logs.append(restart_log)
        children[0] = subprocess.Popen([str(binary),"daemon","--coordinate","--run","--watch-config",str(runtime/"daemon-1.json")], env=env, stdout=restart_log, stderr=restart_log)
        write_json(runtime / "pids.json", [p.pid for p in children])
        wait("Coordinator restart preserves definitions and re-registers three runners",lambda:len(status()["runners"]) == 3 and call("alice","definition?id="+definitions["alice"]["id"])["definition"]["lifecycle"] == "completed")
        assert len(call("alice","inbox")["notifications"]) == 1
        phase("coordinator-restarted")
        write_json(runtime / "native-receipt.json", {"format":"datatug-watch-native-phases/v1", "phases":phases,"emailDelivered":7,"coordinatorRestarted":True,"runnerPIDs":[p.pid for p in children[:3]],"retiredCoordinatorPID":coordinator.pid})
        if ui_worktree:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1",0))
                agent_port=listener.getsockname()[1]
            # The normal CLI link bootstrap is consumed by the browser. Keep its
            # one-time code only in memory and redact it before writing logs.
            agent_log=open(runtime/"agent.log","w"); logs.append(agent_log)
            agent_env=dict(env,DATATUG_DAEMON_DIR=str(runtime/"agent-state"))
            children.append(subprocess.Popen([str(binary),"serve","--project",str(projects[0]),"--host","127.0.0.1","--port",str(agent_port),"--as","local-watch-owner","--allow-opaque-sql","--evidence-dir",str(runtime/"agent-evidence")],env=agent_env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True))
            write_json(runtime / "pids.json", [p.pid for p in children])
            link_code={}
            def record_agent():
                for line in children[-1].stdout:
                    code=re.search(r"#code=([^\s]+)",line)
                    if code: link_code["value"]=code.group(1)
                    agent_log.write(re.sub(r"#code=[^\s]+","#code=[redacted]",line)); agent_log.flush()
            reader=threading.Thread(target=record_agent,daemon=True)
            reader.start(); log_threads.append(reader)
            def agent_ready():
                if not link_code: return False
                with socket.create_connection(("127.0.0.1",agent_port),timeout=1): return True
            wait("Real DataTug project agent listener and normal link bootstrap are ready",agent_ready)
            browser_env=dict(env,DATATUG_WATCH_REAL_AGENT_CODE=link_code["value"],DATATUG_WATCH_REAL_ENDPOINT=endpoint,DATATUG_WATCH_REAL_AGENT=f"http://127.0.0.1:{agent_port}",DATATUG_WATCH_REAL_PROJECT=project_id,DATATUG_WATCH_REAL_TOKEN=env["WATCH_TEST_ALICE"],NX_DAEMON="false",NX_ISOLATE_PLUGINS="false")
            subprocess.run(["node","node_modules/@playwright/test/cli.js","test","-c","apps/datatug-app/playwright.watch.config.ts","-g","real coordinator","--forbid-only"],cwd=ui_worktree,env=browser_env,check=True)
        browser_watches=[]
        if ui_worktree:
            for item in call("alice","definitions")["definitions"]:
                if item["id"] != definitions["alice"]["id"]:
                    wait("Browser-created Watch email delivery is drained",lambda:any(d["channel"]=="email" and d["state"]=="delivered" for d in call("alice","deliveries?watchId="+item["id"])["deliveries"]))
                    browser_watches.append({"definition":item,"runs":call("alice","runs?watchId="+item["id"])["runs"],"deliveries":call("alice","deliveries?watchId="+item["id"])["deliveries"]})
        result = {"format": "datatug-watch-native-demo/v1", "executable": str(binary), "executableSHA256":hashlib.sha256(binary.read_bytes()).hexdigest(), "browserWatches":browser_watches, "project": project_id, "order": 11045, "synthetic": True, "runnerPIDs": [p.pid for p in children[:3]], "projectAgentPID": children[3].pid if len(children)>3 else None, "runnerCount": 3, "phases":phases, "coordinatorRestarted":True, "browserRealBackend":bool(ui_worktree), "combinedCoordinatorRunner": True, "database": str(database), "users": {user: {"definition": call(user, "definition?id=" + definitions[user]["id"])["definition"], "runs": call(user, "runs?watchId=" + definitions[user]["id"])["runs"], "notifications": call(user, "inbox")["notifications"], "deliveries": call(user, "deliveries?watchId=" + definitions[user]["id"])["deliveries"]} for user in users}, "mailSinkFiles": sorted(path.name for path in (runtime / "mail").glob("*.json"))}
        write_json(runtime / "receipt.json", result)
        print(str(runtime / "receipt.json"), flush=True)
        return result
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process in reversed(children):
            try:
                process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        for reader in log_threads:
            reader.join(timeout=2)
        for log in logs:
            log.close()
        write_json(runtime / "cleanup.json", {"ownerPID": os.getpid(), "children": [{"pid": p.pid, "exitCode": p.returncode} for p in retired_children+children], "allStopped": all(p.poll() is not None for p in retired_children+children)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datatug", required=True, type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--local-owner-fixture", action="store_true", help="Opt into owner mode only for isolated synthetic fixture copies")
    parser.add_argument("--ui-worktree", type=Path, help="Run real backend browser acceptance from the built DataTug UI worktree")
    args = parser.parse_args()
    location = args.runtime or Path(tempfile.mkdtemp(prefix="datatug-watch-native-parent-")) / "run"
    try:
        run(args.datatug.resolve(), location.resolve(), args.local_owner_fixture, args.ui_worktree)
    except Exception as error:
        print(f"Watch native integration failed: {error}; artifacts: {location}", flush=True)
        raise
