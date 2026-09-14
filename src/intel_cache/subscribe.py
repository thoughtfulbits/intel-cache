from __future__ import annotations

from .models import DeskSubscription
from .store import CacheStore


def subscribe_desk(
    *,
    store: CacheStore,
    desk_id: str,
    entity_ids: list[str],
    lanes: list[str],
) -> DeskSubscription:
    subscription = DeskSubscription(desk_id=desk_id, entity_ids=entity_ids, lanes=lanes)
    return store.upsert_subscription(subscription)


def list_subscriptions(store: CacheStore) -> list[DeskSubscription]:
    return store.list_subscriptions()
