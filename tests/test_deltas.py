from intel_cache.deltas import list_deltas
from intel_cache.entity import upsert_entity
from intel_cache.store import CacheStore
from intel_cache.subscribe import subscribe_desk


def test_deltas_filter_by_desk_lane_entity_and_since(tmp_path):
    store = CacheStore(tmp_path)
    upsert_entity(store=store, entity_id="acme", display_name="Acme")
    upsert_entity(store=store, entity_id="competitor-a", display_name="Competitor A")
    subscribe_desk(
        store=store,
        desk_id="acme-desk",
        entity_ids=["acme"],
        lanes=["product"],
    )

    acme_delta = store.store_source_blob(
        entity_id="acme",
        url="https://example.com/acme",
        content=b"acme body",
    )
    store.store_source_blob(
        entity_id="competitor-a",
        url="https://example.com/competitor-a",
        content=b"competitor body",
    )

    desk_deltas = list_deltas(store=store, desk_id="acme-desk", lane="product", since="2000-01-01T00:00:00Z")
    assert [delta.entity_id for delta in desk_deltas] == ["acme"]
    assert desk_deltas[0].sha256 == acme_delta.sha256

    assert list_deltas(store=store, desk_id="acme-desk", lane="people") == []
    assert [delta.entity_id for delta in list_deltas(store=store, entity_id="competitor-a")] == ["competitor-a"]
    assert list_deltas(store=store, since="9999-01-01T00:00:00Z") == []
