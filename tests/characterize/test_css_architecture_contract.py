"""AR03-P4 —— CSS 架构契约测试（characterization）。

对应 Plan §4.3 门禁 ①–⑥ 的**Python 侧**镜像断言。

门禁脚本（``scripts/check_css_architecture.js``）是权威检查；本测试文件
提供 pytest 侧的可读断言，使 ``pytest tests/characterize`` 一次覆盖
CSS 架构契约。

**只读**：不修改任何生产文件。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CSS_DIR = ROOT / "static" / "css"
INDEX_HTML = ROOT / "src" / "index.html"
ART_OVERRIDES = ROOT / "static" / "assets" / "art-overrides.css"
FIXTURES = ROOT / "tests" / "fixtures"

CSS_ORDER = ["theme", "layout", "components", "features", "cards", "responsive"]

#: 9 个语义化交互变量（Plan §3.2）。
SEMANTIC_VARS = [
    "--hover-veil",
    "--hover-veil-subtle",
    "--hover-veil-strong",
    "--active-veil",
    "--accent-veil",
    "--accent-veil-soft",
    "--accent-veil-strong",
    "--accent-veil-chip",
    "--danger-veil",
]

#: 语义变量的 dark 值 = 迁移前的原硬编码字面量（Dark 视觉必须不变）。
EXPECTED_DARK = {
    "--hover-veil": "rgba(255,255,255,0.05)",
    "--hover-veil-subtle": "rgba(255,255,255,0.03)",
    "--hover-veil-strong": "rgba(255,255,255,0.1)",
    "--active-veil": "rgba(255,255,255,0.05)",
    "--accent-veil": "rgba(240,192,64,0.1)",
    "--accent-veil-soft": "rgba(240,192,64,0.08)",
    "--accent-veil-strong": "rgba(240,192,64,0.18)",
    "--accent-veil-chip": "rgba(240,192,64,0.15)",
    "--danger-veil": "rgba(231,76,60,0.1)",
}

#: 运行时变量（由 JS / DOM 提供，CSS 不得定义）。
RUNTIME_VARS = ["--card-scale", "--deck-i"]


def _read(name: str) -> str:
    path = CSS_DIR / name
    assert path.exists(), f"缺少 static/css/{name}"
    return path.read_text(encoding="utf-8")


def _strip_comments(css: str) -> str:
    css = re.sub(r"<!--[\s\S]*?-->", "", css)
    return re.sub(r"/\*[\s\S]*?\*/", "", css)


def _block_body(css: str, selector: str) -> str:
    """返回指定选择器块内部的声明文本。"""
    masked = _strip_comments(css)
    idx = masked.find(selector)
    assert idx != -1, f"找不到块 {selector}"
    brace = masked.find("{", idx)
    depth = 0
    for j in range(brace, len(masked)):
        if masked[j] == "{":
            depth += 1
        elif masked[j] == "}":
            depth -= 1
            if depth == 0:
                return masked[brace + 1 : j]
    raise AssertionError(f"块 {selector} 未闭合")


def _var_defs(css: str) -> dict:
    """提取一个块内的 CSS 变量定义。"""
    out = {}
    for m in re.finditer(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;{}]+);", css):
        out[m.group(1)] = m.group(2).strip()
    return out


@pytest.fixture(scope="module")
def css_files() -> dict:
    return {name: _read(f"{name}.css") for name in CSS_ORDER}


# ---------------------------------------------------------------------------
# 门禁 ① Token 所有权分层
# ---------------------------------------------------------------------------


def test_gate1a_root_token_only_in_theme_css(css_files):
    """①a :root / :root[data-theme=...] 只允许出现在 theme.css。"""
    for name, css in css_files.items():
        if name == "theme":
            continue
        masked = _strip_comments(css)
        offenders = [
            m.group(0)
            for m in re.finditer(r"(^|[},;])\s*:root\b", masked)
        ]
        assert not offenders, f"{name}.css 出现了 :root 定义：{offenders}"


def test_gate1b_card_tokens_only_defined_in_cards_css(css_files):
    """①b --card-* 只允许在 cards.css 定义。"""
    for name, css in css_files.items():
        for var in _var_defs(_strip_comments(css)):
            if var.startswith("--card-"):
                assert name == "cards", f"{name}.css 定义了卡牌 Token {var}"


def test_gate1c_art_tokens_only_consumed_not_defined(css_files):
    """①c --art-* 只允许消费（不得在 CSS 中定义）；例外仅 per-theme 路由。"""
    # 唯一允许在 CSS 中定义的美术变量：M1.5C 的 per-theme 路由变量
    allowed = {"--art-card-front-layer"}
    for name, css in css_files.items():
        masked = _strip_comments(css)
        for var in _var_defs(masked):
            if not var.startswith("--art-"):
                continue
            if var in allowed:
                assert re.search(
                    rf"\.task-card\.theme-[a-z-]+\s*\{{[^}}]*{re.escape(var)}\s*:",
                    masked,
                    re.S,
                ), f"{name}.css 的 {var} 必须定义在 .task-card.theme-* 作用域内"
                continue
            raise AssertionError(f"{name}.css 定义了美术 Token {var}（应由 art-overrides.css 提供）")


def test_gate1c_art_token_consumers_are_limited(css_files):
    """①c theme/layout/components/responsive 不得消费 --art-*。"""
    for name, css in css_files.items():
        if name in ("cards", "features"):
            continue
        assert "var(--art-" not in _strip_comments(css), f"{name}.css 消费了 --art-*"


def test_gate1d_runtime_vars_not_defined_in_css(css_files):
    """①d --card-scale / --deck-i 不得在 CSS 中定义。"""
    for name, css in css_files.items():
        defs = _var_defs(_strip_comments(css))
        for var in RUNTIME_VARS:
            assert var not in defs, f"{name}.css 定义了运行时变量 {var}"


def test_gate1c_art_overrides_exists_and_defines_art_tokens():
    """美术 Token 的定义方 static/assets/art-overrides.css 必须存在且定义 --art-*。"""
    assert ART_OVERRIDES.exists(), "缺少 static/assets/art-overrides.css"
    defs = _var_defs(_strip_comments(ART_OVERRIDES.read_text(encoding="utf-8")))
    art_vars = [v for v in defs if v.startswith("--art-")]
    assert len(art_vars) >= 18, f"art-overrides.css 应定义 18 个 --art-*，实际 {len(art_vars)}"


# ---------------------------------------------------------------------------
# 门禁 ② HTML 内联样式收敛
# ---------------------------------------------------------------------------


def test_gate2_no_inline_style_blocks_in_index_html():
    """② src/index.html 内 <style> 块数 = 0。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    no_comments = re.sub(r"<!--[\s\S]*?-->", "", html)
    count = len(re.findall(r"<style[\s>]", no_comments))
    assert count == 0, f"src/index.html 仍有 {count} 个内联 <style> 块"


