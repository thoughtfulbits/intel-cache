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


def list_unacked_deltas(
    *,
    store: CacheStore,
    desk_id: str,
    lane: str,
    since: str | None = None,
    entity_id: str | None = None,
) -> list[Delta]:
    watermark = store.get_delta_watermark(desk_id=desk_id, lane=lane)
    deltas = store.list_deltas(
        since=since,
        desk_id=desk_id,
        lane=lane,
        entity_id=entity_id,
    )
    if watermark is None:
        return deltas
    return [delta for delta in deltas if delta.changed_at > watermark]


def ack_deltas(
    *,
    store: CacheStore,
    desk_id: str,
    lane: str,
    deltas: list[Delta],
) -> str | None:
    if not deltas:
        return store.get_delta_watermark(desk_id=desk_id, lane=lane)
    changed_at = max(delta.changed_at for delta in deltas)
    store.set_delta_watermark(desk_id=desk_id, lane=lane, changed_at=changed_at)
    return changed_at
