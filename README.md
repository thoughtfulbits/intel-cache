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

Fetch mode is selected with `INTEL_CACHE_FETCH` and defaults to `http`, which uses
stdlib `urllib`. Future fetch backends can hang off this environment variable
without putting API keys or private connector config in the repo.

Hashing defaults to raw response bytes. Set `INTEL_CACHE_HASH=normalized` or pass
`--hash-mode normalized` to strip conservative volatile lines such as
`Last updated: ...`, `Generated at: ...`, and cookie headers before calculating
the SHA-256. Source URL identity always drops common tracking query params such
as `utm_*`, `gclid`, and fragments.

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
intel-cache warm --desk acme-desk --summary
intel-cache warm --all --concurrency 8 --summary
```

`warm` continues after per-URL failures and reports each failed URL as a
structured row. With `--summary`, output includes deterministic
`changed`/`unchanged`/`failed` counts so ops bots do not need to summarize a
partial run with an LLM.

List deltas:

```bash
intel-cache deltas --desk acme-desk --lane product --since 2026-01-01
intel-cache deltas --entity competitor-a
intel-cache deltas --desk acme-desk --lane product --format brief --preview-chars 200
```

Relative windows are supported for bot-friendly polling:

```bash
intel-cache deltas --desk acme-desk --lane product --since 24h
```

## Specialist quiet-gate contract

Specialists should use `gate` before spending AI tokens:

```bash
intel-cache gate --desk acme-desk --lane product --since 24h --format brief
```

Exit codes are the contract:

- `0`: no unacknowledged deltas; exit quietly and do no scrape/analysis work.
- `1`: deltas exist; stdout contains only deterministic source metadata
  (`entity`, `url`, short SHA, previous SHA, `changed_at`, byte size, blob path,
  and optional preview text).

`gate` uses a per-`desk`/`lane` watermark so a specialist does not reprocess the
same changed source every morning. Acknowledge after successful analysis:

```bash
intel-cache deltas --desk acme-desk --lane product --unacked --ack --quiet
```

You can also use `deltas --gate` when you want the same exit-code behavior on
the existing command:

```bash
intel-cache deltas --desk acme-desk --lane product --gate --quiet
```

## Local utility commands

Load example or fleet seed files without ad-hoc Python:

```bash
intel-cache seed --path examples/acme
# "import" is an alias:
intel-cache import --path examples/acme
```

Inspect cache health without an AI summary pass:

```bash
intel-cache status
```

Produce a deterministic unified diff between the latest two cached versions of
an entity source:

```bash
intel-cache diff --entity competitor-a
intel-cache diff --entity competitor-a --url https://example.com/competitor-a/news
intel-cache diff --entity competitor-a --sha-a <old_sha> --sha-b <new_sha>
```

## Architecture

```text
entities.json          entity registry: ids, aliases, domains, source URLs
subscriptions.json     desk subscriptions: desk_id -> entity_ids + lanes
blobs/<sha256>         fetched source bodies, content-addressed
sources/<entity>/<key> latest source metadata and current SHA-256
deltas.jsonl           append-only changed-source events
watermarks.json        per-desk/lane specialist ack cursors
```

On every fetch, `intel-cache`:

1. Reads the source with `urllib`.
2. Calculates the response body's SHA-256.
3. Stores the blob at `blobs/<sha256>`.
4. Compares the SHA with the latest metadata for that entity/source.
5. Appends a delta only if the SHA changed.

Specialists should call `gate` or ask for deltas by desk, lane, entity, and
`--since`, then deep-analyze only the changed blob paths returned.

## Safety

Examples use only Acme and Competitor A placeholders. Do not commit credentials, customer data, real company names, or private source URLs.
