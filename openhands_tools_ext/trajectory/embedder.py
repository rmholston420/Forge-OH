"""Embedder for TrajectoryRecords (Rec #3, Slice F.3).

Default model: **BAAI/bge-code-v1** (1536-dim, Qwen2.5-Coder-1.5B-init,
top of CoIR at time of writing). Runs via ``sentence-transformers`` on
CUDA when available, CPU otherwise.

Design
------
- **Lazy singleton**: the underlying ``SentenceTransformer`` is
  expensive to load (~5 GB, seconds on cold start). We instantiate it
  the first time ``embed()``/``embed_batch()`` is called and reuse
  across calls.
- **Device autodetect**: ``FORGE_OH_EMBED_DEVICE`` env override wins,
  otherwise ``cuda`` if ``torch.cuda.is_available()`` else ``cpu``.
- **Deterministic on failure**: import errors are caught only at
  ``load()`` time so tests can substitute a fake loader without needing
  torch installed. Runtime failure (OOM etc.) propagates.
- **Deterministic text preparation**: :func:`build_query_text` and
  :func:`build_record_text` are pure functions so they can be reused by
  the indexer, retriever, and tests without touching the model.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Protocol

from openhands_tools_ext.trajectory.schema import TrajectoryRecord

DEFAULT_MODEL_NAME: str = "BAAI/bge-code-v1"
DEFAULT_EMBEDDING_DIM: int = 1536


class _EncoderLike(Protocol):
    """Minimal interface we need from the ST model.

    Kept narrow so tests can inject fakes without depending on
    sentence-transformers.
    """

    def encode(
        self,
        sentences: str | list[str],
        *,
        normalize_embeddings: bool = ...,
        convert_to_numpy: bool = ...,
    ) -> object: ...


def _select_device() -> str:
    """Return the device string honoring the env override."""
    override = os.environ.get("FORGE_OH_EMBED_DEVICE")
    if override:
        return override
    try:
        import torch  # type: ignore[import-not-found]

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _default_loader(model_name: str, device: str) -> _EncoderLike:
    """Load a real SentenceTransformer. Isolated so tests can bypass it."""
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    return SentenceTransformer(model_name, trust_remote_code=True, device=device)


def build_query_text(task_description: str, symptom: str = "") -> str:
    """Assemble the retrieval query string from a task/symptom pair.

    Kept trivial so the retriever can construct queries symmetrically
    with the record-side representation and get a shared textual space.
    """
    parts = [task_description.strip()]
    if symptom.strip():
        parts.append(f"symptom: {symptom.strip()}")
    return "\n".join(p for p in parts if p)


def build_record_text(record: TrajectoryRecord) -> str:
    """Textual projection of a trajectory used for embedding.

    Concatenates the fields that carry search-relevant signal — task,
    plan, symptom, and touched RepoGraph symbols — in a fixed order so
    repeated embeddings of the same record are stable.
    """
    parts = [record.task_description.strip()]
    if record.symptom.strip():
        parts.append(f"symptom: {record.symptom.strip()}")
    if record.plan.strip():
        parts.append(f"plan:\n{record.plan.strip()}")
    if record.repograph_symbols:
        parts.append("symbols: " + ", ".join(record.repograph_symbols))
    return "\n".join(p for p in parts if p)


class TrajectoryEmbedder:
    """Lazy singleton wrapper over an ST-style encoder.

    Parameters
    ----------
    model_name : str
        Model id. Default ``BAAI/bge-code-v1``.
    device : str | None
        Explicit device override; auto-selects from env / CUDA
        availability when ``None``.
    loader : Callable[[str, str], _EncoderLike] | None
        Injection point for tests; defaults to
        :func:`_default_loader`.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: str | None = None,
        *,
        loader: Callable[[str, str], _EncoderLike] | None = None,
    ) -> None:
        self.model_name = model_name
        self._device = device
        self._loader = loader or _default_loader
        self._model: _EncoderLike | None = None

    # -- lifecycle ----------------------------------------------------------

    @property
    def device(self) -> str:
        if self._device is None:
            self._device = _select_device()
        return self._device

    def load(self) -> None:
        """Force-load the underlying model if it isn't loaded yet."""
        if self._model is None:
            self._model = self._loader(self.model_name, self.device)

    def is_loaded(self) -> bool:
        return self._model is not None

    # -- encoding -----------------------------------------------------------

    def _to_float_list(self, arr: object) -> list[float]:
        """Coerce whatever the encoder returned into a plain ``list[float]``."""
        # numpy arrays expose tolist(); plain lists have it too via py 3.13,
        # so handle both without importing numpy at type-check time.
        tolist = getattr(arr, "tolist", None)
        if callable(tolist):
            raw = tolist()
        else:
            raw = list(arr)  # type: ignore[arg-type]
        return [float(x) for x in raw]

    def embed(self, text: str) -> list[float]:
        """Embed a single string. Returns a normalized 1536-dim vector."""
        self.load()
        assert self._model is not None
        vec = self._model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
        return self._to_float_list(vec)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed many strings at once. Empty input returns empty list."""
        if not texts:
            return []
        self.load()
        assert self._model is not None
        arrs = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        # `encode` on a list returns a 2D array-like; iterate rows.
        out: list[list[float]] = []
        rows = getattr(arrs, "tolist", None)
        if callable(rows):
            for row in rows():
                out.append([float(x) for x in row])
        else:
            for row in arrs:  # type: ignore[assignment]
                out.append(self._to_float_list(row))
        return out

    def embed_record(self, record: TrajectoryRecord) -> list[float]:
        """Embed a trajectory using :func:`build_record_text`."""
        return self.embed(build_record_text(record))


# Module-level singleton — call ``get_default_embedder()`` from
# indexer / retriever code paths to share one model across the process.
_DEFAULT_EMBEDDER: TrajectoryEmbedder | None = None


def get_default_embedder() -> TrajectoryEmbedder:
    """Return the process-wide default embedder, constructing it lazily."""
    global _DEFAULT_EMBEDDER
    if _DEFAULT_EMBEDDER is None:
        _DEFAULT_EMBEDDER = TrajectoryEmbedder()
    return _DEFAULT_EMBEDDER


def reset_default_embedder() -> None:
    """Reset the module singleton — test-only escape hatch."""
    global _DEFAULT_EMBEDDER
    _DEFAULT_EMBEDDER = None
