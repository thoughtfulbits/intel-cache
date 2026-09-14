from intel_cache.entity import upsert_entity
from intel_cache.fetch import fetch_source
from intel_cache.store import CacheStore


def test_fetch_source_reports_hash_changes(monkeypatch, tmp_path):
    store = CacheStore(tmp_path)
    upsert_entity(
        store=store,
        entity_id="acme",
        display_name="Acme",
        source_urls=["https://example.com/acme"],
    )
    payloads = [b"first body", b"first body", b"second body"]

    def fake_fetch_url(url, *, timeout=20.0):
        assert url == "https://example.com/acme"
        return payloads.pop(0)

    monkeypatch.setattr("intel_cache.fetch.fetch_url", fake_fetch_url)

    first = fetch_source(store=store, entity_id="acme", url="https://example.com/acme")
    second = fetch_source(store=store, entity_id="acme", url="https://example.com/acme")
    third = fetch_source(store=store, entity_id="acme", url="https://example.com/acme")

    assert first.changed is True
    assert first.previous_sha256 is None
    assert second.changed is False
    assert second.sha256 == first.sha256
    assert third.changed is True
    assert third.previous_sha256 == first.sha256
    assert third.sha256 != first.sha256
    assert len(store.list_deltas(entity_id="acme")) == 2
