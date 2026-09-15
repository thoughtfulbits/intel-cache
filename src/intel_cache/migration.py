from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .models import Delta, DeskSubscription, Entity, normalize_id, utc_now_iso
from .store import CacheStore, source_key


def migrate_v1_to_v2(*, store: CacheStore) -> dict[str, Any]:
    root = store.root
    legacy_detected = _legacy_layout_detected(root)
    if legacy_detected:
        backup_path = _backup_legacy_metadata(root)
    else:
        backup_path = None

    entities = _legacy_entities(root / "entities.json")
    subscriptions = _legacy_subscriptions(root)
    blob_count = _copy_legacy_blobs(root)
    source_count = _migrate_legacy_meta(store)
    delta_count = _migrate_legacy_deltas(store)

    if entities:
        existing_entities = {entity.id: entity.to_dict() for entity in store.list_entities()}
        for entity in entities:
            existing_entities[entity.id] = entity.to_dict()
        store._write_json(store.entities_path, existing_entities)

    if subscriptions:
        existing_subscriptions = {}
        if store.subscriptions_path.exists():
            existing_subscriptions = {
                subscription.desk_id: subscription.to_dict()
                for subscription in store.list_subscriptions()
                if all(store.get_entity(entity_id) for entity_id in subscription.entity_ids)
            }
        for subscription in subscriptions:
            existing_subscriptions[subscription.desk_id] = subscription.to_dict()
        store._write_json(store.subscriptions_path, existing_subscriptions)

    if not store.watermarks_path.exists():
        store._write_json(store.watermarks_path, {})

    return {
        "migrated": legacy_detected,
        "backup_path": str(backup_path) if backup_path else None,
        "entities": len(entities),
        "subscriptions": len(subscriptions),
        "blobs": blob_count,
        "sources": source_count,
        "deltas": delta_count,
    }


def _legacy_layout_detected(root: Path) -> bool:
    entities_path = root / "entities.json"
    if entities_path.exists():
        try:
            data = _read_json(entities_path)
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("entities"), list):
            return True
    return any((root / name).exists() for name in ("desks", "meta", "deltas"))


def _backup_legacy_metadata(root: Path) -> Path:
    backup_path = root / "migration-backups" / f"v0.1-{_safe_timestamp()}"
    backup_path.mkdir(parents=True, exist_ok=False)
    for name in ("entities.json", "desks", "meta", "deltas"):
        source = root / name
        if source.is_file():
            shutil.copy2(source, backup_path / name)
        elif source.is_dir():
            shutil.copytree(source, backup_path / name)
    return backup_path


def _legacy_entities(path: Path) -> list[Entity]:
    if not path.exists():
        return []
    data = _read_json(path)
    if isinstance(data, dict) and isinstance(data.get("entities"), list):
        values = data["entities"]
    elif isinstance(data, dict):
        return []
    else:
        values = data
    return [_entity_from_dict(value) for value in values]


def _entity_from_dict(data: dict[str, Any]) -> Entity:
    source_urls = data.get("source_urls") or data.get("urls") or []
    if not source_urls and isinstance(data.get("sources"), list):
        source_urls = [
            item["url"] if isinstance(item, dict) else item
            for item in data["sources"]
            if (isinstance(item, str) and item) or (isinstance(item, dict) and item.get("url"))
        ]
    return Entity(
        id=data["id"],
        display_name=data.get("display_name") or data.get("name") or data["id"],
        aliases=list(data.get("aliases", [])),
        domains=list(data.get("domains", [])),
        source_urls=list(source_urls),
    )


def _legacy_subscriptions(root: Path) -> list[DeskSubscription]:
    desks_dir = root / "desks"
    if not desks_dir.is_dir():
        return []
    subscriptions: list[DeskSubscription] = []
    for path in sorted(desks_dir.glob("*.json")):
        data = _read_json(path)
        subscriptions.extend(_subscriptions_from_data(data, fallback_desk_id=path.stem))
    return subscriptions


def _subscriptions_from_data(data: Any, *, fallback_desk_id: str) -> list[DeskSubscription]:
    if isinstance(data, list):
        return [_subscription_from_dict(item, fallback_desk_id=fallback_desk_id) for item in data]
    if isinstance(data, dict) and (
        "desk_id" in data or "entity_ids" in data or "entities" in data
    ):
        return [_subscription_from_dict(data, fallback_desk_id=fallback_desk_id)]
    if isinstance(data, dict):
        return [
            _subscription_from_dict(value, fallback_desk_id=key)
            for key, value in data.items()
            if isinstance(value, dict)
        ]
    return []


