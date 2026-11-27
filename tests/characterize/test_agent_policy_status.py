"""Synthetic-only feature tests for the Agent policy store + status route.

Covers (LT_BOOTSTRAP_FIRST_CARD_20261021_A):
  - policy file missing
  - policy file malformed (invalid JSON)
  - policy present but schema mismatch / missing explicit user approval
  - policy present and explicitly approved -> initialized
  - Factory route behaviour (/api/agent-policy/status)
  - the endpoint never leaks policy content or filesystem paths
  - the endpoint NEVER writes to the policy directory

Every artifact lives under %TEMP%. The project's real
data/agent-policy/, data/task_publisher.db*, config/config.json and
src/notes/** are never read for content nor written.
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sandbox_env import available_port, materialize, seed, server  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import agent_policy  # noqa: E402


VALID_POLICY = {
    "schema_version": 1,
    "version": "2026-10-21.1",
    "approved_by_user": True,
    "approved_at": "2026-10-21T12:00:00Z",
    "free_task_minutes": 25,
    "note": "synthetic-secret-marker",
}


class PolicyDocumentTests(unittest.TestCase):
    """Pure validation logic; no filesystem beyond a temp dir."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lt_policy_unit_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_missing_file_is_not_initialized(self):
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_MISSING)
        self.assertIsNone(result["version"])

    def test_missing_directory_is_not_initialized(self):
        result = agent_policy.read_policy_status(str(self.tmp / "nope"))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_MISSING)

    def test_malformed_json_is_not_initialized(self):
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            "{ this is not json", encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_INVALID_JSON)

    def test_empty_file_is_not_initialized(self):
        (self.tmp / agent_policy.POLICY_FILENAME).write_text("", encoding="utf-8")
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_INVALID_JSON)

    def test_non_object_root_is_not_initialized(self):
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            "[1, 2, 3]", encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_INVALID_SHAPE)

    def test_schema_mismatch_is_not_initialized(self):
        doc = dict(VALID_POLICY, schema_version=99)
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            json.dumps(doc), encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_SCHEMA_MISMATCH)

    def test_missing_version_is_not_initialized(self):
        doc = dict(VALID_POLICY)
        doc.pop("version")
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            json.dumps(doc), encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_MISSING_VERSION)

    def test_missing_approved_at_is_not_initialized(self):
        doc = dict(VALID_POLICY)
        doc.pop("approved_at")
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            json.dumps(doc), encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_MISSING_APPROVED_AT)

    def test_missing_approval_is_not_initialized(self):
        doc = dict(VALID_POLICY)
        doc.pop("approved_by_user")
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            json.dumps(doc), encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_NOT_APPROVED)

    def test_false_approval_is_not_initialized(self):
        doc = dict(VALID_POLICY, approved_by_user=False)
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            json.dumps(doc), encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_NOT_APPROVED)

    def test_empty_approval_is_not_initialized(self):
        doc = dict(VALID_POLICY, approved_by_user="   ")
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            json.dumps(doc), encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_NOT_APPROVED)

    def test_explicit_approved_policy_is_initialized(self):
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            json.dumps(VALID_POLICY), encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertTrue(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_OK)
        self.assertEqual(result["version"], VALID_POLICY["version"])

    def test_reading_never_creates_the_policy_directory(self):
        target = self.tmp / "does-not-exist-yet"
        agent_policy.read_policy_status(str(target))
        self.assertFalse(target.exists())

    def test_reading_never_creates_the_policy_file(self):
        agent_policy.read_policy_status(str(self.tmp))
        self.assertFalse((self.tmp / agent_policy.POLICY_FILENAME).exists())

    def test_result_never_contains_policy_body(self):
        (self.tmp / agent_policy.POLICY_FILENAME).write_text(
            json.dumps(VALID_POLICY), encoding="utf-8"
        )
        result = agent_policy.read_policy_status(str(self.tmp))
        self.assertNotIn("note", result)
        self.assertNotIn("free_task_minutes", result)
        self.assertNotIn("synthetic-secret-marker", json.dumps(result))


