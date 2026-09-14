from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from typing import Any

from .deltas import list_deltas
from .entity import list_entities, upsert_entity
from .fetch import fetch_entity, fetch_source
from .models import LANES
from .store import CacheStore
from .subscribe import list_subscriptions, subscribe_desk
from .warm import warm_all, warm_desk, warm_entities


def _store(args: argparse.Namespace) -> CacheStore:
    return CacheStore(args.cache_dir)


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _normalize_since(value: str | None) -> str | None:
    if value is None:
        return None
    if "T" not in value:
        return f"{value}T00:00:00Z"
    return value


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
        results = [fetch_source(store=store, entity_id=args.entity, url=args.url)]
    else:
        results = fetch_entity(store=store, entity_id=args.entity)
    _print_json([result.to_dict() for result in results])
    return 0


def _cmd_warm(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.all:
        results = warm_all(store=store)
    elif args.desk:
        results = warm_desk(store=store, desk_id=args.desk)
    else:
        results = warm_entities(store=store, entity_ids=args.entity)
    _print_json([result.to_dict() for result in results])
    return 0


def _cmd_deltas(args: argparse.Namespace) -> int:
    deltas = list_deltas(
        store=_store(args),
        since=_normalize_since(args.since),
        desk_id=args.desk,
        lane=args.lane,
        entity_id=args.entity,
    )
    _print_json([delta.to_dict() for delta in deltas])
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
    fetch_parser.set_defaults(func=_cmd_fetch)

    warm_parser = subparsers.add_parser("warm", help="Warm sources for a desk, entity, or every entity.")
    warm_target = warm_parser.add_mutually_exclusive_group(required=True)
    warm_target.add_argument("--desk", help="Warm entities subscribed by a desk.")
    warm_target.add_argument("--entity", action="append", help="Entity id. May be repeated.")
    warm_target.add_argument("--all", action="store_true", help="Warm all registered entities.")
    warm_parser.set_defaults(func=_cmd_warm)

    deltas_parser = subparsers.add_parser("deltas", help="List changed sources.")
    deltas_parser.add_argument("--desk", help="Filter to a desk subscription.")
    deltas_parser.add_argument("--lane", choices=LANES, help="Filter to subscriptions for a lane.")
    deltas_parser.add_argument("--entity", help="Filter to one entity id.")
    deltas_parser.add_argument("--since", help="ISO timestamp or YYYY-MM-DD lower bound.")
    deltas_parser.set_defaults(func=_cmd_deltas)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.func
    try:
        return handler(args)
    except Exception as exc:
        print(f"intel-cache: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
