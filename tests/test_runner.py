"""Regression checks for the bounded, local reviewed-patch runner.

Run from the project root: python3 -m unittest discover -s tests -v
Python tests use the standard library only. Success-path integration tests run the
real installed Node and Git binaries against disposable fixture copies. Tests
whose names start with ``test_injected_`` deliberately inject failures; they are
failure-handling coverage, not evidence that a real verification succeeded.
"""
from __future__ import annotations

import concurrent.futures
import http.client
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("handoff_under_test", PROJECT / "app.py")
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)
REAL_TOOLS = bool(shutil.which("node") and shutil.which("git"))


class IsolatedApp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="handoff-test-")
        self.root = (Path(self.temp.name) / "project").resolve()
        self.root.mkdir()
        for name in ("fixture", "patches", "web"):
            if (PROJECT / name).exists():
                shutil.copytree(PROJECT / name, self.root / name)
        self.data = Path(self.temp.name) / "data"
        self.app = handoff.Handoff(self.root, self.data)

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def create(self, key="create-0001", objective="Keep todo checkboxes checked after reload"):
        return self.app.create({"objective": objective, "recipe": "todo-persistence-v1"}, key)[0]

    @staticmethod
    def decision(doc, choice="approve"):
        return {"decision": choice, "revision": doc["revision"], "plan_digest": doc["plan_digest"]}

    def finish(self, task_id):
        for thread in self.app.threads:
            thread.join(15)
            self.assertFalse(thread.is_alive(), "runner did not stop within test deadline")
        return self.app.get(task_id)

    def approve(self, doc, key="decision-0001"):
        self.app.decide(doc["id"], self.decision(doc), key)
        return self.finish(doc["id"])

    def assertProblem(self, status, code, callback, *args):
        with self.assertRaises(handoff.Problem) as raised:
            callback(*args)
        self.assertEqual((status, code), (raised.exception.status, raised.exception.code))

    def assertNoExecution(self, doc):
        self.assertEqual(0, doc["run_count"])
        self.assertEqual([], doc["checks"])
        self.assertFalse((self.data / "runs" / doc["id"]).exists())


