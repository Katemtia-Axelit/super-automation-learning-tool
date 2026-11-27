"""server.utils.wiki_link — Obsidian ``[[双链]]`` 解析（公开工具门面）。

AR03-P2 / Stage 7
-----------------
此前本模块是 **转发壳**，指向 legacy ``backend_api._extract_links_from_content``
/ ``_resolve_md_link``。但那两份实现 **早已被注释掉**（P1 搬到
:mod:`server.services.knowledge`），因此转发在运行期会抛
``ImportError`` —— 是一条 **死路**。

Stage 7 把它指向 **真正的 owner**：:mod:`server.services.knowledge`。

⚠️ 签名差异（必须如实记录）
--------------------------
legacy 的 ``_extract_links_from_content`` 需要 **5 个** 参数
（``content`` / ``source_id`` / ``current_rel`` / ``stem_index`` /
``path_index``），且返回 **dict 列表**（不是 ``(target, offset)`` 元组）。
旧的 ``server.utils.wiki_link.extract_links`` 门面签名与实现 **都对不上**
（既没有 ``path_index``，返回类型也写错了），因此 **从无生产调用方**。

Stage 7 保留同名函数，但把签名改成与真正 owner 一致，并 **新增**
``extract_links_from_content`` 作为规范入口。旧的 ``resolve_md_link``
两参数版本无法在缺少 ``path_index`` 的情况下正确解析，改为显式要求
完整的索引参数 —— **宁可报错，也不要给出错误答案**。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = [
    "extract_links_from_content",
    "resolve_md_link",
    "wiki_link_target",
]


def wiki_link_target(raw: str) -> str:
    """提取 ``[[双链]]`` 的目标文本（去掉别名与锚点）。"""
    from server.services.knowledge import _wiki_link_target as _impl

    return _impl(raw)


def resolve_md_link(
    href: str,
    current_rel: str,
    path_index: Dict[str, int],
) -> Optional[int]:
    """把 Markdown 相对链接解析成 vault 内的节点 id。

    委托给 :func:`server.services.knowledge._resolve_md_link`。
    """
    from server.services.knowledge import _resolve_md_link as _impl

    return _impl(href, current_rel, path_index)


def extract_links_from_content(
    content: str,
    source_id: int,
    current_rel: str,
    stem_index: Dict[str, List[str]],
    path_index: Dict[str, int],
) -> List[Dict[str, Any]]:
    """从笔记正文抽取所有出链。

    委托给 :func:`server.services.knowledge._extract_links_from_content`。
    """
    from server.services.knowledge import _extract_links_from_content as _impl

    return _impl(content, source_id, current_rel, stem_index, path_index)
