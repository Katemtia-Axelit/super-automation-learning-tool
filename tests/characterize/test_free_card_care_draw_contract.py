"""M02-S02-G01-W07: care-draw 路径（``POST /api/gacha/care-draw``）的自由卡时长合同。

唯一可独立验收目标
------------------
用 **真实 Flask 路由** 在 **完全合成隔离目录** 内验证：只有 **已批准** 的
自由卡时长才决定 care-draw 路径实际派发的自由卡的 ``effective_minutes``
与可用时间筛选；**没有合法已批准时长** 的自由卡 **必须 fail-closed**
（HTTP 404、零发行记录、抽卡计数不变）。

本文件 **只写测试**：不实现、不修改任何生产代码。若真实 care-draw 路由不
符合合同，本文件保留失败用例与证据并上报 ``BLOCKED_CONTRACT``，绝不降低
安全预期、绝不伪造 PASS。

范围与红线
----------
- 只打真实 ``server.blueprints.gacha_bp`` 的 ``POST /api/gacha/care-draw``
  （经 Flask ``test_client``）。**不** 打 ``/draw`` / ``/replace`` /
  ``/multi-draw`` / ``/free-card/suggestion``，**不** 验证前端，
  **不** 触碰 Publisher 实现或 Factory 注册。
- 全部状态在 ``tempfile`` 临时目录内：合成 SQLite + 合成策略目录。
  **绝不** 读写真实 ``data/task_publisher.db``(±wal/shm)、
  ``config/config.json``、``src/notes/**``、``data/agent-policy/latest.json``。
- "已批准"策略一律经 **真实受控 Publisher**（``scripts.agent_policy_publisher``）
  在合成目录里发布（合成批准证据）；本文件 **从不** 自己伪造
  ``approved_by_user`` / ``approved_at``。
- 只读复用既有测试脚手架：``_Harness`` / ``_synthetic_root`` / ``_patched_rng``
  （来自 ``test_free_card_gacha_contract.py``，**不编辑**该既有文件）。

Controller 已裁决的设计不变量（本文档只刻画，不自行重新规划）
------------------------------------------------------------
1. 自由卡时长 **只** 来自已批准策略的 ``free_task_time_strategy.options``
   （合法值严格是整数 25 / 55）。
2. 自由卡 **不按行内 ``estimated_time``** 筛选：它按 **本次发行抽定** 的
   合法时长参与时间预算。
3. ``tasks.estimated_time`` **绝不** 被改写。
4. 没有合法已批准时长 → 该自由卡 **不可派发**：在 **带预算** 的请求里它被
   **移出候选集**（404），在 **不带预算** 的 free-only 池里同样 404；
   **绝不** 回落 ``tasks.estimated_time``。
5. 混合池中合法的 standard 卡 **仍可发行**（非自由卡路径逐位不变）。

最低场景（仅 care-draw）
------------------------
S1  已批准 ``options=[25]``；free-only 卡 ``estimated_time=80``；
    ``available_time=30`` → 200、``effective_minutes=25``、
    ``free_card_dispatchable=true``、行内 80 **不变**、正常发行记录 **恰一行**，
    且该行记录的是 **原请求的可用预算 30**（不是伪装成存储时长 25）。
S2  已批准 ``options=[55]``；free-only 卡 ``estimated_time=25``；
    ``available_time=30`` → 404、零发行记录、抽卡计数不变。
S3  策略 **只批准权重**、**没有获批自由卡时长**；free-only 卡
    ``estimated_time=25``；``available_time=30`` → 404、零发行记录、
    抽卡计数不变（行内 25 ≤ 预算 30：一旦回退就一定会被发行，因此对
    回退是 **尖锐** 的）。
S4  同样没有获批时长的 free 卡；**不带** ``available_time``、指定
    ``pool="fragment"``；行内 ``estimated_time=10``（≤ 碎片池上限 15，
    一旦发生旧式兜底回退就一定会被发行）→ 404、零发行记录、抽卡计数不变。
S5  混合池（free + standard）；策略没有获批自由卡时长；``available_time=30``
    → standard **仍可发行**、free **绝不发行**（用发行记录与
    ``task.task_type`` 证明）。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
_HERE = Path(__file__).resolve().parent
for _extra in (
    str(SOURCE_ROOT),
    str(SOURCE_ROOT / "scripts"),
    # 既有用例目录本身（pytest rootdir 注入与 ``python -m unittest`` 两种
    # 导入模式都需要它才能找到被复用的脚手架模块）。
    str(_HERE),
):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

# 复用既有脚手架（只读导入，**不** 编辑被导入的既有文件）。
# 只导入下划线私有的脚手架符号，避免把既有 TestCase 类重复收集进本文件。
try:  # pragma: no cover - 取决于 pytest 的导入模式
    from test_free_card_gacha_contract import (
        _Harness,
        _patched_rng,
        _synthetic_root,
    )
except ImportError:  # pragma: no cover
    from characterize.test_free_card_gacha_contract import (  # type: ignore
        _Harness,
        _patched_rng,
        _synthetic_root,
    )

from server.services import free_card_policy  # noqa: E402

#: 自由卡合法时长（唯一权威来自生产领域模块，本文件不另立一套）。
LEGAL_FREE_MINUTES = tuple(free_card_policy.FREE_CARD_MINUTES_OPTIONS)

#: care-draw 的真实路由路径（本文件只打这一条）。
CARE_DRAW_ROUTE = "/api/gacha/care-draw"


class _CareHarness(_Harness):
    """在既有合成 harness 上只加一个 care-draw 访问器。

    **绝不** 复用 ``_Harness.draw()``（它打到 ``/api/gacha/draw``）：
    本工单的验收对象是 care-draw 真实路由。
    """

    def care_draw(self, **payload):
        """真实 ``POST /api/gacha/care-draw``；返回 ``(response, body)``。"""
        response = self.client.post(CARE_DRAW_ROUTE, json=payload)
        return response, (response.get_json() or {})


# ===========================================================================
# S1. 已批准 25 分钟 → effective_minutes / 可派发 / 行内不变 / 发行记录
# ===========================================================================


class ApprovedDurationCareDrawTests(unittest.TestCase):
    """已批准的自由卡时长必须真正决定 care-draw 的派发时长与可派发性。"""

    def test_approved_25_minutes_drives_effective_minutes_and_issuance(self):
        """S1：行内 80 + 已批准 25 + 预算 30 → 200 / effective 25 / 行内不变。"""
        with _synthetic_root("lt_fc_s1_") as temp:
            harness = _CareHarness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25]}}
            )

            with _patched_rng(0.5):
                response, body = harness.care_draw(available_time=30)

            self.assertEqual(response.status_code, 200, body)
            task = body["task"]
            self.assertEqual(task["id"], 1, body)
            self.assertEqual(task["task_type"], "free", body)

            # --- 已批准时长决定 effective_minutes -------------------------
            self.assertEqual(task["effective_minutes"], 25, body)
            self.assertIn(25, LEGAL_FREE_MINUTES)
            # --- 可派发标记 -----------------------------------------------
            self.assertIs(task["free_card_dispatchable"], True, body)
            self.assertIsNone(task["free_card_reason"], body)

            # --- 行内 estimated_time 绝不被改写，也绝不当成自由卡时长 -----
            self.assertEqual(task["estimated_time"], 80, body)
            row = harness.task_row(1)
            self.assertEqual(row["estimated_time"], 80, row)
            self.assertNotEqual(task["effective_minutes"], row["estimated_time"])

            # --- 正常发行记录恰一行，且记录的是原请求的可用预算 30 -------
            rows = harness.issuance_rows()
            self.assertEqual(len(rows), 1, rows)
            self.assertEqual(rows[0]["task_id"], 1, rows)
            self.assertEqual(rows[0]["available_time"], 30, rows)
            # 绝不能把"存储时长 25"伪装成"可用预算"。
            self.assertNotEqual(rows[0]["available_time"], 25, rows)

            # --- 合法发行 → 抽卡计数增加一次 ------------------------------
            self.assertEqual(harness.task_row(1)["draw_count_today"], 1)

    def test_approved_duration_is_not_derived_from_inline_estimated_time(self):
        """S1 变体：行内 80 绝不被当成时长，也绝不参与筛选（25 仍能发出）。"""
        with _synthetic_root("lt_fc_s1b_") as temp:
            harness = _CareHarness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25]}}
            )

            # 预算 30：行内 80 放不下，但已批准的 25 放得下 → 必须发出。
            with _patched_rng(0.5):
                response, body = harness.care_draw(available_time=30)
            self.assertEqual(response.status_code, 200, body)
            self.assertEqual(body["task"]["effective_minutes"], 25, body)
            self.assertEqual(body["task"]["estimated_time"], 80, body)

            # 预算 20：已批准的 25 放不下 → 绝不发（行内 80 也不该救它）。
            with _patched_rng(0.5):
                response, body = harness.care_draw(available_time=20)
            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            # 404 不得新增发行记录（首轮的那一行仍然是唯一一行）。
            self.assertEqual(harness.issuance_count(), 1, "404 不得写发行记录")


# ===========================================================================
# S2. 已批准 55 分钟 → 预算不足不发行
# ===========================================================================


class ApprovedLongDurationCareDrawTests(unittest.TestCase):
    """55 分钟的自由卡绝不被发给只有 30 分钟的用户。"""

    def test_55_minute_free_card_is_not_issued_within_30_minute_budget(self):
        """S2：已批准 55 + 预算 30 → 404、零发行、抽卡计数不变。"""
        with _synthetic_root("lt_fc_s2_") as temp:
            harness = _CareHarness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [55]}}
            )

            with _patched_rng(0.5):
                response, body = harness.care_draw(available_time=30)

            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            # 不得发行、不得留下任何副作用。
            self.assertEqual(harness.issuance_rows(), [])
            row = harness.task_row(1)
            self.assertEqual(row["draw_count_today"], 0, row)
            self.assertEqual(row["estimated_time"], 25, row)


# ===========================================================================
# S3. 只批准权重、没有获批自由卡时长 → free-only 池 fail-closed
# ===========================================================================


class MissingApprovedDurationCareDrawTests(unittest.TestCase):
    """没有合法已批准时长 → 自由卡不可派发，且绝不回退任何默认值。"""

    def test_weights_only_policy_free_only_pool_returns_404(self):
        """S3：只批准权重 + 候选只有 free + 预算 30 → 404 且不发行。"""
        with _synthetic_root("lt_fc_s3_") as temp:
            harness = _CareHarness(temp)
            # 行内 25 ≤ 预算 30：一旦发生"回退行内时长"，这张卡一定会被发出来，
            # 因此本用例对回退是**尖锐**的。
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            harness.publish(weights={"card_type:free": 1.0})

            with _patched_rng(0.5):
                response, body = harness.care_draw(available_time=30)

            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            # 不得发行、不得留下副作用。
            self.assertEqual(harness.issuance_rows(), [])
            row = harness.task_row(1)
            self.assertEqual(row["draw_count_today"], 0, row)
            self.assertEqual(row["estimated_time"], 25, row)

    def test_no_budget_fragment_pool_without_approved_duration_returns_404(self):
        """S4：不带预算 + ``pool="fragment"`` + 无获批时长 → 404、零副作用。

        行内 ``estimated_time=10`` ≤ 碎片卡池上限 15：一旦旧式兜底把
        "已被排除" 的自由卡放回候选集，它一定会被发行 → 因此本用例对
        旧式错误回退是 **尖锐** 的。
        """
        with _synthetic_root("lt_fc_s4_") as temp:
            harness = _CareHarness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=10
            )
            harness.publish(weights={"card_type:free": 1.0})

            with _patched_rng(0.5):
                response, body = harness.care_draw(pool="fragment")

            self.assertEqual(response.status_code, 404, body)
            self.assertEqual(body["error"], "No tasks available", body)
            # 零发行记录（连"不可派发"的那种发行都不允许）。
            self.assertEqual(harness.issuance_rows(), [])
            # 抽卡计数逐位不变。
            row = harness.task_row(1)
            self.assertEqual(row["draw_count_today"], 0, row)
            self.assertEqual(row["estimated_time"], 10, row)


# ===========================================================================
# S5. 混合池：非自由卡照发，自由卡绝不发行
# ===========================================================================


class MixedPoolCareDrawTests(unittest.TestCase):
    """混合池里非自由卡仍按原时长发出；仅自由卡被排除。"""

    def test_mixed_pool_issues_standard_card_and_never_the_free_card(self):
        """S5：无获批时长 + 混合池 → 只发 standard，free 零副作用。"""
        with _synthetic_root("lt_fc_s5_") as temp:
            harness = _CareHarness(temp)
            # 两张卡的行内时长都 ≤ 预算 30：free 被排除 **只可能** 因为没有
            # 获批时长（而不是因为"放得下"）。
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=25
            )
            harness.add_task(
                2, "standard-card", "study", task_type="standard",
                estimated_time=25,
            )
            harness.publish(weights={"card_type:free": 1.0})

            with _patched_rng(0.5):
                response, body = harness.care_draw(available_time=30)

            self.assertEqual(response.status_code, 200, body)
            task = body["task"]
            # 发出的必须是 standard 卡（用返回的 task_type 证明）。
            self.assertEqual(task["task_type"], "standard", body)
            self.assertEqual(task["id"], 2, body)
            self.assertEqual(task["estimated_time"], 25, body)
            # 非自由卡的响应字段逐字不变（没有自由卡专属字段）。
            self.assertNotIn("effective_minutes", task)
            self.assertNotIn("free_card_dispatchable", task)
            self.assertNotIn("free_card_reason", task)

            # 发行记录只指向 standard 卡（free 绝不发行）。
            rows = harness.issuance_rows()
            self.assertEqual(len(rows), 1, rows)
            self.assertEqual(rows[0]["task_id"], 2, rows)
            self.assertEqual(rows[0]["available_time"], 30, rows)
            self.assertNotIn(
                1, [row["task_id"] for row in rows], rows
            )

            # free 卡零副作用：既没被发行也没被计数。
            free_row = harness.task_row(1)
            self.assertEqual(free_row["draw_count_today"], 0, free_row)
            self.assertEqual(free_row["estimated_time"], 25, free_row)
            # standard 卡被合法发行 → 抽卡计数增加一次。
            self.assertEqual(harness.task_row(2)["draw_count_today"], 1)


# ===========================================================================
# 路由与隔离性：本文件只打真实 care-draw，且零真实数据写入
# ===========================================================================


class CareDrawRouteAndIsolationTests(unittest.TestCase):
    """路由真实性 + 合成隔离性。"""

    def test_care_draw_route_is_registered_on_the_real_blueprint(self):
        """真实 Flask 应用里确实注册了 ``POST /api/gacha/care-draw``。"""
        with _synthetic_root("lt_fc_iso_") as temp:
            harness = _CareHarness(temp)
            rules = {
                rule.rule: rule for rule in harness.app.url_map.iter_rules()
            }
            self.assertIn(CARE_DRAW_ROUTE, rules, sorted(rules))
            self.assertIn(
                "POST", rules[CARE_DRAW_ROUTE].methods, rules[CARE_DRAW_ROUTE].methods
            )

    def test_everything_stays_inside_the_synthetic_root(self):
        """合成 DB 与合成策略目录都在临时目录内，真实红线文件零写入。"""
        with _synthetic_root("lt_fc_iso2_") as temp:
            harness = _CareHarness(temp)
            harness.add_task(
                1, "free-card", "study", task_type="free", estimated_time=80
            )
            harness.publish(
                policy={"free_task_time_strategy": {"options": [25]}}
            )
            root = Path(temp).resolve()
            self.assertTrue(str(harness.db_path.resolve()).startswith(str(root)))
            self.assertTrue(
                str(harness.policy_dir.resolve()).startswith(str(root))
            )
            latest = harness.policy_dir / "latest.json"
            self.assertTrue(latest.is_file())
            self.assertTrue(str(latest.resolve()).startswith(str(root)))
            # 项目真实红线文件绝不在合成根内被引用。
            self.assertNotIn(
                "task_publisher.db", str(harness.app.config["_db_path"])
            )
            self.assertNotIn(
                "task_publisher.db", str(harness.app.config["_agent_policy_dir"])
            )


if __name__ == "__main__":
    unittest.main()
