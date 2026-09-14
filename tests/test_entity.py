from intel_cache.entity import upsert_entity
from intel_cache.store import CacheStore


def test_entity_upsert_deduplicates_and_persists(tmp_path):
    store = CacheStore(tmp_path)

    entity = upsert_entity(
        store=store,
        entity_id="Acme",
        display_name="Acme",
        aliases=["Acme Inc.", "Acme Inc.", ""],
        domains=["ACME.example", "acme.example"],
        source_urls=["https://example.com/acme", "https://example.com/acme"],
    )

    assert entity.id == "acme"
    assert entity.aliases == ["Acme Inc."]
    assert entity.domains == ["acme.example"]
    assert entity.source_urls == ["https://example.com/acme"]
    assert store.get_entity("acme") == entity
