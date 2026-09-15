import hashlib
import json
from pathlib import Path

from intel_cache.cli import main
from intel_cache.migration import migrate_v1_to_v2
from intel_cache.store import CacheStore


def test_migrate_v1_layout_preserves_blobs_and_enables_status_and_gate(tmp_path, capsys):
    old_sha = hashlib.sha256(b"old page\n").hexdigest()
    new_sha = hashlib.sha256(b"new page\n").hexdigest()
    _write_v1_cache(tmp_path, old_sha=old_sha, new_sha=new_sha)

    result = migrate_v1_to_v2(store=CacheStore(tmp_path))

    assert result["migrated"] is True
    assert result["entities"] == 1
    assert result["subscriptions"] == 1
    assert result["blobs"] == 2
    assert result["sources"] == 1
    assert result["deltas"] == 1
    assert result["backup_path"]
    assert Path(result["backup_path"], "entities.json").exists()

    assert json.loads((tmp_path / "entities.json").read_text(encoding="utf-8")) == {
        "acme": {
            "aliases": ["Acme Inc."],
            "display_name": "Acme",
            "domains": ["acme.example"],
            "id": "acme",
            "source_urls": ["https://example.com/acme"],
        }
    }
    assert (tmp_path / "subscriptions.json").exists()
    assert (tmp_path / "blobs" / old_sha).read_text(encoding="utf-8") == "old page\n"
    assert (tmp_path / "blobs" / new_sha).read_text(encoding="utf-8") == "new page\n"
    assert (tmp_path / "blobs" / "acme" / "url123" / f"{new_sha}.md").exists()

    source_meta = json.loads(
        (tmp_path / "sources" / "acme" / "url123.json").read_text(encoding="utf-8")
    )
    assert source_meta["source_key"] == "url123"
    assert source_meta["sha256"] == new_sha
    assert source_meta["blob_path"] == str(tmp_path / "blobs" / new_sha)

    assert main(["--cache-dir", str(tmp_path), "status"]) == 0
    status_output = capsys.readouterr().out
    assert '"entities": 1' in status_output
    assert '"sources": 1' in status_output
    assert '"deltas": 1' in status_output

    assert (
        main(
            [
                "--cache-dir",
                str(tmp_path),
                "gate",
                "--desk",
                "acme-desk",
                "--lane",
                "product",
            ]
        )
        == 1
    )
    assert '"source_key": "url123"' in capsys.readouterr().out


def test_status_tolerates_source_meta_without_source_key(tmp_path, capsys):
    store = CacheStore(tmp_path)
    store._write_json(
        store.entities_path,
        {
            "acme": {
                "id": "acme",
                "display_name": "Acme",
                "aliases": [],
                "domains": [],
                "source_urls": ["https://example.com/acme"],
            }
        },
    )
    store._write_json(
        store.subscriptions_path,
        {"acme-desk": {"desk_id": "acme-desk", "entity_ids": ["acme"], "lanes": ["product"]}},
    )
    store._write_json(
        store.sources_dir / "acme" / "url123.json",
        {
            "url": "https://example.com/acme",
            "sha256": "abc",
            "fetched_at": "2026-01-01T00:00:00Z",
        },
    )

    assert main(["--cache-dir", str(tmp_path), "status"]) == 0
    assert '"sources": 1' in capsys.readouterr().out


def test_unknown_gate_desk_returns_error_code_two(tmp_path, capsys):
    assert (
        main(
            [
                "--cache-dir",
                str(tmp_path),
                "gate",
                "--desk",
                "missing",
                "--lane",
                "product",
            ]
        )
        == 2
    )
    assert "unknown desk subscription" in capsys.readouterr().err


def _write_v1_cache(root: Path, *, old_sha: str, new_sha: str) -> None:
    (root / "desks").mkdir()
    (root / "blobs" / "acme" / "url123").mkdir(parents=True)
    (root / "meta" / "acme").mkdir(parents=True)
    (root / "deltas" / "2026-01-02").mkdir(parents=True)

    (root / "entities.json").write_text(
        json.dumps(
            {
                "entities": [
                    {
                        "id": "acme",
                        "display_name": "Acme",
                        "aliases": ["Acme Inc."],
                        "domains": ["acme.example"],
                        "source_urls": ["https://example.com/acme"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / "desks" / "acme-desk.json").write_text(
        json.dumps({"desk_id": "acme-desk", "entity_ids": ["acme"], "lanes": ["product"]}),
        encoding="utf-8",
    )
    (root / "blobs" / "acme" / "url123" / f"{old_sha}.md").write_text(
        "old page\n",
        encoding="utf-8",
    )
    (root / "blobs" / "acme" / "url123" / f"{new_sha}.md").write_text(
        "new page\n",
        encoding="utf-8",
    )
    (root / "meta" / "acme" / "url123.json").write_text(
        json.dumps(
            {
                "url": "https://example.com/acme",
                "sha256": new_sha,
                "previous_sha256": old_sha,
                "fetched_at": "2026-01-02T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (root / "deltas" / "2026-01-02" / "acme-desk.json").write_text(
        json.dumps(
            [
                {
                    "entity_id": "acme",
                    "url": "https://example.com/acme",
                    "source_key": "url123",
                    "sha256": new_sha,
                    "previous_sha256": old_sha,
                    "changed_at": "2026-01-02T00:00:00Z",
                    "size": len("new page\n"),
                }
            ]
        ),
        encoding="utf-8",
    )