class RunnerTests(IsolatedApp):
    @unittest.skipUnless(REAL_TOOLS, "real Node and Git required for integration proof")
    def test_real_approved_baseline_failure_patch_and_verification_pass(self):
        before = {p.name: p.read_bytes() for p in (self.root / "fixture").iterdir() if p.is_file()}
        doc = self.create()
        self.assertEqual("awaiting_approval", doc["state"])
        self.assertEqual(handoff.digest(doc["plan"]), doc["plan_digest"])
        self.assertNoExecution(doc)
        done = self.approve(doc)
        self.assertEqual("passed", done["state"], done["error"])
        self.assertEqual(1, done["run_count"])
        self.assertEqual(["baseline", "patch-check", "patch-apply", "verification"], [c["name"] for c in done["checks"]])
        self.assertEqual([1, 0, 0, 0], [c["exit_code"] for c in done["checks"]])
        self.assertIn(handoff.EXPECTED_FAILURE, done["checks"][0]["stdout"])
        self.assertIn("# fail 1", done["checks"][0]["stdout"])
        self.assertIn("# fail 0", done["checks"][-1]["stdout"])
        self.assertEqual(["awaiting_approval", "running", "passed"], [e["state"] for e in done["events"]])
        work = self.data / "runs" / doc["id"]
        self.assertEqual(done, json.loads((work / "evidence.json").read_text()))
        self.assertEqual(doc["plan"], json.loads((work / "approved-plan.json").read_text()))
        for check in done["checks"]:
            self.assertIn(f'exit_code={check["exit_code"]}', (work / f'{check["name"]}.log').read_text())
        for name, content in before.items():
            self.assertEqual(content, (self.root / "fixture" / name).read_bytes(), "shared source fixture must stay unchanged")
            if name != "store.mjs":
                self.assertEqual(content, (work / "fixture" / name).read_bytes())
        self.assertNotEqual(before["store.mjs"], (work / "fixture/store.mjs").read_bytes())

    def test_reject_creates_no_workspace_and_runs_no_command(self):
        doc = self.create()
        with mock.patch.object(self.app, "_command", side_effect=AssertionError("must not execute")) as command:
            result, changed = self.app.decide(doc["id"], self.decision(doc, "reject"), "reject-0001")
        self.assertTrue(changed)
        self.assertEqual("rejected", result["state"])
        self.assertNoExecution(result)
        command.assert_not_called()

    def test_create_is_idempotent_without_extra_task(self):
        first = self.create()
        second, created = self.app.create({"objective": first["objective"], "recipe": "todo-persistence-v1"}, "create-0001")
        self.assertFalse(created)
        self.assertEqual(first, second)
        self.assertEqual(1, self.app.db.execute("SELECT count(*) FROM tasks").fetchone()[0])
        self.assertNoExecution(second)

    def test_create_key_conflict(self):
        self.create()
        self.assertProblem(409, "idempotency_conflict", self.create, "create-0001", "A materially different objective")

    def test_reject_decision_is_idempotent(self):
        doc = self.create()
        body = self.decision(doc, "reject")
        first, _ = self.app.decide(doc["id"], body, "reject-0001")
        second, changed = self.app.decide(doc["id"], body, "reject-0001")
        self.assertFalse(changed)
        self.assertEqual(first, second)
        self.assertNoExecution(second)

    @unittest.skipUnless(REAL_TOOLS, "real Node and Git required")
    def test_approve_decision_retry_does_not_run_twice(self):
        doc = self.create()
        done = self.approve(doc)
        retried, changed = self.app.decide(doc["id"], self.decision(doc), "decision-0001")
        self.assertFalse(changed)
        self.assertEqual(done, retried)
        self.assertEqual(1, len(self.app.threads))
        self.assertEqual(1, retried["run_count"])

    def test_decision_key_conflicts_for_different_decision_or_task(self):
        first, second = self.create(), self.create("create-0002")
        self.app.decide(first["id"], self.decision(first, "reject"), "decision-0001")
        self.assertProblem(409, "idempotency_conflict", self.app.decide, first["id"], self.decision(first), "decision-0001")
        self.assertProblem(409, "idempotency_conflict", self.app.decide, second["id"], self.decision(second, "reject"), "decision-0001")
        self.assertEqual("awaiting_approval", self.app.get(second["id"])["state"])

    def test_stale_plan_revision_and_boolean_revision_rejected(self):
        doc = self.create()
        for i, values in enumerate(({"revision": 0}, {"revision": True}, {"plan_digest": "0" * 64}, {"plan_digest": None})):
            with self.subTest(values=values):
                body = self.decision(doc) | values
                self.assertProblem(409, "stale_approval", self.app.decide, doc["id"], body, f"stale-key-{i}")
        self.assertEqual("awaiting_approval", self.app.get(doc["id"])["state"])
        self.assertNoExecution(self.app.get(doc["id"]))

    def test_second_decision_with_new_key_is_rejected(self):
        doc = self.create()
        self.app.decide(doc["id"], self.decision(doc, "reject"), "reject-0001")
        self.assertProblem(409, "invalid_transition", self.app.decide, doc["id"], self.decision(doc), "approve-0002")

    @unittest.skipUnless(REAL_TOOLS, "real Node and Git required")
    def test_concurrent_double_approval_starts_exactly_one_run(self):
        doc = self.create()
        barrier = threading.Barrier(2)
        def decide(key):
            barrier.wait()
            try:
                self.app.decide(doc["id"], self.decision(doc), key)
                return "accepted"
            except handoff.Problem as exc:
                return exc.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(decide, ("approve-0001", "approve-0002")))
        self.assertCountEqual(["accepted", "invalid_transition"], results)
        done = self.finish(doc["id"])
        self.assertEqual("passed", done["state"], done["error"])
        self.assertEqual(1, done["run_count"])
        self.assertEqual(1, len(self.app.threads))

    def test_malformed_creation_shape(self):
        for body in (None, [], "task", {}, {"objective": "hello"}, {"objective": "hello", "recipe": "todo-persistence-v1", "command": "anything"}):
            with self.subTest(body=body):
                self.assertProblem(400, "invalid_request", self.app.create, body, "create-0001")

    def test_invalid_objectives(self):
        for objective in (None, [], True, 123, "", " abc ", "x" * 2001):
            with self.subTest(objective=str(objective)[:20]):
                self.assertProblem(400, "invalid_objective", self.app.create, {"objective": objective, "recipe": "todo-persistence-v1"}, "create-0001")

    def test_invalid_idempotency_keys(self):
        for key in (None, [], 1, "short", "contains spaces", "x" * 101):
            with self.subTest(key=key):
                self.assertProblem(400, "invalid_key", self.create, key)

    def test_unsupported_recipe_rejected_without_task(self):
        for recipe in ("shell", None, [], {}):
            with self.subTest(recipe=recipe):
                self.assertProblem(422, "unsupported_recipe", self.app.create, {"objective": "Fix my application", "recipe": recipe}, "create-0001")
        self.assertEqual(0, self.app.db.execute("SELECT count(*) FROM tasks").fetchone()[0])

    def test_malformed_decision_shape(self):
        doc = self.create()
        for body in (None, [], {}, self.decision(doc) | {"extra": True}, self.decision(doc) | {"decision": "maybe"}, self.decision(doc) | {"decision": None}):
            with self.subTest(body=body):
                self.assertProblem(400, "invalid_decision", self.app.decide, doc["id"], body, "decision-0001")

    def test_malformed_unhashable_decisions_are_client_errors(self):
        doc = self.create()
        for decision in ([], {}):
            with self.subTest(decision=decision):
                self.assertProblem(400, "invalid_decision", self.app.decide, doc["id"], self.decision(doc) | {"decision": decision}, "decision-0001")

    def test_missing_or_invalid_task_id(self):
        for task_id in ("../../outside", "0" * 32):
            with self.subTest(task_id=task_id):
                self.assertProblem(404, "not_found", self.app.get, task_id)

    def test_patch_drift_fails_before_workspace_or_commands(self):
        doc = self.create()
        patch = self.root / "patches/todo-persistence.patch"
        patch.write_text(patch.read_text() + "\n# drift\n")
        done = self.approve(doc)
        self.assertEqual("failed", done["state"])
        self.assertIn("Patch changed after review", done["error"])
        self.assertNoExecution(done)

    def test_source_drift_fails_before_workspace_or_commands(self):
        doc = self.create()
        source = self.root / "fixture/store.mjs"
        source.write_text(source.read_text() + "\n// drift\n")
        done = self.approve(doc)
        self.assertEqual("failed", done["state"])
        self.assertIn("Fixture changed after review", done["error"])
        self.assertNoExecution(done)

    def test_symlink_source_fails_before_commands(self):
        doc = self.create()
        source = self.root / "fixture/store.mjs"
        outside = self.root / "same-content.mjs"
        outside.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(outside)
        done = self.approve(doc)
        self.assertEqual("failed", done["state"])
        self.assertNoExecution(done)

    @unittest.skipUnless(REAL_TOOLS, "real Node and Git required")
    def test_injected_source_drift_after_read_never_reaches_workspace(self):
        """Fault injection: mutate source after its approved bytes have been read."""
        doc = self.create()
        source = self.root / "fixture/store.mjs"
        original = source.read_bytes()
        read_bytes = Path.read_bytes
        injected = []
        def read_then_drift(path):
            data = read_bytes(path)
            if path == source and not injected:
                source.write_bytes(data + b"\n// injected post-read drift\n")
                injected.append(True)
            return data
        with mock.patch.object(Path, "read_bytes", read_then_drift):
            done = self.approve(doc)
        self.assertEqual([True], injected, "test must actually exercise source drift")
        if done["state"] == "failed":
            self.assertEqual([], done["checks"], "unreviewed source must be blocked before execution")
        else:
            self.assertEqual("passed", done["state"], done["error"])
            expected = original.replace(b"// Known baseline bug: the in-memory toggle is not saved before reload.", b"persist();")
            actual = (self.data / "runs" / doc["id"] / "fixture/store.mjs").read_bytes()
            self.assertEqual(expected, actual, "runner may use the approved snapshot, never the later changed source")

    @unittest.skipUnless(REAL_TOOLS, "real Node and Git required")
    def test_patch_may_not_add_files_outside_declared_changed_files(self):
        patch = self.root / "patches/todo-persistence.patch"
        patch.write_text(patch.read_text() + "\n--- /dev/null\n+++ b/fixture/unapproved.txt\n@@ -0,0 +1 @@\n+Unapproved extra file\n")
        doc = self.create()
        self.assertEqual(["fixture/store.mjs"], doc["plan"]["changed_files"])
        done = self.approve(doc)
        self.assertEqual("failed", done["state"], "a patch that creates undeclared files must fail closed")
        self.assertNotIn("verification", [c["name"] for c in done["checks"]])

    def test_restart_marks_running_interrupted_without_replay(self):
        doc = self.create()
        self.app._update(doc["id"], lambda d: self.app._event(d, "running", "Injected interrupted execution for restart test"))
        self.app.close()
        self.app = handoff.Handoff(self.root, self.data)
        recovered = self.app.get(doc["id"])
        self.assertEqual("interrupted", recovered["state"])
        self.assertEqual("interrupted", recovered["events"][-1]["state"])
        self.assertEqual([], self.app.threads)
        self.assertNoExecution(recovered)
        self.assertProblem(409, "invalid_transition", self.app.decide, doc["id"], self.decision(recovered), "restart-0001")

    def test_restart_preserves_rejected_state_and_decision_idempotency(self):
        doc = self.create()
        body = self.decision(doc, "reject")
        rejected, _ = self.app.decide(doc["id"], body, "reject-0001")
        self.app.close()
        self.app = handoff.Handoff(self.root, self.data)
        replay, changed = self.app.decide(doc["id"], body, "reject-0001")
        self.assertFalse(changed)
        self.assertEqual(rejected, replay)

    @unittest.skipUnless(REAL_TOOLS, "real Node and Git required")
    def test_baseline_that_already_passes_withholds_patch(self):
        source = self.root / "fixture/store.mjs"
        source.write_text(source.read_text().replace("// Known baseline bug: the in-memory toggle is not saved before reload.", "persist();"))
        done = self.approve(self.create())
        self.assertEqual("failed", done["state"])
        self.assertIn("Baseline did not fail exactly one expected regression test", done["error"])
        self.assertEqual(["baseline"], [c["name"] for c in done["checks"]])
        self.assertEqual(0, done["checks"][0]["exit_code"])

    @unittest.skipUnless(REAL_TOOLS, "real Node and Git required")
    def test_injected_failed_verification_retains_failure_evidence(self):
        """Baseline and patch are real; only verification is replaced by an explicit failing process."""
        doc = self.create()
        command = self.app._command
        def fail_verification(task_id, work, name, argv):
            if name == "verification":
                argv = [sys.executable, "-c", "print('INJECTED verification failure'); raise SystemExit(7)"]
            return command(task_id, work, name, argv)
        with mock.patch.object(self.app, "_command", side_effect=fail_verification):
            done = self.approve(doc)
        self.assertEqual("failed", done["state"])
        self.assertEqual([1, 0, 0, 7], [c["exit_code"] for c in done["checks"]])
        self.assertIn("Post-patch verification failed", done["error"])
        self.assertIn("INJECTED verification failure", done["checks"][-1]["stdout"])
        work = self.data / "runs" / doc["id"]
        self.assertEqual(done, json.loads((work / "evidence.json").read_text()))
        self.assertIn("exit_code=7", (work / "verification.log").read_text())

    def test_injected_command_timeout_is_recorded(self):
        doc = self.create()
        work = self.data / "runs" / doc["id"]
        work.mkdir()
        with mock.patch.object(handoff.subprocess, "run", side_effect=subprocess.TimeoutExpired(["node"], 15, output="partial output")):
            result = self.app._command(doc["id"], work, "timeout-injection", ["node"])
        self.assertEqual(124, result["exit_code"])
        self.assertIn("partial output", result["stdout"])
        self.assertIn("15-second", result["stderr"])
        self.assertEqual([result], self.app.get(doc["id"])["checks"])
        self.assertTrue((work / "timeout-injection.log").exists())


