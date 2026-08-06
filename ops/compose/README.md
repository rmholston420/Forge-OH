# ops/compose

Standalone Docker Compose files for local Forge-OH dependencies. Each file
in this directory is self-contained and can be brought up independently of
the others.

## SearXNG (Stage 6.1)

Local metasearch backing the `search_web` tool and `SearchPort` adapter.

```bash
# Bring up
cd ~/dev/forge-oh
docker compose -f ops/compose/searxng.yml up -d

# Verify (returns JSON with the query echoed back)
curl -s "http://127.0.0.1:18888/search?q=probe&format=json" | jq '.query'

# Tear down
docker compose -f ops/compose/searxng.yml down
```

Binding: `127.0.0.1:18888` (loopback-only, intentionally not `8888` — that
port is Kosmos ADR-010's SearXNG on the same workstation).

Environment variable consumed by the adapter:

- `FORGE_SEARXNG_BASE_URL` — default `http://127.0.0.1:18888`.

Setting `FORGE_SEARXNG_BASE_URL` (or `FORGE_SEARCH_EMIT_ENABLED=1`) also
un-gates the BFF's `POST /api/search/emit` bridge endpoint.
