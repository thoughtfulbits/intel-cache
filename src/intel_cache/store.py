from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

from .models import Delta, DeskSubscription, Entity, FetchResult, normalize_id, utc_now_iso
from .normalize import canonical_source_url, sha256_content


def default_cache_dir() -> Path:
    env_value = os.environ.get("INTEL_CACHE_DIR")
    if env_value:
        return Path(env_value).expanduser()
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return Path.cwd() / "intel-cache-data"
    return Path.home() / ".intel-cache"


def source_key(url: str) -> str:
    return sha256_content(canonical_source_url(url).encode("utf-8"))[:24]


class CacheStore:
    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.root = Path(cache_dir).expanduser() if cache_dir is not None else default_cache_dir()
        self.entities_path = self.root / "entities.json"
        self.subscriptions_path = self.root / "subscriptions.json"
        self.blobs_dir = self.root / "blobs"
        self.sources_dir = self.root / "sources"
        self.deltas_path = self.root / "deltas.jsonl"
        self.watermarks_path = self.root / "watermarks.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, sort_keys=True)
            file.write("\n")
        tmp_path.replace(path)

    def list_entities(self) -> list[Entity]:
        data = self._read_json(self.entities_path, {})
        if isinstance(data, dict) and "entities" in data:
            values = data.get("entities", [])
        elif isinstance(data, list):
            values = data
        else:
            values = data.values()
        return [Entity.from_dict(value) for value in sorted(values, key=lambda item: item["id"])]

    def get_entity(self, entity_id: str) -> Entity | None:
        data = self._read_json(self.entities_path, {})
        if isinstance(data, dict) and "entities" in data:
            data = {value["id"]: value for value in data["entities"]}
        elif isinstance(data, list):
            data = {value["id"]: value for value in data}
        entity = data.get(normalize_id(entity_id))
        return Entity.from_dict(entity) if entity else None

    def upsert_entity(self, entity: Entity) -> Entity:
        data = self._read_json(self.entities_path, {})
        data[entity.id] = entity.to_dict()
        self._write_json(self.entities_path, data)
        return entity

    def require_entity(self, entity_id: str) -> Entity:
        entity = self.get_entity(entity_id)
        if entity is None:
            raise KeyError(f"unknown entity: {entity_id}")
        return entity

    def list_subscriptions(self) -> list[DeskSubscription]:
        data = self._read_json(self.subscriptions_path, {})
        if isinstance(data, list):
            return [DeskSubscription.from_dict(value) for value in data]
        if not data and (self.root / "desks").is_dir():
            return [
                DeskSubscription.from_dict(self._read_json(path, {}))
                for path in sorted((self.root / "desks").glob("*.json"))
            ]
        return [
            DeskSubscription.from_dict(value)
            for value in sorted(data.values(), key=lambda item: item["desk_id"])
        ]

    def get_subscription(self, desk_id: str) -> DeskSubscription | None:
        data = self._read_json(self.subscriptions_path, {})
        if not data:
            legacy_path = self.root / "desks" / f"{normalize_id(desk_id)}.json"
            if legacy_path.exists():
                return DeskSubscription.from_dict(self._read_json(legacy_path, {}))
        subscription = data.get(normalize_id(desk_id))
        return DeskSubscription.from_dict(subscription) if subscription else None

    def upsert_subscription(self, subscription: DeskSubscription) -> DeskSubscription:
        for entity_id in subscription.entity_ids:
            self.require_entity(entity_id)
        data = self._read_json(self.subscriptions_path, {})
        data[subscription.desk_id] = subscription.to_dict()
        self._write_json(self.subscriptions_path, data)
        return subscription

    def store_source_blob(
        self,
        entity_id: str,
        url: str,
        content: bytes,
        *,
        hash_mode: str = "raw",
    ) -> FetchResult:
        entity_id = normalize_id(entity_id)
        self.require_entity(entity_id)
        digest = sha256_content(content, mode=hash_mode)
        blob_path = self.blobs_dir / digest
        if not blob_path.exists():
            blob_path.write_bytes(content)

        key = source_key(url)
        meta_path = self._source_meta_path(entity_id, key)
        previous_meta = self._read_json(meta_path, None)
        previous_sha = previous_meta.get("sha256") if previous_meta else None
        changed = previous_sha != digest
        fetched_at = utc_now_iso()
        result = FetchResult(
            entity_id=entity_id,
            url=url,
            source_key=key,
            sha256=digest,
            blob_path=str(blob_path),
            changed=changed,
            previous_sha256=previous_sha,
            fetched_at=fetched_at,
            size=len(content),
            hash_mode=hash_mode,
        )
        self._write_json(meta_path, result.to_dict())
        if changed:
            self._append_delta(
                Delta(
                    entity_id=entity_id,
                    url=url,
                    source_key=key,
                    sha256=digest,
                    previous_sha256=previous_sha,
                    changed_at=fetched_at,
                    blob_path=str(blob_path),
                    size=len(content),
                    hash_mode=hash_mode,
                )
            )
        return result

    def _source_meta_path(self, entity_id: str, key: str) -> Path:
        return self.sources_dir / normalize_id(entity_id) / f"{key}.json"

    def _append_delta(self, delta: Delta) -> None:
        self.deltas_path.parent.mkdir(parents=True, exist_ok=True)
        with self.deltas_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(delta.to_dict(), sort_keys=True))
            file.write("\n")

    def list_deltas(
        self,
        *,
        since: str | None = None,
        desk_id: str | None = None,
        lane: str | None = None,
        entity_id: str | None = None,
    ) -> list[Delta]:
        entity_filter = self._entity_filter_for(desk_id=desk_id, lane=lane, entity_id=entity_id)
        deltas: list[Delta] = []
        if not self.deltas_path.exists():
            return deltas
        with self.deltas_path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                delta = Delta.from_dict(json.loads(line))
                if since and delta.changed_at < since:
                    continue
                if entity_filter is not None and delta.entity_id not in entity_filter:
                    continue
                deltas.append(delta)
        return deltas

    def get_delta_watermark(self, *, desk_id: str, lane: str) -> str | None:
        data = self._read_json(self.watermarks_path, {})
        value = data.get(self._watermark_key(desk_id=desk_id, lane=lane))
        if not value:
            return None
        return str(value.get("last_seen_changed_at") or "")

    def set_delta_watermark(self, *, desk_id: str, lane: str, changed_at: str) -> None:
        data = self._read_json(self.watermarks_path, {})
        key = self._watermark_key(desk_id=desk_id, lane=lane)
        data[key] = {
            "desk_id": normalize_id(desk_id),
            "lane": lane.strip().lower(),
            "last_seen_changed_at": changed_at,
            "updated_at": utc_now_iso(),
        }
        self._write_json(self.watermarks_path, data)

    def status(self) -> dict[str, Any]:
        source_meta = self._source_metadata()
        deltas = self.list_deltas()
        watermarks = self._read_json(self.watermarks_path, {})
        return {
            "entities": len(self.list_entities()),
            "subscriptions": len(self.list_subscriptions()),
            "sources": len(source_meta),
            "blobs": sum(1 for path in self.blobs_dir.iterdir() if path.is_file())
            if self.blobs_dir.exists()
            else 0,
            "deltas": len(deltas),
            "watermarks": len(watermarks),
            "last_fetched_at": max(
                (str(item.get("fetched_at", "")) for item in source_meta),
                default=None,
            ),
            "last_changed_at": max((delta.changed_at for delta in deltas), default=None),
        }

    def _entity_filter_for(
        self,
        *,
        desk_id: str | None,
        lane: str | None,
        entity_id: str | None,
    ) -> set[str] | None:
        entity_ids: set[str] | None = None
        if desk_id:
            subscription = self.get_subscription(desk_id)
            if subscription is None:
                raise KeyError(f"unknown desk subscription: {desk_id}")
            if lane and lane not in subscription.lanes:
                return set()
            entity_ids = set(subscription.entity_ids)
        elif lane:
            entity_ids = {
                entity_id
                for subscription in self.list_subscriptions()
                if lane in subscription.lanes
                for entity_id in subscription.entity_ids
            }
        if entity_id:
            normalized = normalize_id(entity_id)
            entity_ids = {normalized} if entity_ids is None else entity_ids & {normalized}
        return entity_ids

    def load_entities(self, entities: Iterable[Entity]) -> list[Entity]:
        return [self.upsert_entity(entity) for entity in entities]

    def _watermark_key(self, *, desk_id: str, lane: str) -> str:
        return f"{normalize_id(desk_id)}:{lane.strip().lower()}"

    def _source_metadata(self) -> list[dict[str, Any]]:
        if not self.sources_dir.exists():
            return []
        items: list[dict[str, Any]] = []
        for path in self.sources_dir.glob("*/*.json"):
            try:
                item = self._read_json(path, {})
            except json.JSONDecodeError:
                continue
            item.setdefault("entity_id", path.parent.name)
            item.setdefault("source_key", path.stem)
            items.append(item)
        return items
