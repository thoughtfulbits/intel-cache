from intel_cache.cli import main
from intel_cache.entity import upsert_entity
from intel_cache.store import CacheStore
from intel_cache.subscribe import subscribe_desk


def _seed_changed_source(tmp_path):
    store = CacheStore(tmp_path)
    upsert_entity(
        store=store,
        entity_id="acme",
        display_name="Acme",
        source_urls=["https://example.com/acme"],
    )
    subscribe_desk(store=store, desk_id="acme-desk", entity_ids=["acme"], lanes=["product"])
    store.store_source_blob(
        entity_id="acme",
        url="https://example.com/acme",
        content=b"Acme changed its product page.",
    )
    return store


def test_gate_returns_one_for_unacked_deltas_and_zero_after_ack(tmp_path, capsys):
    _seed_changed_source(tmp_path)

    code = main(
        [
            "--cache-dir",
            str(tmp_path),
            "gate",
            "--desk",
            "acme-desk",
            "--lane",
            "product",
            "--since",
            "1d",
            "--format",
            "brief",
        ]
    )

    assert code == 1
    assert "entity=acme" in capsys.readouterr().out

    code = main(
        [
            "--cache-dir",
            str(tmp_path),
            "deltas",
            "--desk",
            "acme-desk",
            "--lane",
            "product",
            "--ack",
            "--quiet",
        ]
    )

    assert code == 0
    assert capsys.readouterr().out == ""

    code = main(
        [
            "--cache-dir",
            str(tmp_path),
            "gate",
            "--desk",
            "acme-desk",
            "--lane",
            "product",
            "--since",
            "1d",
        ]
    )

    assert code == 0
    assert capsys.readouterr().out == ""


def test_deltas_gate_flag_uses_exit_code_without_suppressing_json(tmp_path, capsys):
    _seed_changed_source(tmp_path)

    code = main(
        [
            "--cache-dir",
            str(tmp_path),
            "deltas",
            "--desk",
            "acme-desk",
            "--lane",
            "product",
            "--gate",
        ]
    )

    assert code == 1
    assert '"entity_id": "acme"' in capsys.readouterr().out


def test_status_reports_local_cache_counts(tmp_path, capsys):
    _seed_changed_source(tmp_path)

    assert main(["--cache-dir", str(tmp_path), "status"]) == 0

    output = capsys.readouterr().out
    assert '"entities": 1' in output
    assert '"subscriptions": 1' in output
    assert '"deltas": 1' in output
