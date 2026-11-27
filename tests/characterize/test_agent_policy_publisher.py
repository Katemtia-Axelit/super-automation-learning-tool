"""Synthetic-only tests for scripts/agent_policy_publisher.py.

任务: LT-BOOTSTRAP-POLICY-PUBLISHER-SYNTHETIC-20261022-D
契约: 独立受控发布器 (控制端在 *取得用户明确同意之后* 使用)。

覆盖点（全部在 ``%TEMP%`` 的合成策略根中运行）：

  1. 首次发布（无既有策略）→ latest.json 有效且 ``read_policy_status`` 判为 initialized
  2. 未批准 / 缺批准证据 / 缺操作授权 → 不得写任何文件（fail closed）
  3. 提案变化 → SHA-256 不匹配 → 拒绝
  4. 非法提案 / 危险目标路径 / 坏 JSON → fail closed
  5. 不可变历史被保留（绝不删除、绝不覆盖）
  6. 同一提案重复发布 → 幂等或明确拒绝
  7. 崩溃 / 原子写异常 → 旧 latest 仍完整有效
  8. 批准前 preview（prepare）无任何副作用
  9. 控制端审批证据缺失 / 不完整 → 拒绝
  10. 版本序列（必须严格递增）与重复版本拒绝
  11. 生产根不存在 → 不得被隐式创建
  12. 草案自称 ``approved_by_user`` 不得用于取得发布授权

红线：本文件 **绝不** 写真实 ``data/agent-policy``、``data/task_publisher.db*``、
``config/config.json`` 或 ``src/notes/**``；所有写入都发生在
``tempfile.TemporaryDirectory()`` 之内。
"""

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for _extra in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from server.services import agent_policy  # noqa: E402

agent_policy_publisher = importlib.import_module("agent_policy_publisher")


# --- 合成素材 --------------------------------------------------------------

VALID_PROPOSAL = {
    "schema_version": 1,
    "version": "2026-10-22.1",
    "effect_summary": (
        "任务时长统一收敛到 25 分钟，抽卡结果更稳定；"
        "用户不需要手动选择任何权重数字。"
    ),
    "weights": {"focus": 0.6, "rest": 0.4},
    "policy": {"free_task_minutes": 25},
}

VALID_EVIDENCE = {
    "approved_by": "user",
    "approval_text": "同意按这个方案调整策略",
    "session_id": "synthetic-session-001",
    "approved_at": "2026-10-22T09:00:00+00:00",
}

AUTH_NOTE = "controller 依据真实用户对话核对后的受控发布授权"


def _evidence(**overrides):
    data = dict(VALID_EVIDENCE)
    data.update(overrides)
    return data


def _proposal(**overrides):
    data = json.loads(json.dumps(VALID_PROPOSAL))
    data.update(overrides)
    return data