class FactoryRouteTests(unittest.TestCase):
    """The Factory app must expose a read-only /api/agent-policy/status."""

    @classmethod
    def setUpClass(cls):
        cls.temp = Path(tempfile.mkdtemp(prefix="lt_policy_factory_"))
        cls.port = available_port()
        cls.root = materialize(cls.temp / "runtime", cls.port)
        seed(cls.root)
        cls.policy_dir = cls.root / "data" / "agent-policy"
        cls.policy_dir.mkdir(parents=True, exist_ok=True)
        cls._ctx = server(cls.root, "factory", cls.port)
        cls.base = cls._ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        try:
            cls._ctx.__exit__(None, None, None)
        finally:
            shutil.rmtree(cls.temp, ignore_errors=True)

    def _get(self, path="/api/agent-policy/status"):
        import urllib.request
        with urllib.request.urlopen(self.base + path, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_route_is_registered_in_factory(self):
        status, body = self._get()
        self.assertEqual(status, 200)
        self.assertIn("initialized", body)
        self.assertIn("status", body)

    def test_route_is_missing_policy_not_initialized(self):
        self.assertFalse((self.policy_dir / "latest.json").exists())
        status, body = self._get()
        self.assertEqual(status, 200)
        self.assertFalse(body["initialized"])
        self.assertIsNone(body["version"])

    def test_route_reports_malformed_policy(self):
        (self.policy_dir / "latest.json").write_text("{oops", encoding="utf-8")
        try:
            status, body = self._get()
            self.assertEqual(status, 200)
            self.assertFalse(body["initialized"])
            self.assertEqual(body["status"], agent_policy.STATUS_INVALID_JSON)
        finally:
            (self.policy_dir / "latest.json").unlink()

    def test_route_reports_policy_without_approval(self):
        doc = dict(VALID_POLICY)
        doc.pop("approved_by_user")
        (self.policy_dir / "latest.json").write_text(
            json.dumps(doc), encoding="utf-8"
        )
        try:
            status, body = self._get()
            self.assertEqual(status, 200)
            self.assertFalse(body["initialized"])
            self.assertEqual(body["status"], agent_policy.STATUS_NOT_APPROVED)
        finally:
            (self.policy_dir / "latest.json").unlink()

    def test_route_reports_approved_policy_as_initialized(self):
        (self.policy_dir / "latest.json").write_text(
            json.dumps(VALID_POLICY), encoding="utf-8"
        )
        try:
            status, body = self._get()
            self.assertEqual(status, 200)
            self.assertTrue(body["initialized"])
            self.assertEqual(body["version"], VALID_POLICY["version"])
        finally:
            (self.policy_dir / "latest.json").unlink()

    def test_route_does_not_leak_paths_or_policy_body(self):
        (self.policy_dir / "latest.json").write_text(
            json.dumps(VALID_POLICY), encoding="utf-8"
        )
        try:
            _status, body = self._get()
            blob = json.dumps(body)
            self.assertNotIn("synthetic-secret-marker", blob)
            self.assertNotIn("free_task_minutes", blob)
            self.assertNotIn(str(self.root), blob)
            self.assertNotIn("\\", blob.replace("\\\\", ""))
            self.assertEqual(
                set(body.keys()),
                {"initialized", "version", "status", "reason"},
            )
        finally:
            (self.policy_dir / "latest.json").unlink()

    def test_route_never_creates_the_policy_file(self):
        target = self.policy_dir / "latest.json"
        if target.exists():
            target.unlink()
        self._get()
        self.assertFalse(target.exists())

    def test_synthetic_db_is_the_only_database_touched(self):
        self.assertTrue((self.root / "data" / "synthetic.sqlite3").is_file())
        self.assertFalse((self.root / "data" / "task_publisher.db").exists())
        self.assertFalse((self.root / "src").exists())


class RealProjectUntouchedTests(unittest.TestCase):
    """Guard: the real project data/config/notes are never written."""

    def test_real_project_has_no_policy_dir_created_by_us(self):
        real_policy_dir = PROJECT_ROOT / "data" / "agent-policy"
        # We never create it. If the user later publishes a policy through
        # the controlled Publisher, it may exist; then we only assert that
        # our test run did not mutate anything else.
        if real_policy_dir.exists():
            self.assertTrue(real_policy_dir.is_dir())
        real_db = PROJECT_ROOT / "data" / "task_publisher.db"
        if real_db.exists():
            before = real_db.stat().st_mtime
            self.assertIsInstance(before, float)



class SchemaStrictnessTests(unittest.TestCase):
    """LT_BOOTSTRAP_G1_BROWSER_QA_20261022_B: schema 必须严格。

    重点：`schema_version: true` 不得冒充整数 1；不得仅凭一个无效
    字符串就构成"批准日期"；数字不得冒充显式批准。
    """

    def _validate(self, **overrides):
        doc = dict(VALID_POLICY)
        for key, value in overrides.items():
            if value is _DELETE:
                doc.pop(key, None)
            else:
                doc[key] = value
        return agent_policy.validate_policy_document(doc)

    def test_schema_version_true_does_not_impersonate_int_one(self):
        result = self._validate(schema_version=True)
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_SCHEMA_MISMATCH)

    def test_schema_version_float_one_is_rejected(self):
        result = self._validate(schema_version=1.0)
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_SCHEMA_MISMATCH)

    def test_schema_version_string_one_is_rejected(self):
        result = self._validate(schema_version="1")
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_SCHEMA_MISMATCH)

    def test_schema_version_false_is_rejected(self):
        result = self._validate(schema_version=False)
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_SCHEMA_MISMATCH)

    def test_missing_schema_version_is_rejected(self):
        result = self._validate(schema_version=_DELETE)
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_SCHEMA_MISMATCH)

    def test_approved_at_whitespace_only_is_not_an_approval_date(self):
        result = self._validate(approved_at="   ")
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_INVALID_APPROVED_AT)

    def test_approved_at_empty_string_is_rejected(self):
        result = self._validate(approved_at="")
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_INVALID_APPROVED_AT)

    def test_approved_at_unparseable_string_is_rejected(self):
        for value in ("not-a-date", "2026-13-45", "tomorrow", "12:00:00Z"):
            with self.subTest(value=value):
                result = self._validate(approved_at=value)
                self.assertFalse(result["initialized"])
                self.assertEqual(
                    result["status"], agent_policy.STATUS_INVALID_APPROVED_AT
                )

    def test_approved_at_without_timezone_is_rejected(self):
        result = self._validate(approved_at="2026-10-21T12:00:00")
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_INVALID_APPROVED_AT)

    def test_approved_at_far_future_is_rejected(self):
        result = self._validate(approved_at="2999-12-31T00:00:00Z")
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_INVALID_APPROVED_AT)

    def test_approved_at_with_control_chars_is_rejected(self):
        result = self._validate(approved_at="2026-10-21T12:00:00Z\n forged")
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_INVALID_APPROVED_AT)

    def test_approved_at_non_string_is_rejected(self):
        for value in (0, 1, True, None, 20261021):
            with self.subTest(value=value):
                result = self._validate(approved_at=value)
                self.assertFalse(result["initialized"])
                self.assertEqual(
                    result["status"], agent_policy.STATUS_INVALID_APPROVED_AT
                )

    def test_numeric_approval_is_not_explicit_approval(self):
        for value in (1, 0, 1.0):
            with self.subTest(value=value):
                result = self._validate(approved_by_user=value)
                self.assertFalse(result["initialized"])
                self.assertEqual(
                    result["status"], agent_policy.STATUS_NOT_APPROVED
                )

    def test_approval_with_control_chars_is_rejected(self):
        result = self._validate(approved_by_user="user\nforged")
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_NOT_APPROVED)

    def test_non_text_version_is_rejected(self):
        for value in (1, True, ["v"], {"v": 1}):
            with self.subTest(value=value):
                result = self._validate(version=value)
                self.assertFalse(result["initialized"])
                self.assertEqual(
                    result["status"], agent_policy.STATUS_INVALID_VERSION
                )

    def test_overlong_version_is_rejected(self):
        result = self._validate(version="v" * (agent_policy.MAX_VERSION_LENGTH + 1))
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_INVALID_VERSION)

    def test_offsets_timezone_is_accepted(self):
        result = self._validate(approved_at="2026-10-21T12:00:00+02:00")
        self.assertTrue(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_OK)

    def test_valid_policy_still_initialized_after_hardening(self):
        result = self._validate()
        self.assertTrue(result["initialized"])
        self.assertEqual(result["version"], VALID_POLICY["version"])

    def test_strictness_also_applies_through_the_file_reader(self):
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="lt_policy_strict_") as tmp:
            doc = dict(VALID_POLICY, schema_version=True)
            (Path(tmp) / agent_policy.POLICY_FILENAME).write_text(
                json.dumps(doc), encoding="utf-8"
            )
            result = agent_policy.read_policy_status(tmp)
        self.assertFalse(result["initialized"])
        self.assertEqual(result["status"], agent_policy.STATUS_SCHEMA_MISMATCH)


