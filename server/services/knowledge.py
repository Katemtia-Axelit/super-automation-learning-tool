"""server.services.knowledge - vault walking + graph builder (Phase 2).

Owns the pure file-system logic for the knowledge domain:

- Category-id / category-name mappings (5 fixed subjects).
- Vault walking helpers (`_vault_rel_path`, `_note_category`, tag parsing).
- Wiki / markdown link resolvers.
- `build_vault_knowledge_graph(notes_dir)` — graph builder for
  `/api/knowledge/graph`.

Moved verbatim from `server.backend_api.py` L1667-1845 in Phase 2 Todo 5.
The 4 regexes (`_WIKI_LINK_RE` / `_MD_LINK_RE` / `_TAG_RE` /
`_FRONTMATTER_TAGS_RE`) are preserved module-level as in the original so
that future helpers added in this module can reuse them.

No Flask imports — usable from CLI / scripts / BP layer.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from server.repositories import note_index_repo


# =============================================================================
# Category mapping (5 fixed subjects)
# =============================================================================

_CATEGORY_ID_MAP: Dict[str, str] = {
    "高等数学": "math",
    "大学物理": "physics",
    "线性代数": "linear",
    "电子技术": "electronics",
    "计算机": "computer",
}

_CATEGORY_NAME_MAP: Dict[str, str] = {
    "math": "高等数学",
    "physics": "大学物理",
    "linear": "线性代数",
    "electronics": "电子技术",
    "computer": "计算机",
}


def get_category_id(subject: str) -> str:
    """Return category id (e.g. 'math') for a Chinese subject name."""
    return _CATEGORY_ID_MAP.get(subject, subject.lower())


def get_category_name(category_id: str) -> str:
    """Return Chinese subject name for a category id."""
    return _CATEGORY_NAME_MAP.get(category_id, category_id)


# =============================================================================
# Regex module-level (preserved verbatim from backend_api.py L1687-1690)
# =============================================================================

_WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
_TAG_RE = re.compile(r"(?:^|\s)#([^\s#/,]+)")
_FRONTMATTER_TAGS_RE = re.compile(r"^tags:\s*\[(.*?)\]", re.MULTILINE)


# =============================================================================
# Graph builder helpers (verbatim from backend_api.py L1692-1777)
# =============================================================================

def _wiki_link_target(raw: str) -> str:
    t = raw.strip()
    if "|" in t:
        t = t.split("|", 1)[0]
    if "#" in t:
        t = t.split("#", 1)[0]
    return t.strip()


def _vault_rel_path(root: str, full_path: str) -> str:
    rel = os.path.relpath(full_path, root).replace("\\", "/")
    return rel


def _note_category(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] == "知识点":
        return parts[1]
    if len(parts) >= 2:
        return parts[0]
    return "未分类"


def _parse_note_tags(content: str) -> List[str]:
    tags: List[str] = []
    fm = _FRONTMATTER_TAGS_RE.search(content[:800])
    if fm:
        tags.extend(
            t.strip().strip("\"'") for t in fm.group(1).split(",") if t.strip()
        )
    for m in _TAG_RE.finditer(content[:4000]):
        t = m.group(1).strip()
        if t and t not in tags:
            tags.append(t)
        if len(tags) >= 20:
            break
    return tags


def _resolve_wiki_target(
    target: str,
    current_rel: str,
    stem_index: Dict[str, List[str]],
    path_index: Dict[str, int],
) -> Optional[int]:
    target = target.strip().replace("\\", "/")
    if not target:
        return None
    if target.lower().endswith(".md"):
        target = target[:-3]
    if "/" in target:
        rel = target if target.endswith(".md") else target + ".md"
        return path_index.get(rel)
    cur_dir = os.path.dirname(current_rel).replace("\\", "/")
    if cur_dir:
        rel_try = f"{cur_dir}/{target}.md"
        if rel_try in path_index:
            return path_index[rel_try]
    stem = os.path.basename(target).lower()
    for rel in stem_index.get(stem, []):
        if rel in path_index:
            return path_index[rel]
    return None


def _resolve_md_link(
    href: str,
    current_rel: str,
    path_index: Dict[str, int],
) -> Optional[int]:
    href = href.strip().split("#")[0].strip()
    if not href or href.startswith(("http://", "https://", "mailto:")):
        return None
    if href.startswith("/"):
        rel = href.lstrip("/")
    else:
        cur_dir = os.path.dirname(current_rel).replace("\\", "/")
        rel = os.path.normpath(os.path.join(cur_dir, href)).replace("\\", "/")
    if not rel.lower().endswith(".md"):
        rel += ".md"
    return path_index.get(rel)


def _extract_links_from_content(
    content: str,
    source_id: int,
    current_rel: str,
    stem_index: Dict[str, List[str]],
    path_index: Dict[str, int],
) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    seen: set = set()
    for m in _WIKI_LINK_RE.finditer(content):
        tid = _resolve_wiki_target(
            _wiki_link_target(m.group(1)),
            current_rel,
            stem_index,
            path_index,
        )
        if tid is None or tid == source_id:
            continue
        key = (source_id, tid, "wiki_link")
        if key not in seen:
            seen.add(key)
            links.append({"source": source_id, "target": tid, "type": "wiki_link"})
    for m in _MD_LINK_RE.finditer(content):
        tid = _resolve_md_link(m.group(2), current_rel, path_index)
        if tid is None or tid == source_id:
            continue
        key = (source_id, tid, "markdown_link")
        if key not in seen:
            seen.add(key)
            links.append(
                {"source": source_id, "target": tid, "type": "markdown_link"}
            )
    return links


# =============================================================================
# Graph builder (verbatim from backend_api.py L1779-1845, now parameterised)
# =============================================================================

def build_vault_knowledge_graph(notes_dir: str) -> Dict[str, Any]:
    """Scan vault Markdown and build a knowledge graph from real links.

    Returns ``{"nodes": [...], "links": [...], "categories": [...]}``.
    Mirrors `backend_api.build_vault_knowledge_graph()` but takes the vault
    root as an argument so the function is callable from the BP layer
    via `current_app.config["_notes_dir"]`.
    """
    nodes: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []
    categories: List[str] = []
    category_set: set = set()
    if not notes_dir or not os.path.isdir(notes_dir):
        return {"nodes": nodes, "links": links, "categories": categories}

    md_files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(notes_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".md") and not fn.startswith("."):
                md_files.append(os.path.join(dirpath, fn))

    path_index: Dict[str, int] = {}
    stem_index: Dict[str, List[str]] = {}
    file_meta: List[Dict[str, Any]] = []

    for idx, full in enumerate(sorted(md_files)):
        rel = _vault_rel_path(notes_dir, full)
        rel_md = rel if rel.endswith(".md") else rel + ".md"
        path_index[rel_md] = idx
        stem = os.path.splitext(os.path.basename(rel_md))[0].lower()
        stem_index.setdefault(stem, []).append(rel_md)
        title = os.path.splitext(os.path.basename(rel_md))[0]
        category = _note_category(rel_md)
        if category not in category_set:
            category_set.add(category)
            categories.append(category)
        try:
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            content = ""
        tags = _parse_note_tags(content)
        file_meta.append(
            {
                "id": idx,
                "title": title,
                "name": title,
                "path": rel_md,
                "category": category,
                "tags": tags,
                "content": content,
                "rel": rel_md,
            }
        )

    link_seen: set = set()
    for meta in file_meta:
        nodes.append(
            {
                "id": meta["id"],
                "title": meta["title"],
                "name": meta["title"],
                "path": meta["path"],
                "category": meta["category"],
                "tags": meta["tags"],
            }
        )
        for link in _extract_links_from_content(
            meta["content"], meta["id"], meta["rel"], stem_index, path_index
        ):
            key = (link["source"], link["target"], link["type"])
            if key not in link_seen:
                link_seen.add(key)
                links.append(link)

    return {"nodes": nodes, "links": links, "categories": categories}


# =============================================================================
# Higher-level service functions used by the BP layer
# =============================================================================

def list_categories(notes_dir: str) -> List[Dict[str, Any]]:
    """Return the 5 fixed knowledge categories with current `.md` counts."""
    return note_index_repo.list_categories(notes_dir)


def list_points(notes_dir: str, category: str = "all") -> List[Dict[str, Any]]:
    """Return knowledge points (one entry per `.md` file).

    Mirrors `api_get_knowledge_points` (L1631-1665):
    - `category == 'all'` walks every subject directory under `知识点/`.
    - Otherwise resolves the category id → Chinese name and lists only
      that subject's `.md` files.
    """
    if not notes_dir:
        return []

    points: List[Dict[str, Any]] = []
    base_path = os.path.join(notes_dir, "知识点")
    if not os.path.isdir(base_path):
        return points

    if category == "all":
        for subject in os.listdir(base_path):
            subject_path = os.path.join(base_path, subject)
            if os.path.isdir(subject_path):
                for filename in os.listdir(subject_path):
                    if filename.endswith(".md"):
                        name = filename[:-3]
                        points.append(
                            {
                                "id": name,
                                "name": name,
                                "category": subject,
                                "category_id": get_category_id(subject),
                            }
                        )
    else:
        category_name = get_category_name(category)
        category_path = os.path.join(base_path, category_name)
        if os.path.exists(category_path):
            for filename in os.listdir(category_path):
                if filename.endswith(".md"):
                    name = filename[:-3]
                    points.append(
                        {
                            "id": name,
                            "name": name,
                            "category": category_name,
                            "category_id": category,
                        }
                    )

    return points


def _resolve_md_path(notes_dir: str, note_path: str) -> str:
    """Resolve a vault-relative note path to an absolute `.md` path.

    Appends `.md` if not present. Mirrors backend_api.py L1852-1855 / 1894-1897.
    """
    full_path = os.path.join(notes_dir, note_path)
    if not full_path.endswith(".md"):
        full_path += ".md"
    return full_path


def read_note(notes_dir: str, note_path: str) -> Optional[str]:
    """Read a single vault note (relative to `notes_dir`).

    Returns the UTF-8 contents or ``None`` if the file is missing.
    """
    full_path = _resolve_md_path(notes_dir, note_path)
    if not os.path.exists(full_path):
        return None
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def read_point_detail(
    notes_dir: str, subject: str, point_name: str
) -> Optional[str]:
    """Read a knowledge point's markdown content.

    Mirrors `api_get_knowledge_point_detail` (L1906-1919).
    Path layout: `<notes_dir>/知识点/<subject>/<point_name>.md`.
    """
    point_path = os.path.join(notes_dir, "知识点", subject, f"{point_name}.md")
    if not os.path.exists(point_path):
        return None
    with open(point_path, "r", encoding="utf-8") as f:
        return f.read()


def list_notes(notes_dir: str) -> List[Dict[str, Any]]:
    """List notes at vault root (one level deep).

    Mirrors `api_get_notes` (L1874-1891).
    """
    notes: List[Dict[str, Any]] = []
    if not notes_dir or not os.path.isdir(notes_dir):
        return notes

    for subject in os.listdir(notes_dir):
        subject_path = os.path.join(notes_dir, subject)
        if os.path.isdir(subject_path) and not subject.startswith("."):
            for filename in os.listdir(subject_path):
                if filename.endswith(".md"):
                    name = filename[:-3]
                    notes.append(
                        {
                            "id": f"{subject}/{name}",
                            "name": name,
                            "category": subject,
                            "path": f"{subject}/{filename}",
                        }
                    )
    return notes


__all__ = [
    "get_category_id",
    "get_category_name",
    "list_categories",
    "list_points",
    "read_note",
    "read_point_detail",
    "list_notes",
    "build_vault_knowledge_graph",
]