def _subscription_from_dict(data: dict[str, Any], *, fallback_desk_id: str) -> DeskSubscription:
    return DeskSubscription(
        desk_id=data.get("desk_id") or fallback_desk_id,
        entity_ids=_coerce_entity_ids(data.get("entity_ids") or data.get("entities") or []),
        lanes=_coerce_lanes(data.get("lanes") or []),
    )


def _coerce_entity_ids(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    return [
        item["id"] if isinstance(item, dict) else str(item)
        for item in values
        if (isinstance(item, dict) and item.get("id")) or (not isinstance(item, dict) and item)
    ]


def _coerce_lanes(values: Any) -> list[str]:
    if isinstance(values, str):
        values = values.split(",")
    return [str(value) for value in values if value]


def _copy_legacy_blobs(root: Path) -> int:
    blobs_dir = root / "blobs"
    if not blobs_dir.is_dir():
        return 0
    copied = 0
    for path in blobs_dir.glob("*/*/*"):
        if not path.is_file():
            continue
        sha = path.stem
        target = blobs_dir / sha
        if target.exists():
            continue
        shutil.copy2(path, target)
        copied += 1
    return copied


def _migrate_legacy_meta(store: CacheStore) -> int:
    meta_dir = store.root / "meta"
    if not meta_dir.is_dir():
        return 0
    count = 0
    for path in sorted(meta_dir.glob("*/*.json")):
        data = _read_json(path)
        entity_id = normalize_id(data.get("entity_id") or path.parent.name)
        key = str(data.get("source_key") or path.stem)
        sha = str(data.get("sha256") or data.get("sha") or "")
        url = str(data.get("url") or "")
        target_blob = store.blobs_dir / sha if sha else None
        migrated = {
            **data,
            "entity_id": entity_id,
            "url": url,
            "source_key": key,
            "sha256": sha,
            "blob_path": str(target_blob) if target_blob else data.get("blob_path"),
            "changed": bool(data.get("changed", False)),
            "previous_sha256": data.get("previous_sha256"),
            "fetched_at": data.get("fetched_at") or data.get("changed_at") or utc_now_iso(),
            "size": data.get("size") or _blob_size(target_blob),
            "hash_mode": data.get("hash_mode", "raw"),
        }
        store._write_json(store.sources_dir / entity_id / f"{key}.json", migrated)
        count += 1
    return count


def _migrate_legacy_deltas(store: CacheStore) -> int:
    deltas_dir = store.root / "deltas"
    if not deltas_dir.is_dir():
        return 0

    existing = {
        (
            delta.entity_id,
            delta.source_key,
            delta.sha256,
            delta.changed_at,
        )
        for delta in store.list_deltas()
    }
    migrated: list[Delta] = []
    for path in sorted(deltas_dir.glob("*/*.json")):
        date = path.parent.name
        for item in _delta_items(_read_json(path)):
            delta = _delta_from_dict(store, item, fallback_date=date)
            key = (delta.entity_id, delta.source_key, delta.sha256, delta.changed_at)
            if key in existing:
                continue
            existing.add(key)
            migrated.append(delta)

    if migrated:
        with store.deltas_path.open("a", encoding="utf-8") as file:
            for delta in migrated:
                file.write(json.dumps(delta.to_dict(), sort_keys=True))
                file.write("\n")
    return len(migrated)


def _delta_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("deltas"), list):
        return [item for item in data["deltas"] if isinstance(item, dict)]
    if isinstance(data, dict) and ("sha256" in data or "sha" in data):
        return [data]
    if isinstance(data, dict):
        items: list[dict[str, Any]] = []
        for value in data.values():
            items.extend(_delta_items(value))
        return items
    return []


def _delta_from_dict(store: CacheStore, data: dict[str, Any], *, fallback_date: str) -> Delta:
    entity_id = normalize_id(data["entity_id"])
    url = str(data.get("url") or "")
    key = str(data.get("source_key") or (source_key(url) if url else data.get("url_id") or "unknown"))
    sha = str(data.get("sha256") or data.get("sha"))
    blob_path = data.get("blob_path") or str(store.blobs_dir / sha)
    return Delta(
        entity_id=entity_id,
        url=url,
        source_key=key,
        sha256=sha,
        previous_sha256=data.get("previous_sha256"),
        changed_at=data.get("changed_at") or data.get("fetched_at") or f"{fallback_date}T00:00:00Z",
        blob_path=str(blob_path),
        size=int(data.get("size") or _blob_size(Path(blob_path))),
        hash_mode=data.get("hash_mode", "raw"),
    )


def _blob_size(path: Path | None) -> int:
    if path and path.exists() and path.is_file():
        return path.stat().st_size
    return 0


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _safe_timestamp() -> str:
    return utc_now_iso().replace(":", "").replace("-", "").replace(".", "-")