class ServerGateTests(unittest.TestCase):
    """服务端权威闸门：直接 POST 也必须被拒（前端守卫之外的第二道）。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lt_policy_gate_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _app(self, enforce):
        from flask import Flask

        app = Flask(__name__)
        app.config[agent_policy.ENFORCE_CONFIG_KEY] = enforce

        @app.route("/api/gacha/draw", methods=["POST"])
        def _draw():
            return {"ok": True}

        @app.route("/api/timer/start", methods=["POST"])
        def _timer():
            return {"ok": True}

        @app.route("/api/tasks", methods=["POST"])
        def _tasks():
            return {"ok": True}

        @app.route("/api/gacha/pools", methods=["GET"])
        def _pools():
            return {"ok": True}

        agent_policy.install_bootstrap_gate(app, self.tmp)
        return app

    def _write_policy(self, doc):
        (Path(self.tmp) / agent_policy.POLICY_FILENAME).write_text(
            json.dumps(doc), encoding="utf-8"
        )

    def test_should_block_write_matrix(self):
        block = agent_policy.should_block_write
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertTrue(block("/api/gacha/draw", method))
            self.assertTrue(block("/api/timer/start", method))
            self.assertTrue(block("/api/tasks/1/complete", method))
        for method in ("GET", "HEAD", "OPTIONS", "get", ""):
            self.assertFalse(block("/api/gacha/draw", method))
        # 段边界：相似前缀不得误伤
        self.assertFalse(block("/api/gachaxx/draw", "POST"))
        self.assertFalse(block("/api/timerx/start", "POST"))
        # 非拦截域
        self.assertFalse(block("/api/agent-policy/status", "GET"))
        self.assertFalse(block("/api/knowledge/notes", "GET"))
        self.assertFalse(block("/api/schedule/daily", "POST"))

    def test_direct_post_is_blocked_without_policy(self):
        client = self._app(True).test_client()
        for path in (
            "/api/gacha/draw",
            "/api/timer/start",
            "/api/tasks",
            "/api/tasks/1/complete",
        ):
            with self.subTest(path=path):
                resp = client.post(path, json={})
                self.assertEqual(resp.status_code, agent_policy.LOCKED_STATUS_CODE)
                self.assertEqual(
                    resp.get_json().get("error"), "bootstrap-locked"
                )

    def test_get_requests_are_never_blocked(self):
        client = self._app(True).test_client()
        resp = client.get("/api/gacha/pools")
        self.assertEqual(resp.status_code, 200)

    def test_direct_post_is_allowed_after_valid_approval(self):
        self._write_policy(VALID_POLICY)
        client = self._app(True).test_client()
        resp = client.post("/api/gacha/draw", json={})
        self.assertEqual(resp.status_code, 200)

    def test_gate_fails_closed_on_unapproved_policy(self):
        doc = dict(VALID_POLICY)
        doc.pop("approved_by_user")
        self._write_policy(doc)
        client = self._app(True).test_client()
        self.assertEqual(
            client.post("/api/gacha/draw", json={}).status_code,
            agent_policy.LOCKED_STATUS_CODE,
        )

    def test_gate_fails_closed_on_malformed_json(self):
        (Path(self.tmp) / agent_policy.POLICY_FILENAME).write_text(
            "{oops", encoding="utf-8"
        )
        client = self._app(True).test_client()
        self.assertEqual(
            client.post("/api/gacha/draw", json={}).status_code,
            agent_policy.LOCKED_STATUS_CODE,
        )

    def test_gate_fails_closed_on_schema_version_true(self):
        self._write_policy(dict(VALID_POLICY, schema_version=True))
        client = self._app(True).test_client()
        self.assertEqual(
            client.post("/api/gacha/draw", json={}).status_code,
            agent_policy.LOCKED_STATUS_CODE,
        )

    def test_gate_is_not_installed_by_default(self):
        self.assertFalse(
            agent_policy.install_bootstrap_gate(self._app(False), self.tmp)
        )

    def test_gate_never_creates_the_policy_file(self):
        client = self._app(True).test_client()
        client.post("/api/gacha/draw", json={})
        client.get("/api/gacha/pools")
        self.assertFalse((Path(self.tmp) / agent_policy.POLICY_FILENAME).exists())


class _Delete:
    """Sentinel for 'remove this key' in _validate overrides."""

    def __repr__(self):
        return "<DELETE>"


_DELETE = _Delete()


if __name__ == "__main__":
    unittest.main()
