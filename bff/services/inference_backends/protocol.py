"""``InferenceBackend`` protocol.

All adapters implement this shape. Deliberately minimal — anything
richer belongs on ``route_by_role()`` in ``model_router.py``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import BackendHealth, BackendMeta


@runtime_checkable
class InferenceBackend(Protocol):
    """A named, health-checkable inference runtime."""

    id: str
    display_name: str
    base_url: str
    supports_streaming: bool
    role_hint: str

    async def health(self) -> BackendHealth:
        """Return a fresh health snapshot.

        Adapters MUST NOT raise from this method. Any exception during
        the probe becomes a ``BackendHealth`` with ``state='unhealthy'``
        and the exception string in ``error``.
        """

    def meta(self, health: BackendHealth) -> BackendMeta:
        """Combine immutable metadata with a health snapshot."""
