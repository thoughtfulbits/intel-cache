import pytest

from intel_cache.entity import upsert_entity
from intel_cache.subscribe import subscribe_desk
from intel_cache.store import CacheStore


def test_subscribe_desk_persists_entities_and_lanes(tmp_path):
    store = CacheStore(tmp_path)
    upsert_entity(store=store, entity_id="acme", display_name="Acme")
    upsert_entity(store=store, entity_id="competitor-a", display_name="Competitor A")

    subscription = subscribe_desk(
        store=store,
        desk_id="Acme-Desk",
        entity_ids=["acme", "competitor-a", "acme"],
        lanes=["product", "marketing", "product"],
    )

    assert subscription.desk_id == "acme-desk"
    assert subscription.entity_ids == ["acme", "competitor-a"]
    assert subscription.lanes == ["product", "marketing"]
    assert store.get_subscription("acme-desk") == subscription


def test_subscribe_rejects_unknown_entities(tmp_path):
    store = CacheStore(tmp_path)

    with pytest.raises(KeyError):
        subscribe_desk(store=store, desk_id="desk", entity_ids=["missing"], lanes=["product"])


def test_subscribe_rejects_unknown_lanes(tmp_path):
    store = CacheStore(tmp_path)
    upsert_entity(store=store, entity_id="acme", display_name="Acme")

    with pytest.raises(ValueError):
        subscribe_desk(store=store, desk_id="desk", entity_ids=["acme"], lanes=["finance"])
