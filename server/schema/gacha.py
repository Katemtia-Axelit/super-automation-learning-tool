"""server.schema.gacha — gacha records + pool metadata.

Phase 1 does not own a CREATE TABLE for gacha (gacha is stateless: every
draw reads the `tasks` table). This module exists for two reasons:

  1. Forward-compatibility: when the user later adds gacha_records or
     task_publishes persistence (per plan §1.4), the new DDL will live here
     and `ensure_all()` will call it without touching other modules.
  2. Centralised import surface: business-domain imports for gacha
     features flow through `server.schema.gacha` rather than reaching into
     `backend_api.py`.

The legacy file's gacha helpers (`GachaPool`, `GachaSessionContext`,
`DrawResult`) are still in `backend_api.py` for Phase 1 — they migrate to
`server.services.gacha` in Phase 2.
"""
from __future__ import annotations

# Reserved for future persistence. Phase 1: no-op ensure.
def ensure_schema(conn) -> None:  # pragma: no cover
    return None