class HttpTests(IsolatedApp):
    def setUp(self):
        super().setUp()
        self.server = handoff.ThreadingHTTPServer(("127.0.0.1", 0), handoff.Handler)
        self.server.app = self.app
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()
        super().tearDown()

    def request(self, method="GET", path="/api/health", body=None, headers=None):
        headers = dict(headers or {})
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        if method == "POST":
            headers.setdefault("Content-Type", "application/json")
            headers.setdefault("Idempotency-Key", "http-key-0001")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            data = json.loads(payload) if response.getheader("Content-Type", "").startswith("application/json") else payload
            return response.status, dict(response.getheaders()), data
        finally:
            connection.close()

    def assertHttpError(self, code, error, *args, **kwargs):
        status, _, data = self.request(*args, **kwargs)
        self.assertEqual(code, status, data)
        self.assertEqual(error, data["error"]["code"])

    def test_health_is_truthful_and_has_security_headers(self):
        status, headers, data = self.request()
        self.assertEqual(200, status)
        self.assertFalse(data["live_model"])
        self.assertFalse(data["rinx_host_integration"])
        self.assertEqual("reviewed-patch-replay", data["executor"])
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertEqual("nosniff", headers["X-Content-Type-Options"])
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_host_rejects_foreign_host_even_without_origin(self):
        self.assertHttpError(403, "host_rejected", headers={"Host": "attacker.example"})

    def test_origin_rejects_foreign_and_null_origin(self):
        for origin in ("https://attacker.example", "null", "http://localhost:1"):
            with self.subTest(origin=origin):
                self.assertHttpError(403, "origin_rejected", headers={"Origin": origin})

    def test_exact_loopback_host_and_origin_are_allowed(self):
        status, _, _ = self.request(headers={"Host": f"localhost:{self.port}", "Origin": f"http://localhost:{self.port}"})
        self.assertEqual(200, status)

    def test_json_content_type_required(self):
        self.assertHttpError(415, "json_required", "POST", "/api/tasks", b"{}", {"Content-Type": "text/plain"})

    def test_malformed_json_and_invalid_utf8(self):
        for body in (b"{broken", b"\xff"):
            with self.subTest(body=body):
                self.assertHttpError(400, "invalid_json", "POST", "/api/tasks", body)

    def test_empty_oversized_and_invalid_length_rejected(self):
        self.assertHttpError(413, "invalid_size", "POST", "/api/tasks", b"")
        self.assertHttpError(413, "invalid_size", "POST", "/api/tasks", b"x" * 16385)
        self.assertHttpError(400, "invalid_length", "POST", "/api/tasks", b"{}", {"Content-Length": "not-an-int"})

    def test_valid_json_but_wrong_root_shape_rejected(self):
        self.assertHttpError(400, "invalid_request", "POST", "/api/tasks", [])

    def test_invalid_key_and_unsupported_recipe_rejected(self):
        body = {"objective": "Persist todo checkboxes", "recipe": "todo-persistence-v1"}
        self.assertHttpError(400, "invalid_key", "POST", "/api/tasks", body, {"Idempotency-Key": "x"})
        self.assertHttpError(422, "unsupported_recipe", "POST", "/api/tasks", body | {"recipe": "arbitrary-command"})

    def test_http_create_retry_reject_and_evidence(self):
        body = {"objective": "Persist todo checkboxes", "recipe": "todo-persistence-v1"}
        status, _, first = self.request("POST", "/api/tasks", body)
        self.assertEqual(201, status)
        status, _, second = self.request("POST", "/api/tasks", body)
        self.assertEqual(200, status)
        self.assertEqual(first, second)
        status, _, rejected = self.request("POST", f'/api/tasks/{first["id"]}/decision', self.decision(first, "reject"), {"Idempotency-Key": "http-reject-0001"})
        self.assertEqual(200, status)
        self.assertEqual("rejected", rejected["state"])
        self.assertNoExecution(rejected)
        status, _, evidence = self.request(path=f'/api/tasks/{first["id"]}/evidence')
        self.assertEqual(200, status)
        self.assertEqual(rejected, evidence)

    def test_malformed_decision_is_400_not_500(self):
        doc = self.create()
        self.assertHttpError(400, "invalid_decision", "POST", f'/api/tasks/{doc["id"]}/decision', self.decision(doc) | {"decision": []})

    def test_preview_requires_pass_and_arbitrary_paths_are_not_served(self):
        doc = self.create()
        self.assertHttpError(409, "preview_unavailable", path=f'/preview/{doc["id"]}/index.html')
        for path in ("/app.py", "/../app.py", "/fixture/store.test.mjs", "/var/tasks.sqlite3", f'/preview/{doc["id"]}/../../app.py'):
            with self.subTest(path=path):
                self.assertHttpError(404, "not_found", path=path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