def test_gate2_index_html_keeps_dom_and_inline_handlers():
    """② 迁移不得改动 DOM：class / id / inline handler / style 属性数量保持。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert len(re.findall(r"\sstyle=\"", html)) == 66, "style 属性数量应为 66"
    assert len(re.findall(r"\sonclick=", html)) > 0, "inline onclick handler 丢失"
    assert 'id="freeTaskPanel"' in html, "自由任务面板 DOM 丢失"
    assert 'id="toastContainer"' in html, "toast 容器 DOM 丢失"


# ---------------------------------------------------------------------------
# 门禁 ③ 选择器唯一归属
# ---------------------------------------------------------------------------


def _top_level_selectors(css: str):
    """产出顶层规则的选择器（@media 内部的不算跨文件重复）。"""
    masked = _strip_comments(css)
    out = []
    i = 0
    while i < len(masked):
        while i < len(masked) and masked[i].isspace():
            i += 1
        if i >= len(masked):
            break
        brace = masked.find("{", i)
        if brace == -1:
            break
        prelude = masked[i:brace].strip()
        depth = 0
        end = -1
        for j in range(brace, len(masked)):
            if masked[j] == "{":
                depth += 1
            elif masked[j] == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if not prelude.startswith("@"):
            out.append(prelude)
        if end == -1:
            break
        i = end + 1
    return out


def _normalize(selector: str) -> str:
    parts = []
    for s in selector.split(","):
        s = re.sub(r"\s+", " ", s.strip())
        s = re.sub(
            r"::?(hover|active|focus|focus-visible|focus-within|checked|disabled|"
            r"selected|first-child|last-child|only-child|before|after|placeholder)\b",
            "",
            s,
        )
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            parts.append(s)
    return ",".join(sorted(parts))


def test_gate3_selector_single_ownership(css_files):
    """③ 同一选择器不得在 2 个 CSS 文件中各定义一次（豁免：modal）。"""
    owner: dict[str, set[str]] = {}
    for name, css in css_files.items():
        for sel in _top_level_selectors(css):
            for single in sel.split(","):
                key = _normalize(single)
                if not key:
                    continue
                owner.setdefault(key, set()).add(name)

    violations = []
    for key, files in owner.items():
        if len(files) <= 1:
            continue
        # 唯一豁免：.modal（基础外观 in components + 美术装饰层 in cards）
        if key == ".modal" and files == {"cards", "components"}:
            continue
        violations.append(f"{key} -> {sorted(files)}")
    assert not violations, f"选择器跨文件重复定义：{violations}"


def test_gate3_drawn_card_stage_only_in_cards_css(css_files):
    """③ .drawn-card-stage 只允许在 cards.css（Plan §2.2 显式修正项）。"""
    for name, css in css_files.items():
        if name == "cards":
            continue
        assert "drawn-card-stage" not in _strip_comments(css), (
            f"{name}.css 出现了 .drawn-card-stage —— 它唯一归属 cards.css"
        )
    assert "drawn-card-stage" in _strip_comments(css_files["cards"])


# ---------------------------------------------------------------------------
# 门禁 ④ 样式文件加载顺序
# ---------------------------------------------------------------------------


def test_gate4_css_link_order():
    """④ <link> 顺序 = theme→layout→components→features→cards→responsive。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    links = re.findall(r'href="/static/css/([a-z]+)\.css', html)
    assert links == CSS_ORDER, f"CSS <link> 顺序错误：{links}"