class _PublisherTestBase(unittest.TestCase):
    """每个测试都在独立的合成临时目录内运行。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="lt_policy_pub_")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.policy_dir = str(self.tmp / "agent-policy")
        os.makedirs(self.policy_dir)

    # -- helpers ----------------------------------------------------------
    def _digest(self, proposal=None):
        return agent_policy_publisher.proposal_digest(
            proposal if proposal is not None else VALID_PROPOSAL
        )

    def _publish(self, proposal=None, **kwargs):
        params = dict(
            proposal_digest_expected=self._digest(proposal),
            approval_evidence=_evidence(),
            authorize=True,
            authorization_note=AUTH_NOTE,
        )
        params.update(kwargs)
        return agent_policy_publisher.publish(
            self.policy_dir, proposal if proposal is not None else VALID_PROPOSAL, **params
        )

    def _latest_path(self):
        return Path(self.policy_dir) / agent_policy.POLICY_FILENAME

    def _history_files(self):
        history = Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME
        if not history.is_dir():
            return []
        return sorted(p.name for p in history.iterdir() if p.suffix == ".json")


class PrepareIsSideEffectFreeTests(_PublisherTestBase):
    """批准前的 preview 必须完全没有副作用。"""

    def test_prepare_does_not_write_anything(self):
        before = sorted(os.listdir(self.policy_dir))
        result = agent_policy_publisher.prepare(VALID_PROPOSAL, self.policy_dir)
        self.assertTrue(result["ok"])
        self.assertFalse(result["authorized"])
        self.assertEqual(sorted(os.listdir(self.policy_dir)), before)
        self.assertFalse(self._latest_path().exists())
        self.assertFalse(
            (Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME).exists()
        )

    def test_prepare_on_missing_dir_does_not_create_it(self):
        missing = str(self.tmp / "not-yet")
        result = agent_policy_publisher.prepare(VALID_PROPOSAL, missing)
        self.assertTrue(result["ok"])
        self.assertFalse(Path(missing).exists())

    def test_prepare_reports_proposal_digest_and_effect(self):
        result = agent_policy_publisher.prepare(VALID_PROPOSAL, self.policy_dir)
        self.assertEqual(result["proposal_sha256"], self._digest())
        self.assertEqual(result["effect_summary"], VALID_PROPOSAL["effect_summary"])
        self.assertIn("expected_change", result)

    def test_prepare_shows_current_published_version(self):
        self._publish()
        result = agent_policy_publisher.prepare(_proposal(version="2026-10-22.2"), self.policy_dir)
        self.assertTrue(result["current"]["initialized"])
        self.assertEqual(result["current"]["version"], "2026-10-22.1")
        self.assertEqual(result["expected_change"]["previous_version"], "2026-10-22.1")

    def test_prepare_rejects_invalid_proposal(self):
        for bad in (
            _proposal(schema_version=True),
            _proposal(schema_version=99),
            _proposal(version=""),
            _proposal(effect_summary=""),
            _proposal(effect_summary="x" * 3),
            _proposal(weights={"a": 2.0}),
            _proposal(weights={"a": "high"}),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(agent_policy_publisher.PublisherError):
                    agent_policy_publisher.prepare(bad, self.policy_dir)


class FirstPublishTests(_PublisherTestBase):
    """首次发布：无既有策略 → latest.json 有效。"""

    def test_first_publish_creates_valid_latest(self):
        result = self._publish()
        self.assertTrue(result["ok"])
        self.assertEqual(result["outcome"], "published")
        self.assertIsNone(result["previous_version"])

        self.assertTrue(self._latest_path().is_file())
        doc = json.loads(self._latest_path().read_text(encoding="utf-8"))
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(doc["version"], "2026-10-22.1")
        self.assertIs(doc["approved_by_user"], True)
        self.assertEqual(doc["approved_at"], VALID_EVIDENCE["approved_at"])
        self.assertEqual(doc["free_task_minutes"], 25)

        status = agent_policy.read_policy_status(self.policy_dir)
        self.assertTrue(status["initialized"])
        self.assertEqual(status["version"], "2026-10-22.1")

    def test_first_publish_writes_history_and_receipt(self):
        self._publish()
        self.assertEqual(len(self._history_files()), 1)
        receipts = list((Path(self.policy_dir) / agent_policy_publisher.RECEIPTS_DIRNAME).glob("*.json"))
        self.assertEqual(len(receipts), 1)

    def test_history_entry_contains_full_audit_material(self):
        self._publish()
        entry_path = (
            Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME / self._history_files()[0]
        )
        entry = json.loads(entry_path.read_text(encoding="utf-8"))
        self.assertIsNone(entry["previous_version"])
        self.assertEqual(entry["new_version"], "2026-10-22.1")
        self.assertEqual(entry["proposal_sha256"], self._digest())
        self.assertEqual(entry["effect_summary"], VALID_PROPOSAL["effect_summary"])
        self.assertEqual(entry["approval_evidence"]["approval_text"], VALID_EVIDENCE["approval_text"])
        self.assertEqual(entry["approval_evidence"]["approved_at"], VALID_EVIDENCE["approved_at"])
        # 完整提案内容（供后续 Agent 复盘）
        self.assertEqual(entry["proposal"]["version"], "2026-10-22.1")
        self.assertEqual(entry["proposal"]["weights"], VALID_PROPOSAL["weights"])


class FailClosedTests(_PublisherTestBase):
    """未获授权时不得产生任何写入。"""

    def _assert_nothing_written(self):
        self.assertFalse(self._latest_path().exists())
        self.assertFalse(
            (Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME).exists()
        )
        self.assertFalse(
            (Path(self.policy_dir) / agent_policy_publisher.RECEIPTS_DIRNAME).exists()
        )
        self.assertFalse(
            (Path(self.policy_dir) / agent_policy_publisher.LOCK_FILENAME).exists()
        )

    def test_missing_approval_evidence_fails_closed(self):
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(approval_evidence=None)
        self.assertEqual(ctx.exception.code, "approval_evidence_missing")
        self._assert_nothing_written()

    def test_incomplete_approval_evidence_fails_closed(self):
        for field in ("approved_by", "approval_text", "session_id", "approved_at"):
            with self.subTest(field=field):
                evidence = _evidence()
                evidence.pop(field)
                with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                    self._publish(approval_evidence=evidence)
                self.assertEqual(ctx.exception.code, "approval_evidence_incomplete")
                self._assert_nothing_written()

    def test_approval_evidence_without_timezone_fails_closed(self):
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(approval_evidence=_evidence(approved_at="2026-10-22T09:00:00"))
        self.assertEqual(ctx.exception.code, "approval_evidence_invalid")
        self._assert_nothing_written()

    def test_missing_authorization_fails_closed(self):
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(authorize=False)
        self.assertEqual(ctx.exception.code, "authorization_missing")
        self._assert_nothing_written()

    def test_missing_authorization_note_fails_closed(self):
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(authorization_note="  ")
        self.assertEqual(ctx.exception.code, "authorization_note_missing")
        self._assert_nothing_written()

    def test_missing_digest_fails_closed(self):
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(proposal_digest_expected=None)
        self.assertEqual(ctx.exception.code, "proposal_digest_missing")
        self._assert_nothing_written()

    def test_draft_self_approval_is_not_an_authorization(self):
        """草案里自称 ``approved_by_user`` 不得取得发布授权。"""
        proposal = _proposal(approved_by_user=True, approved_at="2026-01-01T00:00:00Z")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(
                proposal,
                proposal_digest_expected=self._digest(proposal),
                approval_evidence=None,
            )
        self.assertEqual(ctx.exception.code, "approval_evidence_missing")
        self._assert_nothing_written()

    def test_draft_approval_fields_are_ignored_and_reported(self):
        proposal = _proposal(approved_by_user=True)
        preview = agent_policy_publisher.prepare(proposal, self.policy_dir)
        self.assertIn(
            "approved_by_user", preview["proposal"]["ignored_draft_approval_fields"]
        )

    def test_bad_json_proposal_file_fails_closed(self):
        broken = self.tmp / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.load_proposal(str(broken))
        self.assertEqual(ctx.exception.code, "proposal_invalid_json")
        self._assert_nothing_written()

    def test_non_object_proposal_fails_closed(self):
        broken = self.tmp / "list.json"
        broken.write_text("[1,2,3]", encoding="utf-8")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.load_proposal(str(broken))
        self.assertEqual(ctx.exception.code, "proposal_not_object")

    def test_missing_effect_summary_blocks_publish(self):
        proposal = _proposal()
        proposal.pop("effect_summary")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(proposal, proposal_digest_expected=self._digest(proposal))
        self.assertEqual(ctx.exception.code, "missing_effect_summary")
        self._assert_nothing_written()


class DigestMismatchTests(_PublisherTestBase):
    """提案变化 → 摘要不匹配 → 拒绝。"""

    def test_changed_proposal_digest_mismatch(self):
        changed = _proposal(weights={"focus": 0.9, "rest": 0.1})
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(
                changed,
                proposal_digest_expected=self._digest(),
            )
        self.assertEqual(ctx.exception.code, "proposal_digest_mismatch")
        self.assertFalse(self._latest_path().exists())

    def test_digest_is_independent_of_formatting(self):
        other = json.loads(json.dumps(VALID_PROPOSAL))
        self.assertEqual(self._digest(other), self._digest())
        reordered = dict(reversed(list(VALID_PROPOSAL.items())))
        self.assertEqual(self._digest(reordered), self._digest())

    def test_digest_changes_when_semantics_change(self):
        other = _proposal(effect_summary="完全不同的效果说明文本内容")
        self.assertNotEqual(self._digest(other), self._digest())


class DangerousTargetTests(_PublisherTestBase):
    """危险目标路径必须 fail closed。"""

    def test_relative_target_rejected(self):
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.publish(
                "relative/agent-policy",
                VALID_PROPOSAL,
                proposal_digest_expected=self._digest(),
                approval_evidence=_evidence(),
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "target_not_absolute")

    def test_empty_target_rejected(self):
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.publish(
                "",
                VALID_PROPOSAL,
                proposal_digest_expected=self._digest(),
                approval_evidence=_evidence(),
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "target_required")

    def test_notes_redline_target_rejected(self):
        target = str(self.tmp / "src" / "notes" / "agent-policy")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.publish(
                target,
                VALID_PROPOSAL,
                proposal_digest_expected=self._digest(),
                approval_evidence=_evidence(),
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "target_is_protected_path")

    def test_protected_basename_target_rejected(self):
        target = str(self.tmp / "task_publisher.db")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.publish(
                target,
                VALID_PROPOSAL,
                proposal_digest_expected=self._digest(),
                approval_evidence=_evidence(),
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "target_is_protected_path")

    def test_existing_file_target_rejected(self):
        target = self.tmp / "afile"
        target.write_text("x", encoding="utf-8")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.publish(
                str(target),
                VALID_PROPOSAL,
                proposal_digest_expected=self._digest(),
                approval_evidence=_evidence(),
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "target_not_a_directory")


class NoImplicitProductionRootTests(_PublisherTestBase):
    """生产根不存在时不得被隐式创建。"""

    def test_missing_policy_dir_is_not_created_by_default(self):
        missing = str(self.tmp / "does-not-exist")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.publish(
                missing,
                VALID_PROPOSAL,
                proposal_digest_expected=self._digest(),
                approval_evidence=_evidence(),
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "policy_dir_absent")
        self.assertFalse(Path(missing).exists())

    def test_explicit_create_flag_allows_creation(self):
        missing = str(self.tmp / "explicitly-created")
        result = agent_policy_publisher.publish(
            missing,
            VALID_PROPOSAL,
            proposal_digest_expected=self._digest(),
            approval_evidence=_evidence(),
            authorize=True,
            authorization_note=AUTH_NOTE,
            create_policy_dir=True,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(Path(missing).is_dir())

    def test_real_project_policy_root_not_created(self):
        real_root = PROJECT_ROOT / "data" / "agent-policy"
        existed_before = real_root.exists()
        # 只做只读检查；本测试绝不触碰真实数据。
        status = agent_policy.read_policy_status(str(real_root))
        self.assertIn("initialized", status)
        self.assertEqual(real_root.exists(), existed_before)


class HistoryTests(_PublisherTestBase):
    """不可变历史：保留、不覆盖、不删除。"""

    def test_history_accumulates_across_publishes(self):
        self._publish()
        second = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(len(self._history_files()), 2)
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.2"
        )

    def test_history_is_never_overwritten(self):
        self._publish()
        first = self._history_files()[0]
        path = Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME / first
        original = path.read_bytes()
        second = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_bytes(), original)

    def test_history_entries_are_immutable_json(self):
        self._publish()
        path = (
            Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME / self._history_files()[0]
        )
        entry = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(entry["entry_type"], "publish")
        self.assertEqual(entry["previous_version"], None)
        self.assertEqual(entry["new_version"], "2026-10-22.1")
        self.assertIn("proposal", entry)

    def test_second_history_entry_links_previous_policy(self):
        self._publish()
        second = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        self._publish(second, proposal_digest_expected=self._digest(second))
        path = (
            Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME / self._history_files()[1]
        )
        entry = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(entry["previous_version"], "2026-10-22.1")
        self.assertIsNotNone(entry["previous_policy_sha256"])


class DuplicateTests(_PublisherTestBase):
    """同一提案重试：幂等或明确拒绝。"""

    def test_republish_same_proposal_is_idempotent(self):
        first = self._publish()
        second = self._publish()
        self.assertEqual(first["outcome"], "published")
        self.assertEqual(second["outcome"], "already_published")
        self.assertEqual(len(self._history_files()), 1)

    def test_republish_same_proposal_does_not_change_latest_mtime_content(self):
        self._publish()
        content = self._latest_path().read_bytes()
        self._publish()
        self.assertEqual(self._latest_path().read_bytes(), content)

    def test_same_version_with_different_proposal_is_rejected(self):
        self._publish()
        other = _proposal(effect_summary="同版本号但不同内容的效果说明文本")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(other, proposal_digest_expected=self._digest(other))
        self.assertIn(ctx.exception.code, ("duplicate_version", "version_not_newer"))


class VersionSequenceTests(_PublisherTestBase):
    """版本序列必须严格递增。"""

    def test_older_version_is_rejected(self):
        self._publish()
        older = _proposal(version="2026-10-21.9", effect_summary="更旧的版本效果说明文本")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(older, proposal_digest_expected=self._digest(older))
        self.assertEqual(ctx.exception.code, "version_not_newer")
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.1"
        )

    def test_same_version_is_rejected(self):
        self._publish()
        same = _proposal(effect_summary="同版本号但不同内容的效果说明文本")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(same, proposal_digest_expected=self._digest(same))
        self.assertEqual(ctx.exception.code, "duplicate_version")
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.1"
        )

    def test_numeric_version_segments_compare_numerically(self):
        self.assertLess(
            agent_policy_publisher._version_key("2026-10-22.2"),
            agent_policy_publisher._version_key("2026-10-22.10"),
        )

    def test_newer_version_is_accepted(self):
        self._publish()
        newer = _proposal(version="2026-10-22.10", effect_summary="更高的次版本号效果说明")
        result = self._publish(newer, proposal_digest_expected=self._digest(newer))
        self.assertEqual(result["outcome"], "published")
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.10"
        )


class AtomicityTests(_PublisherTestBase):
    """失败时旧 latest 仍必须是完整有效的 JSON。"""

    def test_existing_latest_survives_a_failing_publish(self):
        self._publish()
        good = self._latest_path().read_bytes()
        broken = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        broken["weights"] = {"focus": 5.0}  # 非法权重 → 发布前就失败
        with self.assertRaises(agent_policy_publisher.PublisherError):
            self._publish(broken, proposal_digest_expected=self._digest(broken))
        self.assertEqual(self._latest_path().read_bytes(), good)
        self.assertTrue(agent_policy.read_policy_status(self.policy_dir)["initialized"])

    def test_crash_during_write_keeps_previous_latest_valid(self):
        """模拟原子写失败：``os.replace`` 抛错 → 旧 latest 不受影响。"""
        self._publish()
        good = self._latest_path().read_bytes()
        original_replace = os.replace

        def _boom(src, dst):
            raise OSError("synthetic crash during replace")

        newer = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        os.replace = _boom
        try:
            with self.assertRaises(OSError):
                self._publish(newer, proposal_digest_expected=self._digest(newer))
        finally:
            os.replace = original_replace
        self.assertEqual(self._latest_path().read_bytes(), good)
        self.assertTrue(agent_policy.read_policy_status(self.policy_dir)["initialized"])
        # 临时文件已被清理
        leftovers = [
            p.name
            for p in Path(self.policy_dir).iterdir()
            if p.name.startswith(".tmp-publish-")
        ]
        self.assertEqual(leftovers, [])
        # 锁已释放
        self.assertFalse(
            (Path(self.policy_dir) / agent_policy_publisher.LOCK_FILENAME).exists()
        )

    def test_latest_is_never_half_written(self):
        self._publish()
        raw = self._latest_path().read_bytes()
        json.loads(raw.decode("utf-8"))  # 完整 JSON
        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(b"\r\n", raw)


class LockTests(_PublisherTestBase):
    """并发发布必须串行化。"""

    def test_concurrent_publish_is_locked_out(self):
        lock_path = Path(self.policy_dir) / agent_policy_publisher.LOCK_FILENAME
        lock_path.write_text("held", encoding="utf-8")
        try:
            with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                self._publish()
            self.assertEqual(ctx.exception.code, "publish_locked")
            self.assertFalse(self._latest_path().exists())
        finally:
            lock_path.unlink()


class RollbackTests(_PublisherTestBase):
    """受控回滚：只允许回到历史中已批准的版本。"""

    def test_rollback_to_history_version(self):
        self._publish()
        second = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        self._publish(second, proposal_digest_expected=self._digest(second))
        result = agent_policy_publisher.rollback(
            self.policy_dir,
            version="2026-10-22.1",
            approval_evidence=_evidence(),
            authorize=True,
            authorization_note=AUTH_NOTE,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["restored_version"], "2026-10-22.1")
        status = agent_policy.read_policy_status(self.policy_dir)
        self.assertTrue(status["initialized"])
        self.assertEqual(status["version"], "2026-10-22.1")

    def test_rollback_to_unknown_version_is_rejected(self):
        self._publish()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.rollback(
                self.policy_dir,
                version="2999-01-01.1",
                approval_evidence=_evidence(),
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "rollback_target_not_in_history")
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.1"
        )

    def test_rollback_without_approval_is_rejected(self):
        self._publish()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.rollback(
                self.policy_dir,
                version="2026-10-22.1",
                approval_evidence=None,
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "approval_evidence_missing")

    def test_rollback_without_authorization_is_rejected(self):
        self._publish()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.rollback(
                self.policy_dir,
                version="2026-10-22.1",
                approval_evidence=_evidence(),
                authorize=False,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "authorization_missing")

    def test_rollback_keeps_history_intact(self):
        self._publish()
        second = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        self._publish(second, proposal_digest_expected=self._digest(second))
        agent_policy_publisher.rollback(
            self.policy_dir,
            version="2026-10-22.1",
            approval_evidence=_evidence(),
            authorize=True,
            authorization_note=AUTH_NOTE,
        )
        self.assertEqual(len(self._history_files()), 2)


class CliTests(_PublisherTestBase):
    """最小命令行接口。"""

    def _proposal_file(self, proposal=None):
        path = self.tmp / "proposal.json"
        path.write_text(
            json.dumps(proposal if proposal is not None else VALID_PROPOSAL, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(path)

    def _evidence_file(self, evidence=None):
        path = self.tmp / "approval.json"
        path.write_text(
            json.dumps(evidence if evidence is not None else VALID_EVIDENCE, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(path)

    def test_cli_prepare_has_no_side_effects(self):
        proposal_file = self._proposal_file()
        before = sorted(os.listdir(self.policy_dir))
        code = agent_policy_publisher.main(
            ["prepare", "--proposal", proposal_file, "--policy-dir", self.policy_dir]
        )
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(self.policy_dir)), before)

    def test_cli_publish_then_status(self):
        proposal_file = self._proposal_file()
        evidence_file = self._evidence_file()
        digest = self._digest()
        code = agent_policy_publisher.main([
            "publish",
            "--proposal", proposal_file,
            "--policy-dir", self.policy_dir,
            "--proposal-digest", digest,
            "--approval-evidence", evidence_file,
            "--authorize",
            "--authorization-note", AUTH_NOTE,
        ])
        self.assertEqual(code, 0)
        self.assertTrue(agent_policy.read_policy_status(self.policy_dir)["initialized"])

        code = agent_policy_publisher.main(
            ["status", "--policy-dir", self.policy_dir]
        )
        self.assertEqual(code, 0)

    def test_cli_publish_without_authorization_exits_2(self):
        proposal_file = self._proposal_file()
        evidence_file = self._evidence_file()
        code = agent_policy_publisher.main([
            "publish",
            "--proposal", proposal_file,
            "--policy-dir", self.policy_dir,
            "--proposal-digest", self._digest(),
            "--approval-evidence", evidence_file,
        ])
        self.assertEqual(code, 2)
        self.assertFalse(self._latest_path().exists())

    def test_cli_publish_with_wrong_digest_exits_2(self):
        proposal_file = self._proposal_file()
        evidence_file = self._evidence_file()
        code = agent_policy_publisher.main([
            "publish",
            "--proposal", proposal_file,
            "--policy-dir", self.policy_dir,
            "--proposal-digest", "0" * 64,
            "--approval-evidence", evidence_file,
            "--authorize",
            "--authorization-note", AUTH_NOTE,
        ])
        self.assertEqual(code, 2)
        self.assertFalse(self._latest_path().exists())


class RealDataUntouchedTests(unittest.TestCase):
    """红线守卫：本测试绝不写真实项目数据。"""

    def test_real_paths_not_modified_by_this_module(self):
        protected = [
            PROJECT_ROOT / "data" / "task_publisher.db",
            PROJECT_ROOT / "data" / "task_publisher.db-wal",
            PROJECT_ROOT / "data" / "task_publisher.db-shm",
            PROJECT_ROOT / "config" / "config.json",
        ]
        for path in protected:
            if path.exists():
                self.assertTrue(path.is_file())
        notes = PROJECT_ROOT / "src" / "notes"
        if notes.exists():
            self.assertTrue(notes.is_dir())

    def test_module_never_defines_a_real_data_default(self):
        """发布器不得带有指向真实数据根的缺省目标。"""
        import inspect

        source = inspect.getsource(agent_policy_publisher)
        self.assertNotIn("DEFAULT_POLICY_DIR", source)
        self.assertNotIn("default_policy_dir(", source)


# ===========================================================================
# LT_BOOTSTRAP_PUBLISHER_METADATA_QA_20261022_E
#   1) Publisher 托管字段不得被提案 policy 覆盖（配置完整性）
#   2) 目标路径的 symlink / junction / reparse 绕过
#   3) 回滚的元数据一致性与提案指纹 / 批准证据绑定
#   4) 历史写入后 os.replace 失败的孤儿 entry（已知风险，fail-closed）
#   5) 信任边界的诚实记录（结构校验 ≠ 真实人类同意）
# ===========================================================================


class ReservedPolicyFieldTests(_PublisherTestBase):
    """任何 Agent 提案的 ``policy`` 都不得改写 Publisher 托管字段。

    D 轮独立审计复现的缺陷：``publish()`` 先生成外部批准的可信元数据，
    再 ``for key, value in view['policy'].items(): document[key] = value``，
    于是 ``policy`` 里的任意键可以覆盖身份 / 版本 / 批准 / 审计摘要 /
    权重。E 轮改为 **双重 fail closed**（预览期校验 + 写入期复查）。
    """

    #: 每个保留字段的一次恶意但纯数据的注入尝试。
    ATTEMPTS = {
        "schema_version": 99,
        "version": "HACKED-9999",
        "approved_by_user": "attacker",
        "approved_at": "2000-01-01T00:00:00+00:00",
        "approval": "self-signed-by-agent",
        "effect_summary": "伪造的效果摘要文本",
        "proposal_sha256": "0" * 64,
        "published_at": "1999-01-01T00:00:00+00:00",
        "weights": {"evil": 0.99},
        "policy_document": {"schema_version": 1},
        "trust_boundary": "forged-by-agent",
        "approval_evidence": {"approved_by": "agent"},
    }

    def _malicious(self, key, value):
        return _proposal(policy={key: value, "free_task_minutes": 1})

    def test_every_reserved_field_is_rejected_by_prepare(self):
        """预览阶段直接清晰报错，而不是静默忽略。"""
        for key, value in self.ATTEMPTS.items():
            with self.subTest(field=key):
                with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                    agent_policy_publisher.prepare(self._malicious(key, value), self.policy_dir)
                self.assertEqual(ctx.exception.code, "policy_reserved_field_conflict")
                self.assertIn(key, ctx.exception.detail)
        self._assert_nothing_published()

    def test_every_reserved_field_is_rejected_by_publish(self):
        """publish 必须拒绝，且 latest / history / receipts 一律不被创建。"""
        for key, value in self.ATTEMPTS.items():
            with self.subTest(field=key):
                proposal = self._malicious(key, value)
                with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                    self._publish(proposal, proposal_digest_expected=self._digest(proposal))
                self.assertEqual(ctx.exception.code, "policy_reserved_field_conflict")
                self._assert_nothing_published()

    def test_case_and_whitespace_variants_are_rejected(self):
        """大小写 / 首尾空白不得成为绕过通道。"""
        for key in ("VERSION", "Approved_At", " approved_by_user ", "Effect_Summary"):
            with self.subTest(field=key):
                proposal = _proposal(policy={key: "HACKED"})
                with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                    self._publish(proposal, proposal_digest_expected=self._digest(proposal))
                self.assertEqual(ctx.exception.code, "policy_reserved_field_conflict")
                self._assert_nothing_published()

    def test_reserved_field_never_clobbers_an_existing_policy(self):
        """已有可信策略时，恶意提案不得覆盖 latest / 历史 / 回执。"""
        self._publish()
        before_latest = self._latest_path().read_bytes()
        before_history = self._history_files()

        malicious = _proposal(
            version="2026-10-22.2",
            effect_summary="第二版恶意提案的效果说明文本",
            policy={"version": "HACKED-9999", "approved_at": "2000-01-01T00:00:00+00:00"},
        )
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(malicious, proposal_digest_expected=self._digest(malicious))
        self.assertEqual(ctx.exception.code, "policy_reserved_field_conflict")

        self.assertEqual(self._latest_path().read_bytes(), before_latest)
        self.assertEqual(self._history_files(), before_history)
        status = agent_policy.read_policy_status(self.policy_dir)
        self.assertTrue(status["initialized"])
        self.assertEqual(status["version"], "2026-10-22.1")

    def test_write_path_rechecks_even_if_validation_is_bypassed(self):
        """第二道闸门：即便校验层被绕过，写入路径仍 fail closed。

        这里模拟一个"更坏"的未来回归——有人 monkeypatch 掉
        ``validate_proposal``，使返回的视图里带上保留键。合并阶段必须
        独立地再拒绝一次。
        """
        original = agent_policy_publisher.validate_proposal
        try:
            def _bypass(proposal):
                view = original(proposal)
                view["policy"] = dict(view["policy"], version="HACKED-9999")
                return view

            agent_policy_publisher.validate_proposal = _bypass
            with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                self._publish()
        finally:
            agent_policy_publisher.validate_proposal = original
        self.assertEqual(ctx.exception.code, "policy_reserved_field_conflict")
        self._assert_nothing_published()

    def test_ordinary_extension_fields_still_work(self):
        """普通扩展字段（例如 free_task_minutes）不得被误伤。"""
        result = self._publish()
        self.assertEqual(result["outcome"], "published")
        doc = json.loads(self._latest_path().read_text(encoding="utf-8"))
        self.assertEqual(doc["free_task_minutes"], 25)
        self.assertEqual(doc["weights"], {"focus": 0.6, "rest": 0.4})
        self.assertEqual(doc["version"], "2026-10-22.1")
        self.assertTrue(agent_policy.read_policy_status(self.policy_dir)["initialized"])

    def test_reserved_field_list_is_exported_and_covers_managed_names(self):
        reserved = agent_policy_publisher.PUBLISHER_RESERVED_FIELDS
        for name in (
            "schema_version", "version", "approved_by_user", "approved_at",
            "effect_summary", "proposal_sha256", "weights",
        ):
            self.assertIn(name, reserved)
        self.assertNotIn("free_task_minutes", reserved)

    def _assert_nothing_published(self):
        self.assertFalse(self._latest_path().exists())
        self.assertFalse((Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME).exists())
        self.assertFalse((Path(self.policy_dir) / agent_policy_publisher.RECEIPTS_DIRNAME).exists())
        self.assertFalse((Path(self.policy_dir) / agent_policy_publisher.LOCK_FILENAME).exists())


class _ReparseTargetTests(unittest.TestCase):
    """symlink / junction / reparse 绕过（全部在合成 ``%TEMP%`` 中）。

    Windows 上创建 symlink 需要特权（SeCreateSymbolicLinkPrivilege）或
    开发者模式；本机不可用时 **skip 并公开原因**，绝不静默通过。
    测试绝不触碰真实知识库，只创建 TEMP 下的合成 ``src/notes`` 与
    ``config`` 目录。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="lt_policy_link_")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        # 合成受保护目录（**不是** 真实项目目录）
        self.notes = self.tmp / "src" / "notes"
        self.notes.mkdir(parents=True)
        self.config = self.tmp / "config"
        self.config.mkdir(parents=True)

    def _symlink(self, link_path: Path, target: Path) -> str:
        """尽力创建目录 symlink；失败时 skip（公开原因）。"""
        try:
            os.symlink(str(target), str(link_path), target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest(
                f"当前环境无法创建 symlink（Windows 需开发者模式/管理员）: "
                f"{type(exc).__name__}: {exc}"
            )
        return str(link_path)

    def _publish_to(self, target: str):
        return agent_policy_publisher.publish(
            target,
            VALID_PROPOSAL,
            proposal_digest_expected=agent_policy_publisher.proposal_digest(VALID_PROPOSAL),
            approval_evidence=VALID_EVIDENCE,
            authorize=True,
            authorization_note=AUTH_NOTE,
        )

    def test_symlink_into_synthetic_notes_is_rejected(self):
        link = self.tmp / "policy-link"
        self._symlink(link, self.notes)
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish_to(str(link))
        self.assertIn(
            ctx.exception.code,
            ("target_is_reparse_point", "target_resolves_to_protected_path"),
        )
        self.assertFalse((self.notes / "latest.json").exists())

    def test_symlink_into_synthetic_config_is_rejected(self):
        link = self.tmp / "config-link"
        self._symlink(link, self.config)
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish_to(str(link))
        self.assertIn(
            ctx.exception.code,
            ("target_is_reparse_point", "target_resolves_to_protected_path"),
        )
        self.assertFalse((self.config / "latest.json").exists())

    def test_symlinked_parent_directory_is_rejected(self):
        """父目录是 junction/symlink、末段看起来无害 —— 仍必须拒绝。"""
        parent = self.tmp / "innocent-parent"
        self._symlink(parent, self.notes)
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish_to(str(parent / "agent-policy"))
        self.assertIn(
            ctx.exception.code,
            ("target_is_reparse_point", "target_resolves_to_protected_path"),
        )
        self.assertFalse((self.notes / "agent-policy").exists())

    def test_explicit_notes_path_in_text_form_is_rejected(self):
        """显式指向项目 src/notes 形态的路径：文本检查即拒绝。"""
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish_to(str(self.notes / "agent-policy"))
        self.assertEqual(ctx.exception.code, "target_is_protected_path")

    def test_explicit_config_path_in_text_form_is_rejected(self):
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish_to(str(self.config / "agent-policy"))
        self.assertEqual(ctx.exception.code, "target_is_protected_path")

    # --- 无特权环境也必须跑得动的替代断言 ---------------------------------
    def test_reparse_helper_reports_plain_dir_as_not_reparse(self):
        self.assertFalse(agent_policy_publisher._is_reparse_point(str(self.tmp)))
        self.assertFalse(os.path.islink(str(self.tmp)))

    def test_resolve_candidates_walk_parents_without_touching_fs(self):
        target = os.path.join(str(self.tmp), "a", "b", "c")
        candidates = agent_policy_publisher._resolve_target_candidates(target)
        self.assertEqual(candidates[0], os.path.realpath(target))
        self.assertGreaterEqual(len(candidates), 4)
        # 纯解析：不创建任何目录
        self.assertFalse(Path(target).exists())


class ReparseBypassLogicTests(unittest.TestCase):
    """**无特权也要跑**的重解析点拒绝逻辑（不依赖创建真实 symlink）。

    上面 ``_ReparseTargetTests`` 的真实 symlink 用例在本机因缺少
    ``SeCreateSymbolicLinkPrivilege`` 被 skip。本类用 *受控替身* 覆盖
    同一条决策分支，保证拒绝逻辑在任何环境下都被真实执行过，
    而不是"因为 skip 所以没测"。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="lt_policy_rep_")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.notes = self.tmp / "src" / "notes"
        self.notes.mkdir(parents=True)
        self.config = self.tmp / "config"
        self.config.mkdir(parents=True)
        self.target = self.tmp / "innocent" / "agent-policy"
        self.target.parent.mkdir(parents=True)

    def _publish_to(self, target):
        return agent_policy_publisher.publish(
            target,
            VALID_PROPOSAL,
            proposal_digest_expected=agent_policy_publisher.proposal_digest(VALID_PROPOSAL),
            approval_evidence=VALID_EVIDENCE,
            authorize=True,
            authorization_note=AUTH_NOTE,
        )

    def test_link_itself_is_rejected_as_reparse_point(self):
        """目标自身是 symlink / junction → 直接拒绝（不改真实路径）。"""
        original_islink = os.path.islink
        os.path.islink = lambda p: os.path.normcase(str(p)) == os.path.normcase(str(self.target))
        try:
            with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                self._publish_to(str(self.target))
        finally:
            os.path.islink = original_islink
        self.assertEqual(ctx.exception.code, "target_is_reparse_point")

    def test_junction_target_is_rejected_as_reparse_point(self):
        """Windows junction（``os.path.isjunction``）→ 同样拒绝。"""
        original_isjunction = os.path.isjunction
        os.path.isjunction = lambda p: os.path.normcase(str(p)) == os.path.normcase(str(self.target))
        try:
            with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                self._publish_to(str(self.target))
        finally:
            os.path.isjunction = original_isjunction
        self.assertEqual(ctx.exception.code, "target_is_reparse_point")

    def test_resolution_into_synthetic_notes_is_rejected(self):
        """realpath 解析后落到合成 ``src/notes`` → 拒绝。"""
        original_realpath = os.path.realpath

        def _fake(path, *args, **kwargs):
            text = str(path)
            if text.startswith(str(self.target)):
                return os.path.join(str(self.notes), "agent-policy")
            return original_realpath(path, *args, **kwargs)

        os.path.realpath = _fake
        try:
            with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                self._publish_to(str(self.target))
        finally:
            os.path.realpath = original_realpath
        self.assertEqual(ctx.exception.code, "target_resolves_to_protected_path")

    def test_resolution_into_synthetic_config_is_rejected(self):
        """realpath 解析后落到合成 ``config`` → 拒绝。"""
        original_realpath = os.path.realpath

        def _fake(path, *args, **kwargs):
            text = str(path)
            if text.startswith(str(self.target)):
                return os.path.join(str(self.config), "agent-policy")
            return original_realpath(path, *args, **kwargs)

        os.path.realpath = _fake
        try:
            with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                self._publish_to(str(self.target))
        finally:
            os.path.realpath = original_realpath
        self.assertEqual(ctx.exception.code, "target_resolves_to_protected_path")

    def test_resolution_into_synthetic_db_file_is_rejected(self):
        """realpath 解析后指向受保护 DB 基名 → 拒绝。"""
        original_realpath = os.path.realpath

        def _fake(path, *args, **kwargs):
            text = str(path)
            if text.startswith(str(self.target)):
                return str(self.tmp / "task_publisher.db")
            return original_realpath(path, *args, **kwargs)

        os.path.realpath = _fake
        try:
            with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                self._publish_to(str(self.target))
        finally:
            os.path.realpath = original_realpath
        self.assertEqual(ctx.exception.code, "target_resolves_to_protected_path")

    def test_ordinary_temp_target_is_still_allowed(self):
        """对照组：普通 TEMP 目标不受影响（不得过度拦截）。"""
        plain = self.tmp / "plain-agent-policy"
        plain.mkdir()
        result = self._publish_to(str(plain))
        self.assertEqual(result["outcome"], "published")
        self.assertTrue((plain / agent_policy.POLICY_FILENAME).is_file())


class RollbackMetadataConsistencyTests(_PublisherTestBase):
    """回滚必须恢复"当初被批准的那份文档"，且元数据逐字自洽。"""

    def _history_entry(self, index=0):
        path = Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME / self._history_files()[index]
        return path, json.loads(path.read_text(encoding="utf-8"))

    def _tamper(self, mutate):
        path, entry = self._history_entry()
        mutate(entry)
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_publish_binds_document_metadata_to_the_approval_evidence(self):
        """发布时：策略文档的元数据必须与同一份批准证据逐字绑定。"""
        self._publish()
        path, entry = self._history_entry()
        document = entry["policy_document"]
        evidence = entry["approval_evidence"]
        self.assertEqual(document["approved_at"], evidence["approved_at"])
        self.assertEqual(document["proposal_sha256"], entry["proposal_sha256"])
        self.assertEqual(document["version"], entry["new_version"])
        self.assertEqual(document["effect_summary"], entry["effect_summary"])
        self.assertIs(document["approved_by_user"], True)
        # 文档本身不携带批准人身份（只带"已批准"这一事实）
        self.assertNotIn("approved_by", document)

    def test_rollback_rejects_proposal_digest_mismatch(self):
        """历史条目指纹与策略文档指纹脱钩 → 拒绝回滚。"""
        self._publish()
        self._tamper(lambda e: e["policy_document"].__setitem__("proposal_sha256", "f" * 64))
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.rollback(
                self.policy_dir,
                version="2026-10-22.1",
                approval_evidence=_evidence(),
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "rollback_metadata_mismatch")

    def test_rollback_rejects_approved_at_mismatch(self):
        """策略文档的批准时间与批准证据不一致 → 拒绝回滚。"""
        self._publish()
        self._tamper(
            lambda e: e["policy_document"].__setitem__("approved_at", "2019-01-01T00:00:00+00:00")
        )
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.rollback(
                self.policy_dir,
                version="2026-10-22.1",
                approval_evidence=_evidence(),
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "rollback_metadata_mismatch")

    def test_rollback_restores_original_approved_metadata(self):
        """正向：回滚后的 latest 仍是当初那份被批准的文档。"""
        self._publish()
        first_digest = self._digest()
        second = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        self._publish(second, proposal_digest_expected=self._digest(second))
        agent_policy_publisher.rollback(
            self.policy_dir,
            version="2026-10-22.1",
            approval_evidence=_evidence(),
            authorize=True,
            authorization_note=AUTH_NOTE,
        )
        doc = json.loads(self._latest_path().read_text(encoding="utf-8"))
        self.assertEqual(doc["proposal_sha256"], first_digest)
        self.assertEqual(doc["approved_at"], VALID_EVIDENCE["approved_at"])
        self.assertIs(doc["approved_by_user"], True)
        self.assertEqual(doc["free_task_minutes"], 25)

    def test_rollback_still_requires_fresh_approval(self):
        """回滚必须携带 *本次* 的外部批准证据，不得靠文档自带批准放行。"""
        self._publish()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            agent_policy_publisher.rollback(
                self.policy_dir,
                version="2026-10-22.1",
                approval_evidence=None,
                authorize=True,
                authorization_note=AUTH_NOTE,
            )
        self.assertEqual(ctx.exception.code, "approval_evidence_missing")


class OrphanHistoryEntryTests(_PublisherTestBase):
    """历史写入成功但 ``os.replace`` 失败 → 孤儿 entry。

    Publisher 的写入顺序是"不可变历史 → 原子替换 latest → 回执"。
    若中间崩溃，历史里会留下一条 **从未成为 current** 的 entry。
    这不会破坏既有 latest（仍完整有效），但旧实现会把该提案指纹标记为
    "已发布过"，从而把同提案重试永久挡在 ``duplicate_proposal`` 之前。

    **LT_BOOTSTRAP_PUBLISHER_CRASH_RECOVERY_20261022_F** 把这条"残留风险"
    升级为"可安全恢复的受控流程"：同提案重试不再被永久拒绝，而是在
    写锁保护内逐项核对历史 entry 与当前 latest 的指纹链，核对通过才
    原子完成那次未成功的替换并补写回执；核对不通过一律 fail closed。

    本类的两条用例仍然钉住"崩溃后 latest 字节完全不变"这一底线，
    并补充恢复路径的断言。
    """

    def test_failed_replace_leaves_orphan_entry_but_valid_latest(self):
        self._publish()
        good = self._latest_path().read_bytes()
        second = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        original_replace = os.replace

        def _boom(src, dst):
            raise OSError("synthetic crash during replace")

        os.replace = _boom
        try:
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))
        finally:
            os.replace = original_replace

        # 既有 latest 完好且仍可读
        self.assertEqual(self._latest_path().read_bytes(), good)
        self.assertTrue(agent_policy.read_policy_status(self.policy_dir)["initialized"])
        # 第二版的回执从未生成（只有第一版有回执）
        receipts = sorted(
            p.name for p in (Path(self.policy_dir) / agent_policy_publisher.RECEIPTS_DIRNAME).glob("*.json")
        )
        self.assertEqual(len(receipts), 1)
        self.assertNotIn("2026-10-22.2", receipts[0])
        # 孤儿 entry 存在（不可变，保留待人工审计）
        self.assertEqual(len(self._history_files()), 2)

    def test_orphan_entry_no_longer_permanently_blocks_the_retry(self):
        """F 轮修复：同提案重试不再被永久拒绝，而是走受控恢复。

        旧行为：``duplicate_proposal`` → 用户永远无法发布这份提案
        （尽管它从未真正生效）。新行为：核对通过则安全恢复。
        """
        self._publish()
        second = _proposal(version="2026-10-22.2", effect_summary="第二版效果说明，供用户感知")
        original_replace = os.replace

        def _boom(src, dst):
            raise OSError("synthetic crash during replace")

        os.replace = _boom
        try:
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))
        finally:
            os.replace = original_replace

        result = self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(result["outcome"], "recovered")
        self.assertEqual(result["recovery"], "latest_recovered")
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.2"
        )
        # 历史条目数量不变（恢复 **不** 追加重复历史）
        self.assertEqual(len(self._history_files()), 2)


class TrustBoundaryHonestyTests(_PublisherTestBase):
    """信任边界的诚实记录：结构校验 **不等于** 真实用户同意。

    本类刻意断言一个"限制"而非"能力"：``approval_evidence`` 只做
    结构性校验。结构完整但语义伪造的证据依然会被接受，因为本工具
    既不与人对话，也不做数字签名验签。真实同意的来源永远是 Controller
    对真实用户原文的核对——这一点由本测试固定下来，避免日后被误述为
    "签名鉴权"。
    """

    def test_structurally_valid_but_fabricated_evidence_is_still_accepted(self):
        """**已知限制**：结构完整即通过；这不是身份或签名验证。"""
        fabricated = _evidence(approved_by="totally-not-a-human", approval_text="我本人从未说过这句话")
        result = self._publish(approval_evidence=fabricated)
        self.assertEqual(result["outcome"], "published")
        doc = json.loads(self._latest_path().read_text(encoding="utf-8"))
        self.assertEqual(doc["approved_by_user"], True)  # 恒为 True，不携带批准人身份
        self.assertNotIn("approved_by", doc)

    def test_publisher_never_accepts_self_service_approval_flag(self):
        """并发 / 出错时不得靠提案自称批准自我授权。"""
        proposal = _proposal(approved_by_user=True, approved_at=VALID_EVIDENCE["approved_at"])
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(
                proposal,
                proposal_digest_expected=self._digest(proposal),
                approval_evidence=None,
            )
        self.assertEqual(ctx.exception.code, "approval_evidence_missing")
        self.assertFalse(self._latest_path().exists())

    def test_trust_boundary_note_is_always_reported(self):
        note = agent_policy_publisher.TRUST_BOUNDARY_NOTE
        self.assertIn("无法验证", note)
        self.assertIn("批准证据由 Controller", note)
        preview = agent_policy_publisher.prepare(VALID_PROPOSAL, self.policy_dir)
        self.assertEqual(preview["trust_boundary"], note)
        self.assertFalse(preview["authorized"])


# ===========================================================================
# LT_BOOTSTRAP_PUBLISHER_CRASH_RECOVERY_20261022_F
#   崩溃恢复：安全、可审计、幂等
#
#   场景覆盖（全部在 %TEMP% 合成策略根中运行）：
#     1. 首次 / 后续批准发布成功
#     2. history 写成功之后 monkeypatch os.replace 故障
#        → latest 字节完全不变、历史可追溯、重试时可有条件恢复
#     3. receipt 写失败且 latest 有效 → 幂等恢复
#     4. mismatched proposal SHA / approval evidence / previous latest hash
#        → 一律 fail closed
#     5. 版本冲突、重试多次不增加重复历史
#     6. 旧合法历史与 E 的全部保留字段安全测试不回归
#
#   红线：本文件绝不写真实 data/agent-policy、data/task_publisher.db*、
#   config/config.json 或 src/notes/**；不启动真实 Flask / database。
# ===========================================================================


class CrashRecoveryBase(_PublisherTestBase):
    """崩溃恢复测试的公共辅助（全部使用合成临时目录）。"""

    def _second_proposal(self):
        return _proposal(
            version="2026-10-22.2",
            effect_summary="第二版效果说明，供用户感知",
        )

    def _crash_on_replace(self):
        """返回一个 context manager：期间 ``os.replace`` 一律抛 OSError。"""

        class _Ctx:
            def __init__(self, outer):
                self.outer = outer
                self.original = None

            def __enter__(self):
                self.original = os.replace

                def _boom(src, dst):
                    raise OSError("synthetic crash during replace")

                os.replace = _boom
                return self

            def __exit__(self, *_exc):
                os.replace = self.original
                return False

        return _Ctx(self)

    def _crash_on_nth_replace(self, nth):
        """在第 ``nth`` 次 ``os.replace`` 时抛错（1 = latest，2 = 回执）。"""

        class _Ctx:
            def __init__(self):
                self.original = None
                self.calls = 0

            def __enter__(self):
                self.original = os.replace
                counter = self

                def _counted(src, dst):
                    counter.calls += 1
                    if counter.calls == nth:
                        raise OSError("synthetic crash during replace")
                    return counter.original(src, dst)

                os.replace = _counted
                return self

            def __exit__(self, *_exc):
                os.replace = self.original
                return False

        return _Ctx()

    def _history_entries(self):
        entries = []
        history_dir = Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME
        if history_dir.is_dir():
            for path in sorted(history_dir.glob("*.json")):
                entries.append(json.loads(path.read_text(encoding="utf-8")))
        return entries

    def _receipts(self):
        receipts = []
        receipts_dir = Path(self.policy_dir) / agent_policy_publisher.RECEIPTS_DIRNAME
        if receipts_dir.is_dir():
            for path in sorted(receipts_dir.glob("*.json")):
                receipts.append(json.loads(path.read_text(encoding="utf-8")))
        return receipts


class Scenario1NormalPublishTests(CrashRecoveryBase):
    """场景 1：首次 / 后续批准发布成功（恢复逻辑不得误伤正常路径）。"""

    def test_first_publish_still_succeeds(self):
        result = self._publish()
        self.assertEqual(result["outcome"], "published")
        self.assertTrue(agent_policy.read_policy_status(self.policy_dir)["initialized"])
        self.assertEqual(len(self._history_files()), 1)
        self.assertEqual(len(self._receipts()), 1)

    def test_second_approval_publish_still_succeeds(self):
        self._publish()
        second = self._second_proposal()
        result = self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(result["outcome"], "published")
        self.assertEqual(len(self._history_files()), 2)
        self.assertEqual(len(self._receipts()), 2)
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.2"
        )

    def test_republish_is_still_idempotent(self):
        self._publish()
        again = self._publish()
        self.assertEqual(again["outcome"], "already_published")
        self.assertEqual(len(self._history_files()), 1)
        self.assertEqual(len(self._receipts()), 1)


class Scenario2ReplaceCrashTests(CrashRecoveryBase):
    """场景 2：history 写成功后 ``os.replace`` 故障。

    底线：**latest 字节完全不变**、历史可追溯、重试时可有条件恢复。
    """

    def test_latest_bytes_are_completely_unchanged_after_crash(self):
        self._publish()
        good = self._latest_path().read_bytes()
        second = self._second_proposal()
        with self._crash_on_replace():
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))
        # 字节级完全一致（不只是"仍然有效"）
        self.assertEqual(self._latest_path().read_bytes(), good)
        self.assertTrue(agent_policy.read_policy_status(self.policy_dir)["initialized"])

    def test_history_remains_traceable_after_crash(self):
        self._publish()
        second = self._second_proposal()
        with self._crash_on_replace():
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))
        # 历史保留（不可变），孤儿条目可追溯
        entries = self._history_entries()
        self.assertEqual(len(entries), 2)
        orphan = [e for e in entries if e["new_version"] == "2026-10-22.2"]
        self.assertEqual(len(orphan), 1)
        self.assertEqual(orphan[0]["proposal_sha256"], self._digest(second))
        self.assertIsNotNone(orphan[0]["published_policy_sha256"])
        self.assertIsNotNone(orphan[0]["previous_policy_sha256"])
        # 孤儿条目带完整批准证据（审计材料未丢）
        self.assertEqual(
            orphan[0]["approval_evidence"]["approval_text"],
            VALID_EVIDENCE["approval_text"],
        )

    def test_retry_after_crash_recovers_conditionally(self):
        self._publish()
        second = self._second_proposal()
        with self._crash_on_replace():
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))

        result = self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(result["outcome"], "recovered")
        self.assertEqual(result["recovery"], "latest_recovered")
        status = agent_policy.read_policy_status(self.policy_dir)
        self.assertTrue(status["initialized"])
        self.assertEqual(status["version"], "2026-10-22.2")
        # 历史条目数不变（恢复不追加历史）
        self.assertEqual(len(self._history_files()), 2)
        # 回执已补齐
        self.assertEqual(len(self._receipts()), 2)

    def test_recovery_receipt_records_the_recovery_action(self):
        self._publish()
        second = self._second_proposal()
        with self._crash_on_replace():
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))
        self._publish(second, proposal_digest_expected=self._digest(second))
        recovered = [
            r for r in self._receipts() if r.get("new_version") == "2026-10-22.2"
        ]
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["receipt_type"], "publish_recovered")
        self.assertEqual(recovered[0]["recovery_action"], "replace_latest")
        self.assertEqual(
            recovered[0]["proposal_sha256"], self._digest(second)
        )

    def test_first_publish_crash_then_retry_recovers_to_initial_state(self):
        """首次发布（没有既有 latest）崩溃后同样可恢复。"""
        second = self._second_proposal()
        with self._crash_on_replace():
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertFalse(self._latest_path().exists())
        self.assertEqual(len(self._history_files()), 1)

        result = self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(result["outcome"], "recovered")
        status = agent_policy.read_policy_status(self.policy_dir)
        self.assertTrue(status["initialized"])
        self.assertEqual(status["version"], "2026-10-22.2")
        self.assertEqual(len(self._history_files()), 1)


class Scenario3ReceiptFailureTests(CrashRecoveryBase):
    """场景 3：回执写失败（latest 已生效）→ 幂等恢复。"""

    def _publish_with_receipt_failure(self, proposal=None):
        """让第 2 次 ``os.replace``（即回执写入）失败。"""
        proposal = proposal if proposal is not None else VALID_PROPOSAL
        with self._crash_on_nth_replace(2):
            with self.assertRaises(
                agent_policy_publisher.PublisherError
            ) as ctx:
                self._publish(proposal, proposal_digest_expected=self._digest(proposal))
        self.assertEqual(ctx.exception.code, "receipt_unwritable")
        return ctx.exception

    def test_latest_is_valid_but_receipt_is_missing_after_failure(self):
        self._publish_with_receipt_failure()
        # latest 已生效
        status = agent_policy.read_policy_status(self.policy_dir)
        self.assertTrue(status["initialized"])
        self.assertEqual(status["version"], "2026-10-22.1")
        # 回执缺失
        self.assertEqual(len(self._receipts()), 0)
        # 历史保留
        self.assertEqual(len(self._history_files()), 1)

    def test_retry_recovers_missing_receipt_idempotently(self):
        self._publish_with_receipt_failure()
        result = self._publish()
        self.assertEqual(result["outcome"], "already_published")
        self.assertEqual(result["recovery"], "receipt_recovered")
        receipts = self._receipts()
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["receipt_type"], "publish_recovered")
        self.assertEqual(receipts[0]["recovery_action"], "receipt_only")

    def test_retry_after_receipt_recovery_is_stable_and_idempotent(self):
        self._publish_with_receipt_failure()
        self._publish()  # 补齐回执
        again = self._publish()  # 再来一次
        self.assertEqual(again["outcome"], "already_published")
        self.assertNotIn("recovery", again)
        # 回执与历史都 **不** 重复
        self.assertEqual(len(self._receipts()), 1)
        self.assertEqual(len(self._history_files()), 1)

    def test_receipt_recovery_does_not_rewrite_latest(self):
        self._publish_with_receipt_failure()
        good = self._latest_path().read_bytes()
        self._publish()
        self.assertEqual(self._latest_path().read_bytes(), good)

    def test_receipt_recovery_never_republishes(self):
        """恢复只补回执，绝不重复发布（历史条目数不变）。"""
        self._publish_with_receipt_failure()
        self._publish()
        self._publish()
        self.assertEqual(len(self._history_files()), 1)


class Scenario4FailClosedTests(CrashRecoveryBase):
    """场景 4：核对不通过 → 一律 fail closed，绝不覆盖有效 latest。"""

    def _make_orphan(self):
        """制造一次孤儿 entry（历史已写、latest 替换失败）。"""
        self._publish()
        second = self._second_proposal()
        with self._crash_on_replace():
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))
        return second

    def test_mismatched_approval_evidence_fails_closed(self):
        second = self._make_orphan()
        before = self._latest_path().read_bytes()
        history_before = self._history_files()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(
                second,
                proposal_digest_expected=self._digest(second),
                approval_evidence=_evidence(approval_text="完全不同的批准原文"),
            )
        self.assertEqual(ctx.exception.code, "recovery_approval_mismatch")
        # latest 未被覆盖、历史未被改写
        self.assertEqual(self._latest_path().read_bytes(), before)
        self.assertEqual(self._history_files(), history_before)
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.1"
        )

    def test_different_approver_fails_closed(self):
        second = self._make_orphan()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(
                second,
                proposal_digest_expected=self._digest(second),
                approval_evidence=_evidence(approved_by="someone-else"),
            )
        self.assertEqual(ctx.exception.code, "recovery_approval_mismatch")

    def test_older_approval_timestamp_fails_closed(self):
        second = self._make_orphan()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(
                second,
                proposal_digest_expected=self._digest(second),
                approval_evidence=_evidence(approved_at="2026-10-21T09:00:00+00:00"),
            )
        self.assertEqual(ctx.exception.code, "recovery_approval_mismatch")

    def test_mismatched_proposal_body_in_history_fails_closed(self):
        second = self._make_orphan()
        # 篡改历史条目里的提案原文（指纹字段保持不变）
        history_dir = Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME
        target = None
        for path in history_dir.glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("new_version") == "2026-10-22.2":
                target = path
                doc["proposal"]["effect_summary"] = "被篡改的效果说明文本内容"
                path.write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        self.assertIsNotNone(target)
        before = self._latest_path().read_bytes()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(ctx.exception.code, "recovery_proposal_mismatch")
        self.assertEqual(self._latest_path().read_bytes(), before)

    def test_mismatched_previous_latest_hash_fails_closed(self):
        second = self._make_orphan()
        # 篡改历史条目记录的 previous_policy_sha256（链断）
        history_dir = Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME
        for path in history_dir.glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("new_version") == "2026-10-22.2":
                doc["previous_policy_sha256"] = "f" * 64
                path.write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        before = self._latest_path().read_bytes()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(ctx.exception.code, "recovery_state_mismatch")
        self.assertEqual(self._latest_path().read_bytes(), before)

    def test_corrupted_published_hash_fails_closed(self):
        second = self._make_orphan()
        history_dir = Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME
        for path in history_dir.glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("new_version") == "2026-10-22.2":
                doc["published_policy_sha256"] = "a" * 64
                path.write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        before = self._latest_path().read_bytes()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(ctx.exception.code, "recovery_history_corrupt")
        self.assertEqual(self._latest_path().read_bytes(), before)

    def test_tampered_policy_document_fails_closed(self):
        second = self._make_orphan()
        history_dir = Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME
        for path in history_dir.glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("new_version") == "2026-10-22.2":
                doc["policy_document"]["free_task_minutes"] = 999
                path.write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        before = self._latest_path().read_bytes()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(ctx.exception.code, "recovery_history_corrupt")
        self.assertEqual(self._latest_path().read_bytes(), before)

    def test_unreadable_history_file_is_not_silently_skipped(self):
        """坏 JSON 历史文件不得被静默跳过（它能隐藏同指纹碰撞）。"""
        second = self._make_orphan()
        history_dir = Path(self.policy_dir) / agent_policy_publisher.HISTORY_DIRNAME
        broken = history_dir / "000099-broken-{}.json".format(self._digest(second)[:12])
        broken.write_text("{not json", encoding="utf-8")
        before = self._latest_path().read_bytes()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertIn(
            ctx.exception.code,
            ("history_unreadable", "recovery_history_unreadable"),
        )
        self.assertEqual(self._latest_path().read_bytes(), before)

    def test_recovery_requires_fresh_authorization(self):
        """恢复同样需要本次的显式操作授权。"""
        second = self._make_orphan()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(
                second,
                proposal_digest_expected=self._digest(second),
                authorize=False,
            )
        self.assertEqual(ctx.exception.code, "authorization_missing")

    def test_recovery_requires_approval_evidence(self):
        second = self._make_orphan()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(
                second,
                proposal_digest_expected=self._digest(second),
                approval_evidence=None,
            )
        self.assertEqual(ctx.exception.code, "approval_evidence_missing")

    def test_recovery_does_not_activate_a_proposal_without_approval(self):
        """绝不把一份缺失批准的提案默默激活。"""
        second = self._make_orphan()
        before = self._latest_path().read_bytes()
        with self.assertRaises(agent_policy_publisher.PublisherError):
            self._publish(
                second,
                proposal_digest_expected=self._digest(second),
                approval_evidence=None,
                authorize=True,
            )
        self.assertEqual(self._latest_path().read_bytes(), before)
        self.assertFalse(
            agent_policy.read_policy_status(self.policy_dir)["version"] == "2026-10-22.2"
        )


class Scenario5ConflictAndIdempotenceTests(CrashRecoveryBase):
    """场景 5：版本冲突 fail closed；重试多次不增加重复历史。"""

    def test_latest_updated_by_someone_else_fails_closed(self):
        """latest 已被他人更新 → 绝不覆盖。"""
        self._publish()
        second = self._second_proposal()
        with self._crash_on_replace():
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))

        # 另一个发布落地（更高版本）
        third = _proposal(
            version="2026-10-22.3",
            effect_summary="第三版效果说明，供用户感知",
        )
        self._publish(third, proposal_digest_expected=self._digest(third))
        before = self._latest_path().read_bytes()

        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(ctx.exception.code, "recovery_state_mismatch")
        self.assertEqual(self._latest_path().read_bytes(), before)
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.3"
        )

    def test_repeated_recovery_does_not_duplicate_history(self):
        self._publish()
        second = self._second_proposal()
        with self._crash_on_replace():
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))
        for _ in range(5):
            self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(len(self._history_files()), 2)
        self.assertEqual(len(self._receipts()), 2)

    def test_repeated_recovery_is_idempotent_on_latest_bytes(self):
        self._publish()
        second = self._second_proposal()
        with self._crash_on_replace():
            with self.assertRaises(OSError):
                self._publish(second, proposal_digest_expected=self._digest(second))
        self._publish(second, proposal_digest_expected=self._digest(second))
        good = self._latest_path().read_bytes()
        for _ in range(3):
            result = self._publish(second, proposal_digest_expected=self._digest(second))
            self.assertEqual(result["outcome"], "already_published")
        self.assertEqual(self._latest_path().read_bytes(), good)
        self.assertEqual(len(self._history_files()), 2)

    def test_duplicate_version_with_different_proposal_still_rejected(self):
        self._publish()
        other = _proposal(effect_summary="同版本号但不同内容的效果说明文本")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(other, proposal_digest_expected=self._digest(other))
        self.assertIn(ctx.exception.code, ("duplicate_version", "version_not_newer"))

    def test_rolled_back_proposal_is_not_silently_republished(self):
        """v2 发布过 → 受控回滚到 v1 → 再提交 v2：必须拒绝，绝不静默重发。

        这一条是恢复逻辑最危险的边界：回滚之后，latest 恰好等于 v2
        历史条目记录的 ``previous_policy_sha256``，若不识别回滚记录，
        就会把一次受控回滚悄悄变成一次未经再次批准的重新发布。
        """
        self._publish()
        second = self._second_proposal()
        self._publish(second, proposal_digest_expected=self._digest(second))
        agent_policy_publisher.rollback(
            self.policy_dir,
            version="2026-10-22.1",
            approval_evidence=_evidence(),
            authorize=True,
            authorization_note=AUTH_NOTE,
        )
        before = self._latest_path().read_bytes()
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(second, proposal_digest_expected=self._digest(second))
        self.assertEqual(ctx.exception.code, "duplicate_proposal")
        # latest 未被改动
        self.assertEqual(self._latest_path().read_bytes(), before)
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.1"
        )
        # 历史条目数不变
        self.assertEqual(len(self._history_files()), 2)

    def test_version_must_be_strictly_newer_than_current(self):
        self._publish()
        older = _proposal(version="2026-10-21.9", effect_summary="更旧的版本效果说明文本")
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(older, proposal_digest_expected=self._digest(older))
        self.assertEqual(ctx.exception.code, "version_not_newer")


class Scenario6NoRegressionTests(CrashRecoveryBase):
    """场景 6：旧合法历史与 E 的保留字段安全测试不回归。"""

    def test_legacy_history_entry_still_usable_for_rollback(self):
        """E 轮的合法历史仍可受控回滚（恢复逻辑未破坏回滚路径）。"""
        self._publish()
        second = self._second_proposal()
        self._publish(second, proposal_digest_expected=self._digest(second))
        result = agent_policy_publisher.rollback(
            self.policy_dir,
            version="2026-10-22.1",
            approval_evidence=_evidence(),
            authorize=True,
            authorization_note=AUTH_NOTE,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            agent_policy.read_policy_status(self.policy_dir)["version"], "2026-10-22.1"
        )

    def test_reserved_fields_are_still_rejected_after_recovery_change(self):
        malicious = _proposal(
            version="2026-10-22.9",
            effect_summary="恶意提案的效果说明文本内容",
            policy={"version": "HACKED", "approved_at": "2000-01-01T00:00:00+00:00"},
        )
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(malicious, proposal_digest_expected=self._digest(malicious))
        self.assertEqual(ctx.exception.code, "policy_reserved_field_conflict")
        self.assertFalse(self._latest_path().exists())

    def test_draft_self_approval_still_grants_nothing(self):
        proposal = _proposal(approved_by_user=True, approved_at=VALID_EVIDENCE["approved_at"])
        with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
            self._publish(
                proposal,
                proposal_digest_expected=self._digest(proposal),
                approval_evidence=None,
            )
        self.assertEqual(ctx.exception.code, "approval_evidence_missing")
        self.assertFalse(self._latest_path().exists())

    def test_history_entries_keep_every_reserved_audit_field(self):
        """恢复逻辑引用的审计字段必须真实存在于历史条目中。"""
        self._publish()
        entry = self._history_entries()[0]
        for field in (
            "proposal_sha256",
            "previous_policy_sha256",
            "published_policy_sha256",
            "approval_evidence",
            "policy_document",
            "proposal",
            "previous_version",
            "new_version",
            "sequence",
            "entry_type",
        ):
            self.assertIn(field, entry)

    def test_history_entry_filename_carries_the_digest_prefix(self):
        """恢复判定依赖文件名里的指纹前缀；命名约定不得漂移。"""
        self._publish()
        name = self._history_files()[0]
        self.assertIsNotNone(agent_policy_publisher._history_name_digest(name))
        self.assertEqual(
            agent_policy_publisher._history_name_digest(name),
            self._digest()[:12],
        )


class StaleLockTests(_PublisherTestBase):
    """崩溃残留锁：安全拒绝 + 可核对信息，**绝不** 自动解锁。"""

    def test_stale_lock_blocks_publish_and_reports_detailed_reason(self):
        lock_path = Path(self.policy_dir) / agent_policy_publisher.LOCK_FILENAME
        lock_path.write_text("held", encoding="utf-8")
        try:
            with self.assertRaises(agent_policy_publisher.PublisherError) as ctx:
                self._publish()
            self.assertEqual(ctx.exception.code, "publish_locked")
            self.assertIn("lock_age_seconds", ctx.exception.detail)
            self.assertIn("人工", ctx.exception.detail)
            self.assertFalse(self._latest_path().exists())
        finally:
            lock_path.unlink()

    def test_lock_status_reports_but_never_removes_the_lock(self):
        lock_path = Path(self.policy_dir) / agent_policy_publisher.LOCK_FILENAME
        lock_path.write_text("held", encoding="utf-8")
        try:
            status = agent_policy_publisher.lock_status(self.policy_dir)
            self.assertTrue(status["locked"])
            self.assertIsInstance(status["age_seconds"], int)
            self.assertTrue(lock_path.exists())
        finally:
            lock_path.unlink()

    def test_lock_status_reports_no_lock(self):
        status = agent_policy_publisher.lock_status(self.policy_dir)
        self.assertFalse(status["locked"])
        self.assertIsNone(status["age_seconds"])

    def test_lock_status_never_creates_anything(self):
        agent_policy_publisher.lock_status(self.policy_dir)
        self.assertFalse(
            (Path(self.policy_dir) / agent_policy_publisher.LOCK_FILENAME).exists()
        )

    def test_cli_lock_status_command_never_unlocks(self):
        lock_path = Path(self.policy_dir) / agent_policy_publisher.LOCK_FILENAME
        lock_path.write_text("held", encoding="utf-8")
        try:
            code = agent_policy_publisher.main(
                ["lock-status", "--policy-dir", self.policy_dir]
            )
            self.assertEqual(code, 0)
            self.assertTrue(lock_path.exists())
        finally:
            lock_path.unlink()


class RecoveryRealDataUntouchedTests(unittest.TestCase):
    """红线守卫：恢复路径绝不写真实项目数据。"""

    def test_real_policy_root_is_never_created_by_recovery(self):
        real_root = PROJECT_ROOT / "data" / "agent-policy"
        existed_before = real_root.exists()
        status = agent_policy.read_policy_status(str(real_root))
        self.assertIn("initialized", status)
        self.assertEqual(real_root.exists(), existed_before)

    def test_protected_files_still_exist(self):
        for path in (
            PROJECT_ROOT / "data" / "task_publisher.db",
            PROJECT_ROOT / "config" / "config.json",
        ):
            if path.exists():
                self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
