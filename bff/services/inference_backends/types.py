"""Type declarations for InferenceBackend health inventory.

Kept in a separate module so router code and adapter code can import
these without pulling in httpx.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Canonical backend ids. The router uses these as the ``backend_id``
# opt-in parameter and the UI uses them as the radio-group value.
BackendKind = Literal[
    "ollama",
    "vllm-coder",
    "vllm-planner",
    "vllm-legacy",
    "llamacpp",
    "sglang",
]

# Health state a UI can render directly. ``muted`` means the backend
# is configured but no live probe has run yet (or was skipped because
# the runtime is documented-only on this host).
HealthState = Literal["healthy", "degraded", "unhealthy", "muted"]


@dataclass(frozen=True)
class BackendHealth:
    """Point-in-time health snapshot for a single backend.

    ``state`` maps directly onto the existing ``badge badge--*`` CSS
    classes used by the MCP card:

    - ``healthy``   → ``badge--success``
    - ``degraded``  → ``badge--warning``
    - ``unhealthy`` → ``badge--error``
    - ``muted``     → ``badge--muted``
    """

    state: HealthState
    latency_ms: int | None
    model_count: int | None
    error: str | None


@dataclass(frozen=True)
class BackendMeta:
    """Immutable metadata + a live health snapshot for a backend.

    Serialized to JSON via the ``as_dict`` helper below (Pydantic
    would be overkill for a read-only DTO with a fixed shape).
    """

    id: BackendKind
    display_name: str
    base_url: str
    supports_streaming: bool
    role_hint: Literal["coder", "planner", "any", "probe"]
    health: BackendHealth

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "displayName": self.display_name,
            "baseUrl": self.base_url,
            "supportsStreaming": self.supports_streaming,
            "roleHint": self.role_hint,
            "health": {
                "state": self.health.state,
                "latencyMs": self.health.latency_ms,
                "modelCount": self.health.model_count,
                "error": self.health.error,
            },
        }
