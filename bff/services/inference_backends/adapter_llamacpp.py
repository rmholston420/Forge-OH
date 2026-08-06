"""llama.cpp server adapter.

Not deployed on Colossus in Stage 2 (per amended plan § 2.3). The
adapter exists so the UI can show configured-but-unreachable state
when someone points ``LLAMACPP_URL`` at a real server later.
"""

from __future__ import annotations

import os

from ._common import probe_openai_v1_models
from .types import BackendHealth, BackendMeta


class LlamaCppBackend:
    id = "llamacpp"
    display_name = "llama.cpp"
    supports_streaming = True
    role_hint = "any"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv(
            "LLAMACPP_URL", "http://localhost:8080"
        )

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
