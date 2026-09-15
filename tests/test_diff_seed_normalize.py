import json

from intel_cache.diff import diff_blobs
from intel_cache.normalize import normalize_content, sha256_content
from intel_cache.seed import seed_directory
from intel_cache.store import CacheStore, source_key


def test_diff_uses_latest_two_cached_shas(tmp_path):
    store = CacheStore(tmp_path)
    seed_directory(store=store, directory="examples/acme")

    store.store_source_blob(
        entity_id="acme",
        url="https://example.com/acme/news",
        content=b"headline\nold detail\n",
    )
    store.store_source_blob(
        entity_id="acme",
        url="https://example.com/acme/news",
        content=b"headline\nnew detail\n",
    )

    output = diff_blobs(store=store, entity_id="acme")

    assert "-old detail" in output
    assert "+new detail" in output


def test_seed_directory_loads_entities_and_desks_directory(tmp_path):
    seed_root = tmp_path / "seed"
    desks_dir = seed_root / "desks"
    desks_dir.mkdir(parents=True)
    (seed_root / "entities.json").write_text(
        json.dumps(
            {
                "acme": {
                    "id": "acme",
                    "display_name": "Acme",
                    "source_urls": ["https://example.com/acme"],
                }
            }
        ),
        encoding="utf-8",
    )
    (desks_dir / "acme.json").write_text(
        json.dumps({"desk_id": "acme-desk", "entity_ids": ["acme"], "lanes": ["product"]}),
        encoding="utf-8",
    )
    store = CacheStore(tmp_path / "cache")

    assert seed_directory(store=store, directory=seed_root) == {
        "entities": 1,
        "subscriptions": 1,
    }
    assert store.get_entity("acme") is not None
    assert store.get_subscription("acme-desk") is not None


def test_tracking_query_params_do_not_change_source_key():
    assert source_key("https://Example.com/acme?utm_source=bot&a=1#section") == source_key(
        "https://example.com/acme?a=1"
    )


def test_normalized_hash_ignores_labeled_volatile_lines():
    first = b"title\nLast updated: 2026-01-01T00:00:00Z\nbody\n"
    second = b"title\r\nLast updated: 2026-02-01T00:00:00Z\r\nbody\r\n"

    assert normalize_content(first) == b"title\nLast updated: <volatile>\nbody\n"
    assert sha256_content(first, mode="normalized") == sha256_content(second, mode="normalized")
    assert sha256_content(first) != sha256_content(second)
