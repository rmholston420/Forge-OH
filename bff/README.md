# Forge-OH BFF

The Forge-OH BFF is a FastAPI-based backend that fronts the OpenHands SDK and provides the API surface for the Forge-OH frontend.[file:221] This document describes the pinned runtime stack, the recommended local environment, and how to run and test the BFF.

## Pinned stack

The BFF runs against a pinned Python stack to keep local dev and CI reproducible.[file:221]

- Python: 3.13.x  
- FastAPI: \`fastapi==0.115.5\`  
- Uvicorn: \`uvicorn==0.39.0\`  
- Pydantic: \`pydantic==2.12.5\`  
- Pydantic Settings: \`pydantic-settings==2.6.1\`  
- OpenHands SDK: \`openhands-sdk==1.29.3\`  
- Python Socket.IO: \`python-socketio==5.11.4\`  
- AIOHTTP: \`aiohttp==3.11.10\`  
- AioSQLite: \`aiosqlite==0.22.1\`  

Canonical files:

- Runtime requirements: \`bff/requirements.txt\`  
- Frozen lockfile: \`bff/requirements.lock\` (generated via \`pip freeze\` from \`bff/requirements.txt\`)  

\`bff/requirements.txt\` is intentionally limited to the runtime stack; the full resolved environment (including transitive dependencies like \`lmnr\`, FastMCP, and Opentelemetry) lives in \`bff/requirements.lock\`.[file:221]

## Local environment (.venv-bff)

Use a dedicated virtual environment for BFF work so it is not polluted by vLLM, Torch, or model-hosting packages.[file:221]

```bash
cd ~/Forge-OH

python3 -m venv .venv-bff
source .venv-bff/bin/activate

# Keep pip in a stable range; no need to chase latest.
python -m pip install "pip<27"

# Install the pinned BFF runtime stack.
python -m pip install -r bff/requirements.txt
```

This environment should only be used for BFF work. Install vLLM, Torch, and other model-hosting dependencies in a separate environment if needed.[file:221]

## Running the BFF

From the repo root with \`.venv-bff\` activated:

```bash
cd ~/Forge-OH
source .venv-bff/bin/activate

uvicorn bff.main:app --host 0.0.0.0 --port 8000 --reload
```

The same \`bff.main:app\` entrypoint is referenced in \`docker-compose.dev.yml\` and CI workflows; \`bff.main:app_with_sio\` is no longer used.[file:220][file:221]

## Data and storage

The BFF uses local SQLite databases for certain features:

- Episodic memory: \`data/episodic_memory.db\`  
- Run metadata: \`bff/data/run_metadata.db\`  

These files are generated at runtime and **ignored by git**.[file:221] Do not commit them. If they become corrupted during development, you can delete them and let the BFF recreate them.

## Tests

To run the BFF test suite:

```bash
cd ~/Forge-OH
source .venv-bff/bin/activate

pytest bff
```

Tests assume the pinned stack from \`bff/requirements.txt\` is installed in the active environment.[file:221]

## Updating dependencies

When updating the BFF runtime stack:

1. Edit \`bff/requirements.txt\` (minimal runtime set).  
2. Recreate a clean environment or use \`.venv-bff\` to install from it.  
3. Regenerate \`bff/requirements.lock\` from the clean environment:

   ```bash
   cd ~/Forge-OH
   source .venv-bff/bin/activate

   python -m pip install -r bff/requirements.txt
   python -m pip freeze > bff/requirements.lock
   ```

4. Run the BFF tests and the frontend integration flows before committing.[file:221]

\`docs/Forge-OH-Build-Plan-Definitive.md\` should be updated to match any new pinned versions so the documentation stays in sync with the code.[file:220][file:221]
