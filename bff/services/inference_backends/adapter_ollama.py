"""Ollama backend adapter."""

from __future__ import annotations

import os

from ._common import probe_ollama_tags
from .types import BackendHealth, BackendMeta


class OllamaBackend:
    id = "ollama"
    display_name = "Ollama"
    supports_streaming = True
    role_hint = "any"

    def __init__(self, base_url: str | None = None) -> None:
        # OLLAMA_URL is the native root (no /v1). The router uses the
        # same env var elsewhere; keep names aligned.
        self.base_url = base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")

    async def health(self) -> BackendHealth:
        return await probe_ollama_tags(self.base_url)

    def meta(self, health: BackendHealth) -> BackendMeta:
        return BackendMeta(
            id=self.id,
            display_name=self.display_name,
            base_url=self.base_url,
            supports_streaming=self.supports_streaming,
            role_hint=self.role_hint,
            health=health,
        )
