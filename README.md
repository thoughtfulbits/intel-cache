# intel-cache

Shared fetch + SHA-256 change-detect cache for ThoughtfulBits Company Desk templates.

`intel-cache` keeps competitor and source intelligence keyed by entity. It fetches source URLs, stores response bodies as content-addressed blobs, and records a delta only when a source hash changes. Company Desk specialist bots can then deep-analyze changed blobs instead of re-reading every source on every run.

## Why this shape

- One shared cache for all Company Desk lanes.
- Entity-keyed competitors and sources, not one bot per competitor.
- Specialist bots consume deltas for their lane and desk only.
- No megabot: lane specialists stay focused on people, product, M&A, marketing, customer, or roadmap signals.
- SHA-256 metadata makes unchanged sources cheap to skip.

## Install

```bash
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Cache directory

The cache directory is resolved in this order:

1. `INTEL_CACHE_DIR`
2. `./intel-cache-data` when running under pytest
3. `~/.intel-cache`

Set `INTEL_CACHE_FETCH=http` to enable HTTP fetching through `urllib`.

## CLI examples

Create entities:

```bash
intel-cache entity upsert \
  --id acme \
  --display-name "Acme" \
  --alias "Acme Inc." \
  --domain acme.example \
  --source-url https://example.com/acme/news

intel-cache entity upsert \
  --id competitor-a \
  --display-name "Competitor A" \
  --domain competitor-a.example \
  --source-url https://example.com/competitor-a/news
```

Subscribe a desk to entities and lanes:

```bash
intel-cache subscribe \
  --desk acme-desk \
  --entity acme \
  --entity competitor-a \
  --lane product \
  --lane marketing \
  --lane roadmap
```

Warm the cache:

```bash
INTEL_CACHE_FETCH=http intel-cache warm --desk acme-desk
INTEL_CACHE_FETCH=http intel-cache warm --all
```

List deltas:

```bash
intel-cache deltas --desk acme-desk --lane product --since 2026-01-01
intel-cache deltas --entity competitor-a
```

## Architecture

```text
entities.json          entity registry: ids, aliases, domains, source URLs
subscriptions.json     desk subscriptions: desk_id -> entity_ids + lanes
blobs/<sha256>         fetched source bodies, content-addressed
sources/<entity>/<key> latest source metadata and current SHA-256
deltas.jsonl           append-only changed-source events
```

On every fetch, `intel-cache`:

1. Reads the source with `urllib`.
2. Calculates the response body's SHA-256.
3. Stores the blob at `blobs/<sha256>`.
4. Compares the SHA with the latest metadata for that entity/source.
5. Appends a delta only if the SHA changed.

Specialists should ask for deltas by desk, lane, entity, and `--since`, then deep-analyze only the changed blob paths returned.

## Safety

Examples use only Acme and Competitor A placeholders. Do not commit credentials, customer data, real company names, or private source URLs.
