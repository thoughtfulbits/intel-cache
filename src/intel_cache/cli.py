from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from .deltas import ack_deltas, list_deltas, list_unacked_deltas
from .diff import diff_blobs
from .entity import list_entities, upsert_entity
from .fetch import fetch_entity, fetch_source
from .migration import migrate_v1_to_v2
from .models import LANES
from .normalize import HASH_MODES
from .seed import seed_directory
from .store import CacheStore
from .subscribe import list_subscriptions, subscribe_desk
from .warm import summarize_warm, warm_all, warm_desk, warm_entities


def _store(args: argparse.Namespace) -> CacheStore:
    return CacheStore(args.cache_dir)


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


_RELATIVE_SINCE_RE = re.compile(r"^(?P<count>\d+)(?P<unit>[mhd])$")


def _normalize_since(value: str | None) -> str | None:
    if value is None:
        return None
    match = _RELATIVE_SINCE_RE.match(value.strip().lower())
    if match:
        count = int(match.group("count"))
        unit = match.group("unit")
        delta = {
            "m": timedelta(minutes=count),
            "h": timedelta(hours=count),
            "d": timedelta(days=count),
        }[unit]
        return (datetime.now(timezone.utc) - delta).isoformat().replace("+00:00", "Z")
    if "T" not in value:
        return f"{value}T00:00:00Z"
    return value


def _print_deltas(deltas: list[Any], *, output_format: str, preview_chars: int = 0) -> None:
    if output_format == "json":
        _print_json([delta.to_dict() for delta in deltas])
        return
    for delta in deltas:
        print(
            "- "
            f"entity={delta.entity_id} "
            f"url={delta.url} "
            f"sha={delta.sha256[:12]} "
            f"previous={delta.previous_sha256[:12] if delta.previous_sha256 else '-'} "
            f"changed_at={delta.changed_at} "
            f"bytes={delta.size} "
            f"blob={delta.blob_path}"
        )
        if preview_chars > 0:
            print(f"  preview={_preview_blob(delta.blob_path, preview_chars)}")


def _preview_blob(blob_path: str, limit: int) -> str:
    with open(blob_path, "rb") as file:
        text = file.read(limit).decode("utf-8", errors="replace")
    return " ".join(text.split())


def _deltas_for_args(args: argparse.Namespace, *, unacked_default: bool = False) -> list[Any]:
    store = _store(args)
    since = _normalize_since(args.since)
    use_unacked = unacked_default or getattr(args, "unacked", False) or getattr(args, "ack", False)
    if use_unacked:
        if not args.desk or not args.lane:
            raise ValueError("--unacked/--ack requires both --desk and --lane")
        return list_unacked_deltas(
            store=store,
            desk_id=args.desk,
            lane=args.lane,
            since=since,
            entity_id=args.entity,
        )
    return list_deltas(
        store=store,
        since=since,
        desk_id=args.desk,
        lane=args.lane,
        entity_id=args.entity,
    )


def _ack_deltas_for_args(args: argparse.Namespace, deltas: list[Any]) -> None:
    if not getattr(args, "ack", False):
        return
    if not args.desk or not args.lane:
        raise ValueError("--ack requires both --desk and --lane")
    ack_deltas(store=_store(args), desk_id=args.desk, lane=args.lane, deltas=deltas)


def _cmd_entity_upsert(args: argparse.Namespace) -> int:
    entity = upsert_entity(
        store=_store(args),
        entity_id=args.id,
        display_name=args.display_name,
        aliases=args.alias,
        domains=args.domain,
        source_urls=args.source_url,
    )
    _print_json(entity.to_dict())
    return 0


def _cmd_entity_list(args: argparse.Namespace) -> int:
    _print_json([entity.to_dict() for entity in list_entities(_store(args))])
    return 0


def _cmd_subscribe(args: argparse.Namespace) -> int:
    subscription = subscribe_desk(
        store=_store(args),
        desk_id=args.desk,
        entity_ids=args.entity,
        lanes=args.lane,
    )
    _print_json(subscription.to_dict())
    return 0


def _cmd_subscriptions(args: argparse.Namespace) -> int:
    _print_json([subscription.to_dict() for subscription in list_subscriptions(_store(args))])
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.url:
        results = [
            fetch_source(
                store=store,
                entity_id=args.entity,
                url=args.url,
                timeout=args.timeout,
                hash_mode=args.hash_mode,
            )
        ]
    else:
        results = fetch_entity(
            store=store,
            entity_id=args.entity,
            timeout=args.timeout,
            hash_mode=args.hash_mode,
        )
    _print_json([result.to_dict() for result in results])
    return 0


