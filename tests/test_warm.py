from intel_cache.entity import upsert_entity
from intel_cache.models import FetchFailure, FetchResult
from intel_cache.store import CacheStore
from intel_cache.warm import summarize_warm, warm_all


def test_warm_continues_after_url_failure(monkeypatch, tmp_path):
    store = CacheStore(tmp_path)
    upsert_entity(
        store=store,
        entity_id="acme",
        display_name="Acme",
        source_urls=["https://example.com/acme"],
    )
    upsert_entity(
        store=store,
        entity_id="competitor-a",
        display_name="Competitor A",
        source_urls=["https://example.com/fail"],
    )

    def fake_fetch_url(url, *, timeout=20.0):
        if url.endswith("/fail"):
            raise OSError("network down")
        return b"acme body"

    monkeypatch.setattr("intel_cache.warm.fetch_url", fake_fetch_url)

    results = warm_all(store=store, concurrency=2)

    assert isinstance(results[0], FetchResult)
    assert results[0].changed is True
    assert isinstance(results[1], FetchFailure)
    assert "network down" in results[1].error
    assert summarize_warm(results) == {
        "changed": 1,
        "unchanged": 0,
        "failed": 1,
        "total": 2,
    }
