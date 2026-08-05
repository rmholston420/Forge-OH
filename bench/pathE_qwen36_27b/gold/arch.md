**Decision:** Keep `bff/openhands_client.py`; delete `bff/services/openhands_client.py`.

**Justification:** Inspecting the repo shows `bff/openhands_client.py` is the canonical, working client: it owns the shared `httpx.AsyncClient` lifecycle (`startup`/`shutdown`/`lifespan`/`get_client`), its docstring names its own path, and its relative import `from .settings import get_settings` binds it to the `bff/` package root. The live importer graph points exclusively at the flat path — `bff/main.py` wires `from bff.openhands_client import startup, shutdown` into the FastAPI lifespan, and `bff/routers/runs.py` already imports `from bff.openhands_client import get_client` — while `bff/services/openhands_client.py` is a stale-refactor shim with zero importers. Deleting the shim changes no behavior; deleting the flat file would break app startup and the exact `runs.py` wiring Step 3 depends on. So the "services layer wins" heuristic is wrong here: the file that matches the code content and importer graph survives.

1. **Kept:** `bff/openhands_client.py` — **Deleted:** `bff/services/openhands_client.py`

2. **Grep for imports of the deleted path:**
   ```bash
   grep -rnE --include='*.py' 'services\.openhands_client|from (bff\.|\.{1,2})?services import openhands_client' .
   ```
   (Expected: zero hits — the shim has no importers at baseline.)

3. **Rewrite any such imports to the kept path:**
   ```bash
   grep -rlE --include='*.py' 'services.*openhands_client' . | xargs -r sed -i -E 's/\.services\.openhands_client/.openhands_client/g; s/from bff\.services import openhands_client/from bff import openhands_client/g; s/from (\.{1,2})services import openhands_client/from \1 import openhands_client/g'
   ```
   (No-op at baseline; included as a safety net.)

4. **Convention-based reason:** The convention above reserves `bff/*.py` for the app entrypoint, config, and cross-cutting concerns — and this module is exactly a cross-cutting lifecycle concern: a process-wide singleton `httpx.AsyncClient` whose `startup`/`shutdown` are wired into `main.py`'s FastAPI lifespan alongside `settings.py`, not business logic like the real `services/` modules (`model_router.py`, `episodic_memory.py`). Under that same layout, `bff/routers/runs.py` importing `bff.openhands_client` is fully convention-compliant, so keeping the flat file satisfies both the layering rule and the actual importer graph, while the `services/` copy is an empty-shim violation of "services contain fully real, working code."