def _cmd_warm(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.all:
        results = warm_all(
            store=store,
            timeout=args.timeout,
            concurrency=args.concurrency,
            hash_mode=args.hash_mode,
        )
    elif args.desk:
        results = warm_desk(
            store=store,
            desk_id=args.desk,
            timeout=args.timeout,
            concurrency=args.concurrency,
            hash_mode=args.hash_mode,
        )
    else:
        results = warm_entities(
            store=store,
            entity_ids=args.entity,
            timeout=args.timeout,
            concurrency=args.concurrency,
            hash_mode=args.hash_mode,
        )
    rows = [result.to_dict() for result in results]
    if args.summary:
        _print_json({"summary": summarize_warm(results), "results": rows})
    else:
        _print_json(rows)
    return 0


def _cmd_deltas(args: argparse.Namespace) -> int:
    deltas = _deltas_for_args(args)
    if not args.quiet:
        _print_deltas(deltas, output_format=args.format, preview_chars=args.preview_chars)
    _ack_deltas_for_args(args, deltas)
    return 1 if args.gate and deltas else 0


def _cmd_gate(args: argparse.Namespace) -> int:
    if not args.desk or not args.lane:
        raise ValueError("gate requires both --desk and --lane")
    deltas = _deltas_for_args(args, unacked_default=True)
    if deltas:
        _print_deltas(deltas, output_format=args.format, preview_chars=args.preview_chars)
    _ack_deltas_for_args(args, deltas)
    return 1 if deltas else 0


def _cmd_diff(args: argparse.Namespace) -> int:
    print(
        diff_blobs(
            store=_store(args),
            entity_id=args.entity,
            url=args.url,
            sha_a=args.sha_a,
            sha_b=args.sha_b,
            context=args.context,
        ),
        end="",
    )
    return 0


def _cmd_seed(args: argparse.Namespace) -> int:
    _print_json(seed_directory(store=_store(args), directory=args.path))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    _print_json(_store(args).status())
    return 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    _print_json(migrate_v1_to_v2(store=_store(args)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intel-cache",
        description="Shared fetch + SHA-256 change-detect cache for Company Desk templates.",
    )
    parser.add_argument("--cache-dir", help="Cache directory. Defaults to INTEL_CACHE_DIR or ~/.intel-cache.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    entity_parser = subparsers.add_parser("entity", help="Manage tracked entities.")
    entity_subparsers = entity_parser.add_subparsers(dest="entity_command", required=True)

    entity_upsert = entity_subparsers.add_parser("upsert", help="Create or replace an entity.")
    entity_upsert.add_argument("--id", required=True, help="Stable entity id.")
    entity_upsert.add_argument("--display-name", required=True, help="Human-readable entity name.")
    entity_upsert.add_argument("--alias", action="append", default=[], help="Alias. May be repeated.")
    entity_upsert.add_argument("--domain", action="append", default=[], help="Domain. May be repeated.")
    entity_upsert.add_argument("--source-url", action="append", default=[], help="Source URL. May be repeated.")
    entity_upsert.set_defaults(func=_cmd_entity_upsert)

    entity_list = entity_subparsers.add_parser("list", help="List entities.")
    entity_list.set_defaults(func=_cmd_entity_list)

    subscribe_parser = subparsers.add_parser("subscribe", help="Create or replace a desk subscription.")
    subscribe_parser.add_argument("--desk", required=True, help="Desk id.")
    subscribe_parser.add_argument("--entity", action="append", required=True, help="Entity id. May be repeated.")
    subscribe_parser.add_argument("--lane", action="append", choices=LANES, required=True, help="Lane. May be repeated.")
    subscribe_parser.set_defaults(func=_cmd_subscribe)

    subscriptions_parser = subparsers.add_parser("subscriptions", help="List desk subscriptions.")
    subscriptions_parser.set_defaults(func=_cmd_subscriptions)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch one entity source or all sources for an entity.")
    fetch_parser.add_argument("--entity", required=True, help="Entity id.")
    fetch_parser.add_argument("--url", help="Specific source URL. Defaults to all sources for the entity.")
    fetch_parser.add_argument("--timeout", type=float, default=20.0, help="Fetch timeout in seconds.")
    fetch_parser.add_argument("--hash-mode", choices=HASH_MODES, help="Hash raw or normalized content.")
    fetch_parser.set_defaults(func=_cmd_fetch)

    warm_parser = subparsers.add_parser("warm", help="Warm sources for a desk, entity, or every entity.")
    warm_target = warm_parser.add_mutually_exclusive_group(required=True)
    warm_target.add_argument("--desk", help="Warm entities subscribed by a desk.")
    warm_target.add_argument("--entity", action="append", help="Entity id. May be repeated.")
    warm_target.add_argument("--all", action="store_true", help="Warm all registered entities.")
    warm_parser.add_argument("--timeout", type=float, default=20.0, help="Fetch timeout in seconds.")
    warm_parser.add_argument("--concurrency", type=int, default=4, help="Maximum parallel fetches.")
    warm_parser.add_argument("--hash-mode", choices=HASH_MODES, help="Hash raw or normalized content.")
    warm_parser.add_argument("--summary", action="store_true", help="Print changed/unchanged/failed counts.")
    warm_parser.set_defaults(func=_cmd_warm)

    deltas_parser = subparsers.add_parser("deltas", help="List changed sources.")
    deltas_parser.add_argument("--desk", help="Filter to a desk subscription.")
    deltas_parser.add_argument("--lane", choices=LANES, help="Filter to subscriptions for a lane.")
    deltas_parser.add_argument("--entity", help="Filter to one entity id.")
    deltas_parser.add_argument("--since", help="ISO timestamp, YYYY-MM-DD, or relative window like 24h/7d.")
    deltas_parser.add_argument("--format", choices=("json", "brief"), default="json", help="Output format.")
    deltas_parser.add_argument("--preview-chars", type=int, default=0, help="Include the first N blob chars in brief output.")
    deltas_parser.add_argument("--quiet", action="store_true", help="Suppress output.")
    deltas_parser.add_argument("--gate", action="store_true", help="Exit 0 when empty, 1 when deltas exist.")
    deltas_parser.add_argument("--unacked", action="store_true", help="Only show deltas after the desk/lane watermark.")
    deltas_parser.add_argument("--ack", action="store_true", help="Advance the desk/lane watermark to the listed deltas.")
    deltas_parser.set_defaults(func=_cmd_deltas)

    gate_parser = subparsers.add_parser("gate", help="Quiet specialist gate: exit 0 if no unacked deltas, 1 if work exists.")
    gate_parser.add_argument("--desk", required=True, help="Desk id.")
    gate_parser.add_argument("--lane", choices=LANES, required=True, help="Lane.")
    gate_parser.add_argument("--entity", help="Filter to one entity id.")
    gate_parser.add_argument("--since", help="ISO timestamp, YYYY-MM-DD, or relative window like 24h/7d.")
    gate_parser.add_argument("--format", choices=("json", "brief"), default="json", help="Output format when deltas exist.")
    gate_parser.add_argument("--preview-chars", type=int, default=0, help="Include the first N blob chars in brief output.")
    gate_parser.add_argument("--ack", action="store_true", help="Advance the desk/lane watermark to the listed deltas.")
    gate_parser.set_defaults(func=_cmd_gate)

    diff_parser = subparsers.add_parser("diff", help="Print a unified diff between cached blobs.")
    diff_parser.add_argument("--entity", required=True, help="Entity id.")
    diff_parser.add_argument("--url", help="Source URL. Optional when the entity has one source URL.")
    diff_parser.add_argument("--sha-a", help="Older blob SHA. Requires --sha-b.")
    diff_parser.add_argument("--sha-b", help="Newer blob SHA. Requires --sha-a.")
    diff_parser.add_argument("--context", type=int, default=3, help="Unified diff context lines.")
    diff_parser.set_defaults(func=_cmd_diff)

    seed_parser = subparsers.add_parser("seed", help="Load entities.json and subscriptions/desks JSON from a directory.")
    seed_parser.add_argument("--path", required=True, help="Directory containing seed JSON files.")
    seed_parser.set_defaults(func=_cmd_seed)

    import_parser = subparsers.add_parser("import", help="Alias for seed.")
    import_parser.add_argument("--path", required=True, help="Directory containing seed JSON files.")
    import_parser.set_defaults(func=_cmd_seed)

    status_parser = subparsers.add_parser("status", help="Print cache counts and latest timestamps.")
    status_parser.set_defaults(func=_cmd_status)

    migrate_parser = subparsers.add_parser("migrate", help="Migrate a v0.1 cache layout to v0.2.")
    migrate_parser.set_defaults(func=_cmd_migrate)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.func
    try:
        return handler(args)
    except Exception as exc:
        print(f"intel-cache: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
