"""AR03-P4 —— Theme / Light Mode 收敛契约测试（characterization）。

对应 Plan §3.3 / §3.4 的 A–H 分类审计结论与 Plan §4.3 的验收断言：

- 7 处白色低透明度 hover / 边框 → 语义化变量
- 11 处金色强调交互态 → --accent-veil* 语义化变量
- 3 处金色徽标底 → --accent-veil-chip
- 危险操作底 → --danger-veil
- Light 主题下这些交互态必须**可见**（不再是白底白）
- 卡牌画布内的白 / 黑低透明度**一律不动**（深色设计语言保护）
- prefers-reduced-motion 不破坏抽卡 / 完成 / 弃牌状态机

**只读**：不修改任何生产文件。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CSS_DIR = ROOT / "static" / "css"
INDEX_HTML = ROOT / "src" / "index.html"
CSS_ORDER = ["theme", "layout", "components", "features", "cards", "responsive"]


def _read(name: str) -> str:
    return (CSS_DIR / name).read_text(encoding="utf-8")


def _strip_comments(css: str) -> str:
    css = re.sub(r"<!--[\s\S]*?-->", "", css)
    return re.sub(r"/\*[\s\S]*?\*/", "", css)


def _all_css() -> str:
    return "\n".join(_strip_comments(_read(f"{n}.css")) for n in CSS_ORDER)


def _rule_body(css: str, selector: str) -> str:
    """取出某个选择器规则块的声明体（取第一次出现）。

    选择器文本可能跨行（如 `button.gacha-multi-item:hover,\\n.gacha-multi-item:hover`），
    因此先做空白归一化再匹配。
    """
    masked = _strip_comments(css)
    # 归一化：把所有空白（含换行）压成单个空格，便于跨行选择器匹配
    flat = re.sub(r"\s+", " ", masked)
    flat_selector = re.sub(r"\s+", " ", selector)
    idx = flat.find(flat_selector)
    assert idx != -1, f"找不到选择器 {selector}"
    brace = flat.find("{", idx)
    depth = 0
    for j in range(brace, len(flat)):
        if flat[j] == "{":
            depth += 1
        elif flat[j] == "}":
            depth -= 1
            if depth == 0:
                return flat[brace + 1 : j]
    raise AssertionError(f"{selector} 未闭合")


@pytest.fixture(scope="module")
def all_css() -> str:
    return _all_css()


# ---------------------------------------------------------------------------
# C 类：白色低透明度 hover / 边框（7 处）
# ---------------------------------------------------------------------------

#: 选择器 → 必须使用的语义变量。
HOVER_VEIL_EXPECTATIONS = {
    ".nav-btn:hover": "--hover-veil",
    ".card:hover": "--hover-veil-strong",
    ".sched-slot:hover": "--hover-veil-subtle",
    ".cat-item:hover": "--hover-veil-subtle",
    ".note-item:hover": "--hover-veil-subtle",
    ".prompt-file-item:hover, .prompt-file-item.active": "--active-veil",
    ".agent-ro-item:hover, .agent-ro-item.active": "--active-veil",
}


@pytest.mark.parametrize("selector,var", sorted(HOVER_VEIL_EXPECTATIONS.items()))
def test_c_class_hover_uses_semantic_var(all_css, selector, var):
    """C 类：7 处 hover / 边框改用语义化变量，不再硬编码白色低透明度。"""
    body = _rule_body(all_css, selector)
    assert f"var({var})" in body, f"{selector} 应使用 var({var})"
    assert "rgba(255,255,255,0.0" not in body, (
        f"{selector} 仍含硬编码白色低透明度 → Light Mode 下不可见"
    )


# ---------------------------------------------------------------------------
# B 类：金色强调交互态（8 处）+ 金色徽标底（3 处）
# ---------------------------------------------------------------------------

ACCENT_EXPECTATIONS = {
    ".nav-btn.active": "--accent-veil",
    ".cat-item.active": "--accent-veil",
    ".feedback-emoji button:hover, .feedback-emoji button.sel": "--accent-veil",
    ".feedback-option:hover, .feedback-option.sel": "--accent-veil-soft",
    ".agent-ro-tab.active": "--accent-veil",
    ".replace-reason input:checked + label": "--accent-veil-chip",
    "button.gacha-multi-item:hover, .gacha-multi-item:hover": "--accent-veil-soft",
    'button.gacha-multi-item[aria-pressed="true"], .gacha-multi-item.activated': (
        "--accent-veil-strong"
    ),
}

CHIP_EXPECTATIONS = {
    ".bg-gold": "--accent-veil-chip",
    ".tag-chip": "--accent-veil-chip",
    ".gacha-multi-item-tag": "--accent-veil-chip",
}


@pytest.mark.parametrize("selector,var", sorted(ACCENT_EXPECTATIONS.items()))
def test_b_class_accent_uses_semantic_var(all_css, selector, var):
    """B 类：11 处金色强调交互态改用 --accent-veil* 语义化变量。"""
    body = _rule_body(all_css, selector)
    assert f"var({var})" in body, f"{selector} 应使用 var({var})"
    assert "rgba(240,192,64,0.1" not in body, f"{selector} 仍硬编码金色低透明度"


@pytest.mark.parametrize("selector,var", sorted(CHIP_EXPECTATIONS.items()))
def test_b_class_chip_uses_accent_veil_chip(all_css, selector, var):
    """B 类：3 处金色徽标底改用 --accent-veil-chip。"""
    body = _rule_body(all_css, selector)
    assert f"var({var})" in body, f"{selector} 应使用 var({var})"
    assert "rgba(240,192,64,0.15" not in body, f"{selector} 仍硬编码金色徽标底"


# ---------------------------------------------------------------------------
# D 类：危险操作底
# ---------------------------------------------------------------------------


def test_d_class_danger_uses_semantic_var(all_css):
    """D 类：危险操作底改用 --danger-veil。"""
    body = _rule_body(all_css, ".btn.danger")
    assert "var(--danger-veil)" in body
    assert "rgba(231,76,60,0.1" not in body


# ---------------------------------------------------------------------------
# Light Mode 可见性（语义变量的 light 值必须"可见"）
# ---------------------------------------------------------------------------


def test_light_mode_hover_veils_are_visible():
    """Light Mode：hover 底必须是**黑色**低透明度（白底上白色不可见）。"""
    theme = _read("theme.css")
    light_body = _rule_body(theme, ':root[data-theme="light"]')
    for var in ("--hover-veil", "--hover-veil-subtle", "--hover-veil-strong", "--active-veil"):
        m = re.search(rf"{re.escape(var)}\s*:\s*([^;]+);", light_body)
        assert m, f"light 主题缺少 {var}"
        value = m.group(1).strip()
        assert value.startswith("rgba(0,0,0"), (
            f"{var} 的 light 值 {value} 应为黑色低透明度（白底上白色不可见）"
        )
        alpha = float(value.split(",")[3].rstrip(")"))
        assert 0.02 <= alpha <= 0.2, f"{var} 的 light 透明度 {alpha} 不在可读区间"


def test_light_mode_accent_veils_are_visible():
    """Light Mode：金色强调底必须足够深（浅金在白底上对比不足）。"""
    theme = _read("theme.css")
    light_body = _rule_body(theme, ':root[data-theme="light"]')
    for var in (
        "--accent-veil",
        "--accent-veil-soft",
        "--accent-veil-strong",
        "--accent-veil-chip",
    ):
        m = re.search(rf"{re.escape(var)}\s*:\s*([^;]+);", light_body)
        assert m, f"light 主题缺少 {var}"
        value = m.group(1).strip()
        alpha = float(value.split(",")[3].rstrip(")"))
        assert alpha >= 0.12, f"{var} 的 light 透明度 {alpha} 过低，在浅色底上不可见"


# ---------------------------------------------------------------------------
# 卡牌深色设计语言保护
# ---------------------------------------------------------------------------

#: 卡牌画布内的选择器前缀 —— 其中的白色 / 黑色低透明度**一律不动**。
CARD_CANVAS_PREFIXES = (
    ".task-card",
    ".task-card-front",
    ".task-card-back",
    ".task-card-inner",
    ".task-card-face",
    ".drawn-card",
    ".card-deck",
    ".discard-",
    ".flying-card",
    ".card-fly-layer",
)


def test_card_canvas_does_not_use_theme_veil_vars():
    """卡牌画布内**不得**使用全局交互遮罩变量（保持独立深色设计语言）。"""
    cards = _strip_comments(_read("cards.css"))
    for var in (
        "--hover-veil",
        "--hover-veil-subtle",
        "--hover-veil-strong",
        "--active-veil",
        "--accent-veil",
        "--accent-veil-soft",
        "--accent-veil-strong",
        "--accent-veil-chip",
        "--danger-veil",
    ):
        assert f"var({var})" not in cards, (
            f"cards.css 使用了全局语义变量 {var} → 卡牌深色设计语言被全局主题污染"
        )


def test_card_deep_dark_backgrounds_preserved():
    """卡牌底色仍是深色渐变（不被浅色主题重映射）。"""
    cards = _strip_comments(_read("cards.css"))
    assert "--card-bg: linear-gradient(145deg, #121a32, #1a2848)" in cards, (
        "math 变体的 --card-bg 改变了 → 卡牌深色设计语言被破坏"
    )
    assert "--card-bg: linear-gradient(145deg, #0e1418, #152028)" in cards, (
        "code 变体的 --card-bg 改变了"
    )


def test_light_theme_does_not_remap_card_tokens():
    """:root[data-theme=light] 不得重映射任何 --card-* 变量。"""
    theme = _read("theme.css")
    light_body = _rule_body(theme, ':root[data-theme="light"]')
    assert "--card-" not in light_body, "light 主题重映射了卡牌变量 → 破坏深色设计语言"


# ---------------------------------------------------------------------------
# prefers-reduced-motion（不得破坏状态机）
# ---------------------------------------------------------------------------


def test_reduced_motion_uses_duration_not_none():
    """reduced-motion 用 animation-duration，不用 animation: none。

    `animation: none` 会让元素不再派发 animationend 事件 → 可能破坏未来的
    动画态监听。改用 0.01ms 保留事件派发能力。
    """
    responsive = _read("responsive.css")
    body = _rule_body(responsive, "@media (prefers-reduced-motion: reduce)")
    assert "animation-duration: 0.01ms" in body, "reduced-motion 未设置 animation-duration"
    assert "animation: none" not in body, (
        "reduced-motion 不得用 animation: none（会丢失 animationend 派发）"
    )
    assert "transition-duration: 0.01ms" in body


def test_reduced_motion_restores_pointer_events():
    """6 个带 pointer-events:none 的动画态必须在 reduced-motion 下恢复交互。"""
    responsive = _read("responsive.css")
    body = _rule_body(responsive, "@media (prefers-reduced-motion: reduce)")
    for cls in (
        ".task-card.is-evaporating",
        ".task-card.is-fly-to-pile",
        ".task-card.is-discarding",
        ".task-card.is-skipping",
        ".task-card.is-refusing",
        ".task-card.is-burning",
    ):
        assert cls in body, f"reduced-motion 未覆盖 {cls}"
    assert "pointer-events: auto !important" in body


def test_no_animation_event_listeners_in_frontend():
    """前端**零** animationend / transitionend 监听器。

    → 动画状态转换全部由 setTimeout / rAF 驱动，与 CSS 动画时长解耦，
       reduced-motion 压缩时长不会打断抽卡 / 完成 / 弃牌状态机。
    """
    static_dir = ROOT / "static"
    offenders = []
    for path in static_dir.rglob("*.js"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "animationend" in text or "transitionend" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"发现动画事件监听器（会与 reduced-motion 冲突）：{offenders}"


def test_frontend_uses_timeout_or_raf_for_card_animations():
    """卡牌动画的状态推进由 setTimeout / rAF 驱动（而非 CSS 事件）。"""
    app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8", errors="ignore")
    assert "setTimeout" in app_js
    assert "requestAnimationFrame" in app_js or "rAF" in app_js


# ---------------------------------------------------------------------------
# prefers-contrast
# ---------------------------------------------------------------------------


def test_prefers_contrast_enhances_only_border():
    """prefers-contrast 只增强 --border（不引入第二个边框变量）。"""
    theme = _read("theme.css")
    body = _rule_body(theme, "@media (prefers-contrast: more)")
    assert "--border:" in body, "prefers-contrast 未增强 --border"
    assert "--border-strong" not in _strip_comments(theme), (
        "不得引入 --border-strong（制造第二个边框变量 → Token 权威歧义）"
    )
    assert "--card-border" not in body, "prefers-contrast 不得改卡牌边框"


def test_prefers_contrast_lives_in_theme_css():
    """:root 的重映射归 theme.css 所有（全局主题 Token 唯一权威）。"""
    theme = _read("theme.css")
    assert "@media (prefers-contrast: more)" in theme
    responsive = _read("responsive.css")
    assert ":root" not in _strip_comments(responsive), (
        "responsive.css 不得定义 :root（全局 Token 只能在 theme.css）"
    )
