from __future__ import annotations

import difflib
from pathlib import Path

from .store import CacheStore, source_key


def diff_blobs(
    *,
    store: CacheStore,
    entity_id: str,
    url: str | None = None,
    sha_a: str | None = None,
    sha_b: str | None = None,
    context: int = 3,
) -> str:
    left_sha, right_sha = _resolve_shas(
        store=store,
        entity_id=entity_id,
        url=url,
        sha_a=sha_a,
        sha_b=sha_b,
    )
    left_text = _blob_text(store.blobs_dir / left_sha)
    right_text = _blob_text(store.blobs_dir / right_sha)
    lines = difflib.unified_diff(
        left_text.splitlines(keepends=True),
        right_text.splitlines(keepends=True),
        fromfile=left_sha,
        tofile=right_sha,
        n=context,
    )
    return "".join(lines)


def _resolve_shas(
    *,
    store: CacheStore,
    entity_id: str,
    url: str | None,
    sha_a: str | None,
    sha_b: str | None,
) -> tuple[str, str]:
    if sha_a and sha_b:
        return sha_a, sha_b
    if sha_a or sha_b:
        raise ValueError("--sha-a and --sha-b must be provided together")

    entity = store.require_entity(entity_id)
    resolved_url = url
    if resolved_url is None:
        if len(entity.source_urls) != 1:
            raise ValueError("--url is required when an entity has multiple source URLs")
        resolved_url = entity.source_urls[0]

    deltas = [
        delta
        for delta in store.list_deltas(entity_id=entity.id)
        if delta.source_key == source_key(resolved_url)
    ]
    if not deltas:
        raise ValueError("no cached delta found for entity/source")
    latest = deltas[-1]
    if latest.previous_sha256 is None:
        raise ValueError("latest delta has no previous SHA to diff")
    return latest.previous_sha256, latest.sha256


def _blob_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"missing blob: {path.name}")
    return path.read_bytes().decode("utf-8", errors="replace")
