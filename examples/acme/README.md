# Acme example

Placeholder example data for an Acme desk with one competitor.

The example intentionally uses only:

- Acme
- Competitor A

Load the files into a cache directory by copying them to the cache root:

```bash
mkdir -p /tmp/intel-cache-example
cp examples/acme/entities.json /tmp/intel-cache-example/entities.json
cp examples/acme/subscriptions.json /tmp/intel-cache-example/subscriptions.json
INTEL_CACHE_DIR=/tmp/intel-cache-example intel-cache deltas --desk acme-desk
```
