"""Unit tests for TrajectoryEmbedder (Rec #3, Slice F.3).

The real BAAI/bge-code-v1 model is 5+ GB and depends on torch+CUDA,
which we don't want in the unit suite. Every test that involves an
encode call uses a fake loader that returns deterministic vectors.
"""

from __future__ import annotations

import pytest

from openhands_tools_ext.trajectory.embedder import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_MODEL_NAME,
    TrajectoryEmbedder,
    build_query_text,
    build_record_text,
    get_default_embedder,
    reset_default_embedder,
)
from openhands_tools_ext.trajectory.schema import (
    TrajectoryRecord,
    TrajectoryStatus,
    make_trajectory_id,
)


class FakeEncoder:
    """Deterministic stand-in for a SentenceTransformer.

    Records every call and returns fixed-length "vectors" (Python
    lists) so tests can assert on both the call and the return shape.
    """

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim
        self.calls: list[tuple[str | list[str], bool, bool]] = []

    def encode(
        self,
        sentences: str | list[str],
        *,
        normalize_embeddings: bool = False,
        convert_to_numpy: bool = False,
    ) -> object:
        self.calls.append((sentences, normalize_embeddings, convert_to_numpy))
        if isinstance(sentences, str):
            return [float(len(sentences) % 7)] * self.dim
        return [[float((len(s) + i) % 7)] * self.dim for i, s in enumerate(sentences)]


def _make_record() -> TrajectoryRecord:
    return TrajectoryRecord(
        trajectory_id=make_trajectory_id("run1"),
        run_id="run1",
        session_id="sess",
        task_description="fix null deref in RunMetadataStore.get",
        plan="1. reproduce\n2. patch\n3. verify",
        symptom="AttributeError on None",
        repograph_symbols=["bff.services.run_metadata_store.get"],
        final_status=TrajectoryStatus.SUCCESS,
        created_at="2026-08-03T12:00:00Z",
    )


class TestConstants:
    def test_defaults(self) -> None:
        assert DEFAULT_MODEL_NAME == "BAAI/bge-code-v1"
        assert DEFAULT_EMBEDDING_DIM == 1536


class TestBuildQueryText:
    def test_task_only(self) -> None:
        assert build_query_text("do the thing") == "do the thing"

    def test_task_with_symptom(self) -> None:
        out = build_query_text("do the thing", "boom")
        assert "do the thing" in out
        assert "symptom: boom" in out
        assert out.index("do the thing") < out.index("symptom: boom")

    def test_ignores_whitespace_only_symptom(self) -> None:
        assert build_query_text("t", "   ") == "t"


class TestBuildRecordText:
    def test_includes_all_signal_fields(self) -> None:
        rec = _make_record()
        out = build_record_text(rec)
        assert "fix null deref in RunMetadataStore.get" in out
        assert "symptom: AttributeError on None" in out
        assert "plan:" in out
        assert "reproduce" in out
        assert "symbols: bff.services.run_metadata_store.get" in out

    def test_ordering_stable(self) -> None:
        rec = _make_record()
        out1 = build_record_text(rec)
        out2 = build_record_text(rec)
        assert out1 == out2

    def test_omits_empty_optional_fields(self) -> None:
        bare = TrajectoryRecord(
            trajectory_id="t",
            run_id="r",
            session_id="s",
            task_description="hi",
            final_status=TrajectoryStatus.SUCCESS,
            created_at="2026-08-03T12:00:00Z",
        )
        out = build_record_text(bare)
        assert out == "hi"


class TestTrajectoryEmbedder:
    def test_lazy_load(self) -> None:
        calls: list[tuple[str, str]] = []

        def loader(name: str, device: str) -> FakeEncoder:
            calls.append((name, device))
            return FakeEncoder(dim=8)

        emb = TrajectoryEmbedder(model_name="fake", device="cpu", loader=loader)
        assert emb.is_loaded() is False
        assert calls == []
        emb.embed("hello")
        assert emb.is_loaded() is True
        assert calls == [("fake", "cpu")]

    def test_load_is_idempotent(self) -> None:
        calls: list[tuple[str, str]] = []

        def loader(name: str, device: str) -> FakeEncoder:
            calls.append((name, device))
            return FakeEncoder()

        emb = TrajectoryEmbedder(device="cpu", loader=loader)
        emb.load()
        emb.load()
        emb.embed("hi")
        assert len(calls) == 1

    def test_embed_returns_plain_floats(self) -> None:
        emb = TrajectoryEmbedder(device="cpu", loader=lambda n, d: FakeEncoder(dim=4))
        vec = emb.embed("hi")
        assert vec == [float((len("hi")) % 7)] * 4
        assert all(isinstance(x, float) for x in vec)

    def test_embed_passes_normalize_and_numpy_flags(self) -> None:
        enc = FakeEncoder(dim=2)
        emb = TrajectoryEmbedder(device="cpu", loader=lambda n, d: enc)
        emb.embed("hello")
        # (sentences, normalize_embeddings, convert_to_numpy)
        assert enc.calls == [("hello", True, True)]

    def test_embed_batch(self) -> None:
        enc = FakeEncoder(dim=4)
        emb = TrajectoryEmbedder(device="cpu", loader=lambda n, d: enc)
        out = emb.embed_batch(["a", "bb", "ccc"])
        assert len(out) == 3
        assert all(len(v) == 4 for v in out)

    def test_embed_batch_empty_short_circuits(self) -> None:
        loaded: list[bool] = []

        def loader(n: str, d: str) -> FakeEncoder:
            loaded.append(True)
            return FakeEncoder()

        emb = TrajectoryEmbedder(device="cpu", loader=loader)
        assert emb.embed_batch([]) == []
        # Empty input must not trigger a model load.
        assert loaded == []

    def test_embed_record_uses_build_record_text(self) -> None:
        enc = FakeEncoder(dim=4)
        emb = TrajectoryEmbedder(device="cpu", loader=lambda n, d: enc)
        rec = _make_record()
        emb.embed_record(rec)
        # The FakeEncoder captured the exact text we sent.
        sent = enc.calls[0][0]
        assert isinstance(sent, str)
        assert sent == build_record_text(rec)

    def test_device_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_OH_EMBED_DEVICE", "cuda:1")
        emb = TrajectoryEmbedder(loader=lambda n, d: FakeEncoder())
        assert emb.device == "cuda:1"

    def test_default_device_falls_back_to_cpu_when_no_cuda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FORGE_OH_EMBED_DEVICE", raising=False)
        # Force the torch import to fail so autodetect returns "cpu".
        import builtins

        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "torch":
                raise ImportError("no torch in this test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        emb = TrajectoryEmbedder(loader=lambda n, d: FakeEncoder())
        assert emb.device == "cpu"


class TestGetDefaultEmbedder:
    def test_singleton_reused(self) -> None:
        reset_default_embedder()
        a = get_default_embedder()
        b = get_default_embedder()
        assert a is b

    def test_reset(self) -> None:
        reset_default_embedder()
        a = get_default_embedder()
        reset_default_embedder()
        b = get_default_embedder()
        assert a is not b
