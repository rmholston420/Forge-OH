# Forge-OH BFF

The Forge-OH BFF is the FastAPI backend for Forge-OH. It fronts the OpenHands SDK and provides the backend API surface used by the frontend.[file:221]

## Pinned stack

The BFF uses a pinned Python runtime stack so local development and lockfile generation stay reproducible.[file:220][file:221]

- Python: 3.13.x
- FastAPI: `fastapi==0.115.5`
- Uvicorn: `uvicorn==0.39.0`
- Pydantic: `pydantic==2.12.5`
- Pydantic Settings: `pydantic-settings==2.6.1`
- OpenHands SDK: `openhands-sdk==1.29.3`
- Python Socket.IO: `python-socketio==5.11.4`
- AIOHTTP: `aiohttp==3.11.10`
- AioSQLite: `aiosqlite==0.22.1`

Canonical files:

- Runtime requirements: `bff/requirements.txt`
- Frozen environment snapshot: `bff/requirements.lock`

`bff/requirements.txt` is intentionally the minimal runtime set, while `bff/requirements.lock` captures the full resolved environment generated from a clean install.[file:220][file:221]

## Local environment

Use a dedicated virtual environment for BFF work so it does not get polluted by vLLM, Torch, or other model-hosting dependencies that belong in a separate environment.[file:221]

```bash
cd ~/Forge-OH
python3 -m venv .venv-bff
source .venv-bff/bin/activate
python -m pip install "pip<27"
python -m pip install -r bff/requirements.txt
```

## Running the BFF

The BFF should run with `bff.main:app`, not `bff.main:app_with_sio`, and your local dev port is `8081`.[file:220]

### Preferred launcher

```bash
cd ~/Forge-OH
./scripts/dev-bff.sh
```

### Direct uvicorn command

```bash
cd ~/Forge-OH
source .venv-bff/bin/activate
uvicorn bff.main:app --host 0.0.0.0 --port 8081 --reload
```

## Tests

Run the BFF tests from the dedicated environment:

```bash
cd ~/Forge-OH
source .venv-bff/bin/activate
pytest bff
```

## Data files

The BFF may create local SQLite databases during development, including runtime state under `bff/data/` and other app data under `data/`.[file:221] These directories are generated at runtime and are git-ignored, so they should not be committed.[file:221]

## Updating dependencies

When you change the BFF runtime stack:

1. Update `bff/requirements.txt`.
2. Install into a clean BFF environment.
3. Regenerate the lockfile.

```bash
cd ~/Forge-OH
source .venv-bff/bin/activate
python -m pip install -r bff/requirements.txt
python -m pip freeze > bff/requirements.lock
```

Keep `docs/Forge-OH-Build-Plan-Definitive.md` aligned with any changes to the pinned runtime versions or startup command.[file:220]
