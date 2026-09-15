# Acme example

Placeholder example data for an Acme desk with one competitor.

The example intentionally uses only:

- Acme
- Competitor A

Load the files into a cache directory with the CLI:

```bash
mkdir -p /tmp/intel-cache-example
intel-cache --cache-dir /tmp/intel-cache-example seed --path examples/acme
INTEL_CACHE_DIR=/tmp/intel-cache-example intel-cache deltas --desk acme-desk
```
