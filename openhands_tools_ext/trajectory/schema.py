"""TrajectoryRecord schema — one structured record per completed run.

A ``TrajectoryRecord`` is Rec #3's storage unit: the durable, embeddable
memory of a completed task. It is written once at run-completion by the
trajectory writer hook, indexed into a local SQLite case base, and
retrieved before a new task starts so the agent can inject the most
similar prior case(s) as few-shot context.

Design invariants
-----------------
- **Local-first**: no cloud fields, no auth. Records live in
  ``~/.forge-oh/trajectories.db``.
- **Verification-aware**: every record carries the sequence of
  ``VerificationStep`` iterations from Rec #2, plus a top-level
  ``final_status``. Retrieval defaults to ``verified_only=True`` so
  known-failed cases don't propagate bad patterns.
- **Graph-linked**: ``repograph_symbols`` names the RepoGraph symbol ids
  touched by this run's diffs. Retrieval co-ranks semantic similarity
  with structural overlap.
- **Embedding is optional at write-time**: the writer may emit a record
  with ``embedding=None`` and let a batch indexer fill it in. This
  avoids blocking run completion on GPU availability.

Parity with the frontend Zod schema (``src/lib/schemas/trajectory.ts``)
is enforced by ``tests/trajectory/test_schema.py::TestFrontendParity``.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from openhands_tools_ext.verify.schema import VerificationStep


class TrajectoryStatus(str, Enum):
    """Terminal status of a run at the moment its trajectory was recorded."""

    SUCCESS = "success"  # task completed, verify passed (or was N/A)
    FAILED = "failed"  # task completed with a hard failure
    VERIFIED_FAILURE = "verified_failure"  # verify loop exhausted retries
    ABORTED = "aborted"  # user stop / timeout / crash
    UNKNOWN = "unknown"  # writer could not determine


class TrajectoryDiff(BaseModel):
    """One file-level diff captured by the trajectory writer.

    We store per-file summaries rather than raw unified diffs to keep
    records embeddable and small. The raw diff is recoverable from the
    workspace git history when needed.
    """

    path: str
    lines_added: int = Field(ge=0)
    lines_removed: int = Field(ge=0)
    summary: str = ""  # short natural-language description


class TrajectoryRecord(BaseModel):
    """Structured record of one completed run for case-based retrieval.

    Attributes
    ----------
    trajectory_id : str
        Unique id for this record. Convention: ``traj_<run_id>``.
    run_id : str
        The BFF run id this trajectory belongs to.
    session_id : str
        The agent-server session id (matches
        ``.forge-oh/verify-state.json`` keys).
    task_description : str
        The user-visible task prompt / instruction. This is the primary
        semantic-query surface for retrieval.
    plan : str
        The agent's own plan text at task-start. Empty if the run had no
        planning step.
    diffs : list[TrajectoryDiff]
        Per-file diff summaries. Empty for read-only runs.
    verify_iterations : list[VerificationStep]
        Every verify-loop iteration observed during the run, in order.
        Empty if the run never triggered verify.
    final_status : TrajectoryStatus
        Terminal outcome. Retrieval filters on this by default.
    symptom : str
        For debug-style tasks: the observed error / behavior text that
        motivated the task. Empty for greenfield tasks.
    repograph_repo_key : str
        The ``repo_key`` this trajectory's diffs touched. Used to scope
        symbol-overlap co-ranking to the right graph.
    repograph_symbols : list[str]
        RepoGraph symbol ids touched by the diffs (fully-qualified,
        matches ``Symbol.id`` in the graph). Empty if no graph was
        indexed or no symbols could be resolved.
    embedding : list[float] | None
        The record's embedding vector. ``None`` before indexing;
        populated by the embedder. Dimensionality is fixed by the
        embedder impl (``bge-code-v1`` → 1536).
    embedding_model : str
        Identifier of the model that produced ``embedding``. Empty when
        ``embedding is None``.
    created_at : str
        ISO-8601 UTC timestamp of record creation. String rather than
        datetime for trivial JSON roundtrip.
    """

    model_config = ConfigDict(use_enum_values=True)

    trajectory_id: str
    run_id: str
    session_id: str
    task_description: str
    plan: str = ""
    diffs: list[TrajectoryDiff] = Field(default_factory=list)
    verify_iterations: list[VerificationStep] = Field(default_factory=list)
    final_status: TrajectoryStatus
    symptom: str = ""
    repograph_repo_key: str = ""
    repograph_symbols: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    embedding_model: str = ""
    created_at: str


# Canonical BFF endpoint prefix for trajectory read APIs.
TRAJECTORY_API_PREFIX: Literal["/trajectories"] = "/trajectories"

# Default retrieval budget (top-k) for the case-retrieval widget.
DEFAULT_RETRIEVAL_K: int = 3

# Weights for co-ranking. Retriever computes:
#   score = SEMANTIC_WEIGHT * semantic_score + SYMBOL_WEIGHT * symbol_overlap
# Both components are normalized to [0, 1]. See tests/trajectory/test_retriever.py.
SEMANTIC_WEIGHT: float = 0.7
SYMBOL_WEIGHT: float = 0.3


def make_trajectory_id(run_id: str) -> str:
    """Return the canonical trajectory id derived from a run id."""
    return f"traj_{run_id}"
