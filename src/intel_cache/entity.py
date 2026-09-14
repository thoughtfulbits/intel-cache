from __future__ import annotations

from .models import Entity
from .store import CacheStore


def upsert_entity(
    *,
    store: CacheStore,
    entity_id: str,
    display_name: str,
    aliases: list[str] | None = None,
    domains: list[str] | None = None,
    source_urls: list[str] | None = None,
) -> Entity:
    entity = Entity(
        id=entity_id,
        display_name=display_name,
        aliases=aliases or [],
        domains=domains or [],
        source_urls=source_urls or [],
    )
    return store.upsert_entity(entity)


def list_entities(store: CacheStore) -> list[Entity]:
    return store.list_entities()
