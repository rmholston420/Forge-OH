"""ports.embeddings — EmbeddingsPort Protocol (ADR-073).

Split off ``LLMPort.embed()`` (ADR-063) into a dedicated capability port.
Rationale is documented in `docs/adrs/ADR-073-embeddings-port.md`:

- Category coupling: chat LLM backends (e.g. llama-swap) should not be
  forced to implement embedding surfaces they don't natively provide.
- Untyped `dict[str, Any]` return on ``LLMPort.embed()`` forces every
  caller to know Ollama's response shape. This port returns typed
  `list[list[float]]` vectors.
- Zero-trust invariants: consumers (``VectorPort.upsert``) enforce
  provenance + confidence at the storage seam; embed generation is a
  pure compute port that returns vectors of a declared dimension.

Contract:

- ``embed(texts=...)`` is **batch-only**. Single-text callers pass
  ``embed(texts=[text])[0]``. Prevents the "single-str vs list-of-str"
  dispatch mess that ``LLMPort.embed()`` currently has.
- ``dimensions(model=...)`` is called once at collection-create time by
  ``VectorPort`` adapters. Runtime ``len(embed(...)[0])`` MUST match or
  callers raise ``EmbeddingDimensionMismatch``.
- ``is_healthy()`` is a non-throwing sync probe (ADR-023 rule 5 reused).
- ``close()`` is idempotent.

References:
    - ADR-073 (this port's authority)
    - ADR-023 (LLMPort health-probe rules — reused here)
    - ADR-026 (VectorPort — downstream consumer)
    - ADR-054 (Stage 6.3.9 factory parity — reason ``LLMPort.embed()``
      keeps a deprecation window rather than being deleted immediately)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = [
    "EmbeddingError",
    "EmbeddingDimensionMismatch",
    "EmbeddingsPort",
]


class EmbeddingError(RuntimeError):
    """Backend failure surfacing from an ``EmbeddingsPort.embed`` call.

    Adapters MUST raise this (never return partial results) when any text
    in the batch fails to embed. Callers treat this as a full-batch
    failure and do not retry a partial subset.
    """


class EmbeddingDimensionMismatch(RuntimeError):
    """Runtime vector dimension does not match ``dimensions(model=...)``.

    Raised by callers (e.g. ``VectorPort`` adapters) when they detect
    that ``len(embed(texts=[t])[0]) != dimensions(model=m)``. Signals
    either a misconfigured collection or a model swap without a
    collection migration.
    """


@runtime_checkable
class EmbeddingsPort(Protocol):
    """Formal port for text-to-vector transformation.

    Implementations MUST be safe for concurrent ``embed`` calls from
    multiple coroutines. ``close`` MUST be idempotent. All async methods
    MUST NOT block the event loop.
    """

    async def embed(
        self,
        *,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Return one vector per input text, same length and order as ``texts``.

        Args:
            texts: Batch of strings to embed. Empty list returns ``[]``.
                Adapters MAY reject batches larger than a backend-specific
                cap; when they do, they raise ``EmbeddingError``.
            model: Override the adapter's default model. When ``None``,
                the adapter uses its constructor-configured default.

        Returns:
            A list of vectors (list-of-floats), each of the length
            declared by ``dimensions(model=model)``. Never partial.

        Raises:
            EmbeddingError: The backend failed to embed any text in the
                batch. The caller MUST treat the full batch as failed.
        """
        ...

    async def dimensions(self, *, model: str | None = None) -> int:
        """Declared vector dimension for ``model``.

        Args:
            model: When ``None``, the adapter's default model's dimension.

        Returns:
            Positive integer vector dimension.

        Raises:
            EmbeddingError: The model is not known to the backend.
        """
        ...

    def is_healthy(self) -> bool:
        """Non-throwing sync probe of adapter reachability.

        Returns ``False`` (never raises) when the adapter cannot reach
        its backend. Callers use this for /health surfacing without
        risking an exception on a healthy code path.
        """
        ...

    async def close(self) -> None:
        """Release backend resources. Idempotent — safe to call twice."""
        ...
