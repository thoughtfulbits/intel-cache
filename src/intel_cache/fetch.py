from __future__ import annotations

import os
import urllib.request

from .models import FetchResult
from .store import CacheStore


USER_AGENT = "intel-cache/0.1"


def fetch_url(url: str, *, timeout: float = 20.0) -> bytes:
    mode = os.environ.get("INTEL_CACHE_FETCH", "http").strip().lower()
    if mode != "http":
        raise RuntimeError("fetching is disabled unless INTEL_CACHE_FETCH=http")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_source(
    *,
    store: CacheStore,
    entity_id: str,
    url: str,
    timeout: float = 20.0,
) -> FetchResult:
    content = fetch_url(url, timeout=timeout)
    return store.store_source_blob(entity_id=entity_id, url=url, content=content)


def fetch_entity(
    *,
    store: CacheStore,
    entity_id: str,
    timeout: float = 20.0,
) -> list[FetchResult]:
    entity = store.require_entity(entity_id)
    return [
        fetch_source(store=store, entity_id=entity.id, url=url, timeout=timeout)
        for url in entity.source_urls
    ]
