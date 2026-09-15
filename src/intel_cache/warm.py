from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .fetch import default_hash_mode, fetch_url
from .models import FetchFailure, FetchResult, normalize_id, utc_now_iso
from .store import CacheStore
from .store import source_key


WarmResult = FetchResult | FetchFailure


def warm_entities(
    *,
    store: CacheStore,
    entity_ids: list[str],
    timeout: float = 20.0,
    concurrency: int = 4,
    hash_mode: str | None = None,
) -> list[WarmResult]:
    sources: list[tuple[str, str]] = []
    seen_entities: set[str] = set()
    for entity_id in entity_ids:
        normalized = normalize_id(entity_id)
        if normalized in seen_entities:
            continue
        seen_entities.add(normalized)
        entity = store.require_entity(normalized)
        sources.extend((entity.id, url) for url in entity.source_urls)

    if not sources:
        return []

    workers = max(1, concurrency)
    fetch_results: list[bytes | BaseException] = [b""] * len(sources)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_indexes = {
            executor.submit(fetch_url, url, timeout=timeout): index
            for index, (_, url) in enumerate(sources)
        }
        for future, index in future_indexes.items():
            try:
                fetch_results[index] = future.result()
            except BaseException as exc:  # noqa: BLE001 - failures become structured rows.
                fetch_results[index] = exc

    mode = hash_mode or default_hash_mode()
    results: list[WarmResult] = []
    for (entity_id, url), value in zip(sources, fetch_results, strict=True):
        if isinstance(value, BaseException):
            results.append(
                FetchFailure(
                    entity_id=entity_id,
                    url=url,
                    source_key=source_key(url),
                    error=f"{type(value).__name__}: {value}",
                    fetched_at=utc_now_iso(),
                )
            )
            continue
        results.append(
            store.store_source_blob(
                entity_id=entity_id,
                url=url,
                content=value,
                hash_mode=mode,
            )
        )
    return results


def warm_desk(
    *,
    store: CacheStore,
    desk_id: str,
    timeout: float = 20.0,
    concurrency: int = 4,
    hash_mode: str | None = None,
) -> list[WarmResult]:
    subscription = store.get_subscription(desk_id)
    if subscription is None:
        raise KeyError(f"unknown desk subscription: {desk_id}")
    return warm_entities(
        store=store,
        entity_ids=subscription.entity_ids,
        timeout=timeout,
        concurrency=concurrency,
        hash_mode=hash_mode,
    )


def warm_all(
    *,
    store: CacheStore,
    timeout: float = 20.0,
    concurrency: int = 4,
    hash_mode: str | None = None,
) -> list[WarmResult]:
    return warm_entities(
        store=store,
        entity_ids=[entity.id for entity in store.list_entities()],
        timeout=timeout,
        concurrency=concurrency,
        hash_mode=hash_mode,
    )


def summarize_warm(results: list[WarmResult]) -> dict[str, int]:
    changed = sum(1 for result in results if isinstance(result, FetchResult) and result.changed)
    unchanged = sum(1 for result in results if isinstance(result, FetchResult) and not result.changed)
    failed = sum(1 for result in results if isinstance(result, FetchFailure))
    return {
        "changed": changed,
        "unchanged": unchanged,
        "failed": failed,
        "total": len(results),
    }
