"""InferenceBackend health-inventory + selection layer (Stage 2.1).

This package sits ABOVE the existing role-routing core in
``bff/services/model_router.py``. It does not replace
``route_by_role()`` — it exposes the concrete runtimes (Ollama,
vLLM coder/planner/legacy, llama.cpp, SGLang) as first-class,
health-checked entities so the UI can show live inventory and the
run-creation path can optionally pin a specific backend.

See ``docs/reconciliation-plan-stage-2.md`` § 2.1 for the full
contract and the invariant that ``route_by_role()`` behavior is
byte-for-byte preserved when ``backend_id`` is ``None`` (default).
"""

from .protocol import InferenceBackend
from .registry import BACKEND_REGISTRY, get_backend, list_backends
from .types import BackendHealth, BackendKind, BackendMeta

__all__ = [
    "BACKEND_REGISTRY",
    "BackendHealth",
    "BackendKind",
    "BackendMeta",
    "InferenceBackend",
    "get_backend",
    "list_backends",
]
