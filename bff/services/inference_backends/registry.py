"""Backend registry — the canonical inventory of configured backends.

``BACKEND_REGISTRY`` is a dict keyed by ``BackendKind``. Order matters:
the ``GET /api/inference-backends`` endpoint returns entries in this
order, which is what the UI radio group renders.

Order rationale:
1. ``ollama``       — always-on primary Ollama runtime.
2. ``vllm-coder``   — canonical coder role (ADR-009 §3a).
3. ``vllm-planner`` — canonical planner role (ADR-009 §3a).
4. ``vllm-legacy``  — F.18 probe endpoint, listed but expected muted.
5. ``llamacpp``     — configured-only on Colossus, not deployed.
6. ``sglang``       — configured-only on Colossus, not deployed.
"""

from __future__ import annotations

import asyncio
from typing import Iterable

from .adapter_llamacpp import LlamaCppBackend
from .adapter_ollama import OllamaBackend
from .adapter_sglang import SGLangBackend
from .adapter_vllm import vllm_coder, vllm_legacy, vllm_planner
from .protocol import InferenceBackend
from .types import BackendMeta


def _build_registry() -> dict[str, InferenceBackend]:
    return {
        "ollama": OllamaBackend(),
        "vllm-coder": vllm_coder(),
        "vllm-planner": vllm_planner(),
        "vllm-legacy": vllm_legacy(),
        "llamacpp": LlamaCppBackend(),
        "sglang": SGLangBackend(),
    }


BACKEND_REGISTRY: dict[str, InferenceBackend] = _build_registry()


def get_backend(backend_id: str) -> InferenceBackend | None:
    """Look up an adapter by canonical id, or ``None`` if unknown."""

    return BACKEND_REGISTRY.get(backend_id)


async def list_backends(
    backends: Iterable[InferenceBackend] | None = None,
) -> list[BackendMeta]:
    """Probe all configured backends in parallel; return their metas.

    Adapters MUST NOT raise from ``health()``; every task returns a
    ``BackendHealth`` even on transport failure. This function is safe
    to call from a request handler.
    """

    items = list(backends if backends is not None else BACKEND_REGISTRY.values())
    healths = await asyncio.gather(*[b.health() for b in items])
    return [b.meta(h) for b, h in zip(items, healths, strict=True)]
