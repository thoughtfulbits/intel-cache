from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


LANES = ("people", "product", "ma", "marketing", "customer", "roadmap")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_id(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("id cannot be empty")
    return normalized


def unique_strings(values: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values or []:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


@dataclass(slots=True)
class Entity:
    id: str
    display_name: str
    aliases: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = normalize_id(self.id)
        self.display_name = self.display_name.strip()
        if not self.display_name:
            raise ValueError("display_name cannot be empty")
        self.aliases = unique_strings(self.aliases)
        self.domains = unique_strings([domain.lower() for domain in self.domains])
        self.source_urls = unique_strings(self.source_urls)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "aliases": self.aliases,
            "domains": self.domains,
            "source_urls": self.source_urls,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entity":
        return cls(
            id=data["id"],
            display_name=data["display_name"],
            aliases=list(data.get("aliases", [])),
            domains=list(data.get("domains", [])),
            source_urls=list(data.get("source_urls", [])),
        )


@dataclass(slots=True)
class DeskSubscription:
    desk_id: str
    entity_ids: list[str] = field(default_factory=list)
    lanes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.desk_id = normalize_id(self.desk_id)
        self.entity_ids = unique_strings([normalize_id(entity_id) for entity_id in self.entity_ids])
        self.lanes = unique_strings([lane.strip().lower() for lane in self.lanes])
        invalid_lanes = [lane for lane in self.lanes if lane not in LANES]
        if invalid_lanes:
            raise ValueError(f"unknown lanes: {', '.join(invalid_lanes)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "desk_id": self.desk_id,
            "entity_ids": self.entity_ids,
            "lanes": self.lanes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeskSubscription":
        return cls(
            desk_id=data["desk_id"],
            entity_ids=list(data.get("entity_ids", [])),
            lanes=list(data.get("lanes", [])),
        )


@dataclass(frozen=True, slots=True)
class FetchResult:
    entity_id: str
    url: str
    source_key: str
    sha256: str
    blob_path: str
    changed: bool
    previous_sha256: str | None
    fetched_at: str
    size: int
    hash_mode: str = "raw"

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "url": self.url,
            "source_key": self.source_key,
            "sha256": self.sha256,
            "blob_path": self.blob_path,
            "changed": self.changed,
            "previous_sha256": self.previous_sha256,
            "fetched_at": self.fetched_at,
            "size": self.size,
            "hash_mode": self.hash_mode,
        }


@dataclass(frozen=True, slots=True)
class FetchFailure:
    entity_id: str
    url: str
    source_key: str
    error: str
    fetched_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "url": self.url,
            "source_key": self.source_key,
            "error": self.error,
            "fetched_at": self.fetched_at,
            "failed": True,
        }


@dataclass(frozen=True, slots=True)
class Delta:
    entity_id: str
    url: str
    source_key: str
    sha256: str
    previous_sha256: str | None
    changed_at: str
    blob_path: str
    size: int
    hash_mode: str = "raw"

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "url": self.url,
            "source_key": self.source_key,
            "sha256": self.sha256,
            "previous_sha256": self.previous_sha256,
            "changed_at": self.changed_at,
            "blob_path": self.blob_path,
            "size": self.size,
            "hash_mode": self.hash_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Delta":
        return cls(
            entity_id=data["entity_id"],
            url=data["url"],
            source_key=data["source_key"],
            sha256=data["sha256"],
            previous_sha256=data.get("previous_sha256"),
            changed_at=data["changed_at"],
            blob_path=data["blob_path"],
            size=int(data["size"]),
            hash_mode=data.get("hash_mode", "raw"),
        )
