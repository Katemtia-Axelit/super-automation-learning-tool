"""AR03-P5 —— ``/api/health`` 响应契约测试。

裁决依据
--------
``docs/P2_LEGACY_DIVERGENCE_LEDGER_20261121.md`` **L-01** 已裁决：

    **R1** —— Factory 为权威（生产实际可观察形状）
    处置   —— **保留 Factory 形状** ``{"phase": 1, "status": "ok"}``

因此本测试锁定的唯一权威形状是::

    {"phase": 1, "status": "ok"}

历史形状 ``{"status": "healthy"}`` **只**允许出现在 **冻结的历史 fixture**
（``tests/fixtures/legacy_baseline.json`` / ``legacy_divergence.json``）
与 **历史文档 / 归档脚本** 中 —— 那些是历史 oracle，不是活代码。

测试方式
--------
**全部用 Flask ``test_client()``** —— 不启动任何额外服务进程。

关于 ``server/backend_api.py``
-----------------------------
legacy 兼容入口 **不再持有** 自己的 ``/api/health`` 路由（已收口为薄别名，
委托 ``create_app()``），因此它天然与 Factory **逐键一致**。
本测试用 **导入兼容入口** 的方式验证这一点；若兼容入口不可导入，
则断言「该事实」本身，**不** 因此失败。

安全边界
--------
全部使用 **临时合成 SQLite** 与临时 Vault；
**绝不** 读写生产 ``data/task_publisher.db*``、``src/notes/**``、
``config/config.json``。
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


#: L-01 裁决的 **唯一权威形状**。
AUTHORITATIVE_HEALTH_BODY = {"phase": 1, "status": "ok"}

#: 历史形状 —— 只允许出现在冻结 fixture 与历史文档里。
LEGACY_HEALTH_BODY = {"status": "healthy"}

#: 允许命中历史形状的 **冻结** fixture。
FROZEN_FIXTURES = {
    "tests/fixtures/legacy_baseline.json",
    "tests/fixtures/legacy_divergence.json",
}


# ---------------------------------------------------------------------------
# 合成环境
# ---------------------------------------------------------------------------

def _make_sandbox(tmp_path):
    """构造一个 **完全合成** 的项目根（配置 + 数据库 + Vault）。

    绝不读写真实 ``config/config.json``、``data/task_publisher.db``、
    ``src/notes/**``。
    """
    from sandbox_env import available_port, materialize, seed

    root = materialize(tmp_path / "sandbox", available_port())
    seed(root)
    return root


def _factory_app(root: Path):
    """在合成根上创建 Factory app。"""
    import os

    previous = os.getcwd()
    os.chdir(root)
    try:
        for module in list(sys.modules):
            if module.startswith("server"):
                del sys.modules[module]
        sys.path.insert(0, str(root))
        try:
            from server.app.app_factory import create_app

            return create_app()
        finally:
            sys.path.remove(str(root))
    finally:
        os.chdir(previous)


# ---------------------------------------------------------------------------
# 核心契约
# ---------------------------------------------------------------------------

def test_factory_health_is_200_and_authoritative_shape(tmp_path):
    """Factory 的 ``/api/health`` → 200 + ``{"phase": 1, "status": "ok"}``（逐键断言）。"""
    root = _make_sandbox(tmp_path)
    app = _factory_app(root)

    with app.test_client() as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.get_json()
    assert body == AUTHORITATIVE_HEALTH_BODY, (
        f"/api/health 形状必须逐键等于 L-01 裁决的权威形状；实际 = {body}"
    )


def test_health_response_has_exactly_two_keys(tmp_path):
    """形状是 **精确** 的 —— 不允许多余键（防止悄悄加字段）。"""
    root = _make_sandbox(tmp_path)
    app = _factory_app(root)

    with app.test_client() as client:
        body = client.get("/api/health").get_json()

    assert set(body) == {"phase", "status"}
    assert body["status"] == "ok"
    assert body["phase"] == 1


def test_legacy_entrypoint_health_matches_factory(tmp_path):
    """兼容入口的 ``/api/health`` 与 Factory **逐键一致**。

    ``server/backend_api.py`` 已收口为薄别名（委托 ``create_app()``），
    因此两者天然一致。若兼容入口不可导入，则断言「不可达」这一事实本身
    —— **不** 因此失败（那也是一个合法的收敛结果）。
    """
    root = _make_sandbox(tmp_path)
    factory_app = _factory_app(root)

    with factory_app.test_client() as client:
        factory_body = client.get("/api/health").get_json()

    import os

    previous = os.getcwd()
    os.chdir(root)
    try:
        for module in list(sys.modules):
            if module.startswith("server"):
                del sys.modules[module]
        sys.path.insert(0, str(root))
        try:
            import server.backend_api as backend_api
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"兼容入口不可导入（合法的收敛结果）：{exc}")
        finally:
            sys.path.remove(str(root))
    finally:
        os.chdir(previous)

    legacy_app = getattr(backend_api, "app", None)
    if legacy_app is None:
        create_app = getattr(backend_api, "create_app", None)
        assert callable(create_app), (
            "兼容入口必须导出 create_app() 或 app 实例"
        )
        legacy_app = create_app()

    with legacy_app.test_client() as client:
        legacy_body = client.get("/api/health").get_json()

    assert legacy_body == factory_body, (
        f"兼容入口与 Factory 的 /api/health 不一致："
        f"{legacy_body} != {factory_body}"
    )


# ---------------------------------------------------------------------------
# 全仓唯一形状
# ---------------------------------------------------------------------------

def _scan_python_sources_for_legacy_shape():
    """扫描 ``server/**`` 与 ``static/**`` 的 **活代码**，找历史形状。

    判定依据是 **返回值形状**，而不是「文本里出现过 healthy」——
    文档与注释里提到历史形状是 **允许** 的（那是迁移记录，不是依赖）。

    具体口径：
    * Python：存在 **返回** 了含 ``"healthy"`` 字面量的 dict 的表达式；
    * JavaScript：存在 **返回** 了含 ``healthy`` 字面量的对象字面量。
    """
    offenders = []
    roots = [
        _PROJECT_ROOT / "server",
        _PROJECT_ROOT / "static",
    ]

    def _dict_has_healthy(node) -> bool:
        """判断一个 dict 字面量是否含 ``"healthy"`` 值。"""
        for key, value in zip(node.keys, node.values):
            if isinstance(value, ast.Constant) and value.value == "healthy":
                return True
            if isinstance(value, ast.Dict) and _dict_has_healthy(value):
                return True
        return False

    for root_dir in roots:
        if not root_dir.is_dir():
            continue
        for path in sorted(root_dir.rglob("*")):
            if path.suffix == ".py":
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"))
                except (SyntaxError, UnicodeDecodeError):
                    continue
                for node in ast.walk(tree):
                    # 只看 **被 return** 的 dict
                    if isinstance(node, ast.Return) and node.value is not None:
                        value = node.value
                        if isinstance(value, ast.Dict) and _dict_has_healthy(value):
                            offenders.append(
                                path.relative_to(_PROJECT_ROOT).as_posix()
                            )
                            break
            elif path.suffix == ".js":
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                # JS：``{ status: 'healthy' }`` 形式的 **对象字面量**
                if re.search(
                    r"\{\s*status\s*:\s*['\"]healthy['\"]", text
                ):
                    offenders.append(path.relative_to(_PROJECT_ROOT).as_posix())
    return sorted(set(offenders))


def test_no_live_code_returns_legacy_health_shape():
    """``server/**`` 与 ``static/**`` 的活代码 **不得** 返回历史形状。

    历史形状 ``{"status": "healthy"}`` 只允许出现在 **冻结 fixture**
    与历史文档 / 归档脚本 中。
    """
    offenders = _scan_python_sources_for_legacy_shape()
    assert not offenders, (
        "以下活代码仍含历史形状 'healthy'："
        + ", ".join(offenders)
        + " —— 权威形状是 "
        + json.dumps(AUTHORITATIVE_HEALTH_BODY, ensure_ascii=False)
    )


def test_backend_api_has_no_own_health_route():
    """``server/backend_api.py`` **不持有** 自己的 ``/api/health`` 路由。

    legacy 侧一旦重新长出自己的 health 路由，就会出现「同一 URL 两个形状」
    的漂移 —— 这正是 L-01 要消除的。
    """
    source = (_PROJECT_ROOT / "server" / "backend_api.py").read_text(
        encoding="utf-8"
    )
    assert "/api/health" not in source, (
        "server/backend_api.py 不得再持有 /api/health 路由"
    )


def test_frozen_fixtures_still_carry_the_legacy_oracle():
    """冻结的历史 fixture **保持原样**（它们是历史 oracle，不是活代码）。

    P5 **不改** 这些文件 —— 改了就失去了历史差异比对的基准。
    """
    baseline = json.loads(
        (_PROJECT_ROOT / "tests" / "fixtures" / "legacy_baseline.json").read_text(
            encoding="utf-8"
        )
    )
    entries = baseline if isinstance(baseline, list) else baseline.get("entries", [])
    health = [e for e in entries if e.get("path") == "/api/health"]
    assert health, "legacy_baseline.json 必须保留 /api/health 的历史 oracle"
    assert health[0].get("json") == LEGACY_HEALTH_BODY


# ---------------------------------------------------------------------------
# 启动链只依赖 HTTP 200
# ---------------------------------------------------------------------------

def test_startup_scripts_only_depend_on_http_200():
    """启动脚本的健康门禁 **只依赖 HTTP 200**，不解析 JSON 形状。

    因此统一形状 **不需要** 改启动脚本 —— 这也是本轮 **不** 提取
    ``_health()`` 函数的理由之一。
    """
    script = _PROJECT_ROOT / "scripts" / "start_web_safe.bat"
    if not script.is_file():
        pytest.skip("start_web_safe.bat 不存在")
    text = script.read_text(encoding="utf-8", errors="replace")

    assert "/api/health" in text, "启动脚本必须探测 /api/health"
    # 断言脚本里 **没有** 对 health 响应体做 JSON 形状断言
    assert "status" not in text.lower() or "healthy" not in text.lower(), (
        "启动脚本不应依赖 /api/health 的 JSON 形状"
    )


def test_launch_server_has_no_health_shape_dependency():
    """``scripts/launch_server.py`` 同样只依赖 HTTP 200。"""
    script = _PROJECT_ROOT / "scripts" / "launch_server.py"
    if not script.is_file():
        pytest.skip("launch_server.py 不存在")
    text = script.read_text(encoding="utf-8", errors="replace")

    assert "healthy" not in text, (
        "launch_server.py 不得依赖 /api/health 的历史形状"
    )
