from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import DeskSubscription, Entity
from .store import CacheStore


def seed_directory(*, store: CacheStore, directory: str | Path) -> dict[str, int]:
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"seed directory not found: {root}")

    entities = _load_entities(root / "entities.json")
    loaded_entities = store.load_entities(entities)

    subscriptions = _load_subscriptions(root)
    loaded_subscriptions = [
        store.upsert_subscription(subscription) for subscription in subscriptions
    ]

    return {
        "entities": len(loaded_entities),
        "subscriptions": len(loaded_subscriptions),
    }


def _load_entities(path: Path) -> list[Entity]:
    if not path.exists():
        return []
    data = _read_json(path)
    values = data.values() if isinstance(data, dict) else data
    return [Entity.from_dict(value) for value in values]


def _load_subscriptions(root: Path) -> list[DeskSubscription]:
    subscriptions: list[DeskSubscription] = []
    subscriptions_path = root / "subscriptions.json"
    if subscriptions_path.exists():
        data = _read_json(subscriptions_path)
        values = data.values() if isinstance(data, dict) else data
        subscriptions.extend(DeskSubscription.from_dict(value) for value in values)

    desks_dir = root / "desks"
    if desks_dir.is_dir():
        for path in sorted(desks_dir.glob("*.json")):
            data = _read_json(path)
            if isinstance(data, dict) and "desk_id" in data:
                subscriptions.append(DeskSubscription.from_dict(data))
            elif isinstance(data, dict):
                subscriptions.extend(
                    DeskSubscription.from_dict(value) for value in data.values()
                )
            else:
                subscriptions.extend(DeskSubscription.from_dict(value) for value in data)
    return subscriptions


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
