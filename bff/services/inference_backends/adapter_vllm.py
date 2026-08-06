"""vLLM backend adapters — one class, three instantiations.

ADR-009 §3a: only one vLLM role can be resident on the 5090 at a
time. That's a *router* concern, enforced by ``ops/vllm_supervisor.sh``.
For inventory purposes each configured role/endpoint is its own
``BackendMeta`` so the UI can show them independently.

Endpoint sources (matches ``model_router.py``):

- ``LLM_CODER_URL``   default ``http://localhost:8501``  (coder role)
- ``LLM_PLANNER_URL`` default ``http://localhost:8511``  (planner role)
- ``VLLM_URL``        default ``http://localhost:8500``  (legacy F.18
  probe — kept for the settings UI health signal, not part of live
  routing per ``model_router.py`` docstring)
"""

from __future__ import annotations

import os

from ._common import probe_openai_v1_models
from .types import BackendHealth, BackendMeta


class VLLMBackend:
    """Generic vLLM adapter parametrized by id + display_name + env var."""

    supports_streaming = True

    def __init__(
        self,
        *,
        id: str,
        display_name: str,
        env_var: str,
        default_url: str,
        role_hint: str,
    ) -> None:
        self.id = id
        self.display_name = display_name
        self.role_hint = role_hint
        self.base_url = os.getenv(env_var, default_url)

    async def health(self) -> BackendHealth:
        return await probe_openai_v1_models(self.base_url)

    def meta(self, health: BackendHealth) -> BackendMeta:
        return BackendMeta(
            id=self.id,
            display_name=self.display_name,
            base_url=self.base_url,
            supports_streaming=self.supports_streaming,
            role_hint=self.role_hint,
            health=health,
        )


def vllm_coder() -> VLLMBackend:
    return VLLMBackend(
        id="vllm-coder",
        display_name="vLLM (coder role)",
        env_var="LLM_CODER_URL",
        default_url="http://localhost:8501",
        role_hint="coder",
    )


def vllm_planner() -> VLLMBackend:
    return VLLMBackend(
        id="vllm-planner",
        display_name="vLLM (planner role)",
        env_var="LLM_PLANNER_URL",
        default_url="http://localhost:8511",
        role_hint="planner",
    )


def vllm_legacy() -> VLLMBackend:
    return VLLMBackend(
        id="vllm-legacy",
        display_name="vLLM (legacy F.18 probe)",
        env_var="VLLM_URL",
        default_url="http://localhost:8500",
        role_hint="probe",
    )