def test_gate4_theme_sync_script_before_css():
    """④ 主题早期同步脚本必须位于所有 CSS 之前（否则 FOUC）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    script_at = html.find("sal.theme")
    css_at = html.find("/static/css/theme.css")
    assert script_at != -1, "找不到主题早期同步脚本"
    assert css_at != -1, "找不到 CSS <link>"
    assert script_at < css_at, "主题早期同步脚本必须先于所有 CSS"


# ---------------------------------------------------------------------------
# 门禁 ⑤ 语义变量双向定义
# ---------------------------------------------------------------------------


def test_gate5_semantic_vars_defined_in_both_themes(css_files):
    """⑤ 9 个语义变量在 dark + light 两套主题都有定义。"""
    theme = css_files["theme"]
    dark = _var_defs(_block_body(theme, ":root {"))
    light = _var_defs(_block_body(theme, ':root[data-theme="light"]'))
    for var in SEMANTIC_VARS:
        assert var in dark, f"dark 主题缺少 {var}"
        assert var in light, f"light 主题缺少 {var}"


def test_gate5_dark_values_equal_original_literals(css_files):
    """⑤ dark 值逐字等于迁移前的原硬编码字面量（Dark 视觉不变）。"""
    dark = _var_defs(_block_body(css_files["theme"], ":root {"))
    for var, expected in EXPECTED_DARK.items():
        assert dark.get(var) == expected, (
            f"{var} 的 dark 值应为 {expected}（= 迁移前字面量），实际 {dark.get(var)}"
        )


def test_gate5_light_values_differ_from_dark(css_files):
    """⑤ light 值必须与 dark 不同（Light Mode 修复实际生效）。"""
    theme = css_files["theme"]
    dark = _var_defs(_block_body(theme, ":root {"))
    light = _var_defs(_block_body(theme, ':root[data-theme="light"]'))
    for var in SEMANTIC_VARS:
        assert light.get(var) != dark.get(var), f"{var} 的 light 值与 dark 相同"


# ---------------------------------------------------------------------------
# 门禁 ⑥ 源序等价性（覆盖对 + 共现）
# ---------------------------------------------------------------------------


def test_gate6_baseline_exists_with_declaration_pairs():
    """⑥ 基线必须存在且包含 declarationPairs。"""
    path = FIXTURES / "css_cascade_baseline.json"
    assert path.exists(), "缺少 tests/fixtures/css_cascade_baseline.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "declarationPairs" in data, "基线缺少 declarationPairs"
    assert len(data["declarationPairs"]) > 0


def test_gate6_no_utility_component_regression(css_files):
    """⑥ 工具类 × 组件类共现时，胜者不得改变（源序等价性）。"""
    # 复用 JS 侧脚本的结论：直接调用该脚本并断言其退出码为 0
    import subprocess

    script = ROOT / "scripts" / "check_layout_utility_conflicts.js"
    assert script.exists(), "缺少 scripts/check_layout_utility_conflicts.js"
    proc = subprocess.run(
        ["node", str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "布局工具类 / 组件类属性冲突扫描失败：\n" + proc.stdout + proc.stderr
    )


# ---------------------------------------------------------------------------
# 卡牌 Token 保护
# ---------------------------------------------------------------------------


def test_card_theme_vars_unchanged():
    """卡牌 8 变体的 --card-* 变量必须与迁移前基线逐字一致。"""
    path = FIXTURES / "card_theme_baseline.json"
    assert path.exists(), "缺少 tests/fixtures/card_theme_baseline.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))["cardThemeVars"]

    cards = _strip_comments(_read("cards.css"))
    current: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"\.task-card(?:\.(theme-[\w-]+))?\s*\{([^}]*)\}", cards):
        key = m.group(1) or "base"
        vars_found = {}
        for vm in re.finditer(r"(--card-[a-z-]+)\s*:\s*([^;]+);", m.group(2)):
            vars_found[vm.group(1)] = vm.group(2).strip()
        if vars_found:
            current.setdefault(key, {}).update(vars_found)

    assert set(current) == set(baseline), (
        f"卡牌变体集合改变：{sorted(set(current) ^ set(baseline))}"
    )
    for key, vars_found in baseline.items():
        for var, value in vars_found.items():
            assert current[key].get(var) == value, (
                f"卡牌变量 {key}.{var} 改变了：{value} → {current[key].get(var)}"
            )
