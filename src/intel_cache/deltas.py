from __future__ import annotations

from .models import Delta
from .store import CacheStore


def list_deltas(
    *,
    store: CacheStore,
    since: str | None = None,
    desk_id: str | None = None,
    lane: str | None = None,
    entity_id: str | None = None,
) -> list[Delta]:
    return store.list_deltas(since=since, desk_id=desk_id, lane=lane, entity_id=entity_id)
