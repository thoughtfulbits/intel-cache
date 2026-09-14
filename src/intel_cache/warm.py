from __future__ import annotations

from .fetch import fetch_entity
from .models import FetchResult
from .store import CacheStore


def warm_entities(
    *,
    store: CacheStore,
    entity_ids: list[str],
    timeout: float = 20.0,
) -> list[FetchResult]:
    results: list[FetchResult] = []
    for entity_id in entity_ids:
        results.extend(fetch_entity(store=store, entity_id=entity_id, timeout=timeout))
    return results


def warm_desk(*, store: CacheStore, desk_id: str, timeout: float = 20.0) -> list[FetchResult]:
    subscription = store.get_subscription(desk_id)
    if subscription is None:
        raise KeyError(f"unknown desk subscription: {desk_id}")
    return warm_entities(store=store, entity_ids=subscription.entity_ids, timeout=timeout)


def warm_all(*, store: CacheStore, timeout: float = 20.0) -> list[FetchResult]:
    return warm_entities(
        store=store,
        entity_ids=[entity.id for entity in store.list_entities()],
        timeout=timeout,
    )
