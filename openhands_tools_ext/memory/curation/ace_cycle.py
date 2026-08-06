"""ACE-style memory curation cycle (Stage 5.5, ADR-023).

The generate → reflect → curate cycle runs at write time. Its job is to
decide whether a candidate observation should be persisted, merged with
existing memory, or discarded as a duplicate.

## Design invariants (ADR-023)

- **Triple-shaped**, not free-string. Every candidate carries the
  ``subject`` / ``predicate`` / ``object`` triple that ADR-021 pins as
  the ``:MemoryEvent`` shape. Free-string observations must be lifted
  to a triple by the caller before entering the cycle.
- **Deterministic first pass.** Reflection uses string-overlap over
  the normalized triple. No LLM call, no embedding-similarity call.
  Escalation to embedding similarity requires an ADR-023 amendment
  (still no LLM call).
- **Zero-trust floor preserved.** ``curated_write`` calls
  ``adapter.write_event`` on the ``keep`` / ``merge`` branch; the
  adapter's port-layer ``validate_zero_trust_write`` runs first and
  raises ``ValueError`` on invalid provenance/confidence. Curation
  MUST NOT swallow that error.
- **Library-only until a caller exists.** No wire-in from higher-stack
  callers this stage — this module ships as a library available for
  future stages (e.g., when Letta-style memory blocks land).

## Reflection semantics

The reflection function returns a natural-language string, and
``curate`` inspects it for substrings. This mirrors the plan §5.5.1
sketch to keep future LLM/embedding escalations drop-in-compatible
(they just return a different reflection string; ``curate`` is unchanged).

- reflection contains ``"duplicate"`` → :class:`CurationResult` action=``discard``
- reflection contains ``"refine"``    → action=``merge`` (persist candidate anyway;
  merge semantics beyond persistence are deferred to a future ADR)
- otherwise                            → action=``keep``

References
----------
- ADR-021 §D1 — ``:MemoryEvent`` triple shape
- ADR-023 — this cycle's decision + escalation policy
- ADR-022 — zero-trust write validators (invoked by ``adapter.write_event``)
- ``Forge-OH-reconciliation-plan-v1-stage-5.md`` §5.5
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from openhands_tools_ext.memory.ports.memory import MemoryHit, MemoryPort

__all__ = [
    "CurationCandidate",
    "CurationResult",
    "generate_candidate",
    "reflect_on_candidate",
    "curate",
    "curated_write",
]


CurationAction = Literal["keep", "merge", "discard"]


@dataclass(frozen=True, slots=True)
class CurationCandidate:
    """One observation entering the ACE cycle.

    Triple-shaped per ADR-021 / ADR-023 D1. All fields are the same
    ones ``DozerDbMemoryAdapter.write_event`` accepts, so the
    ``keep``/``merge`` branch can splat the candidate into the adapter
    call verbatim.
    """

    subject: str
    predicate: str
    object: str
    provenance: str
    confidence: float
    source_citation: str | None = None
    pii_tier: str = "Public"
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_write_kwargs(self) -> dict[str, Any]:
        """Kwargs for ``adapter.write_event``."""
        return {
            "provenance": self.provenance,
            "confidence": self.confidence,
            "source_citation": self.source_citation,
            "pii_tier": self.pii_tier,
            "attributes": dict(self.attributes),
        }

    def triple_text(self) -> str:
        """Normalized ``f"{subject} {predicate} {object}"`` used for
        deterministic reflection. Lowercase, whitespace-collapsed."""
        return " ".join(
            part.strip().lower()
            for part in (self.subject, self.predicate, self.object)
        )


@dataclass(frozen=True, slots=True)
class CurationResult:
    """Cycle outcome. ``final_event`` is ``None`` iff ``action == "discard"``."""

    action: CurationAction
    reason: str
    final_event: CurationCandidate | None


# ── Cycle steps ─────────────────────────────────────────────────────────────


async def generate_candidate(
    *,
    subject: str,
    predicate: str,
    object: str,
    provenance: str,
    confidence: float,
    source_citation: str | None = None,
    pii_tier: str = "Public",
    attributes: dict[str, Any] | None = None,
) -> CurationCandidate:
    """Construct a :class:`CurationCandidate`.

    Async for symmetry with the rest of the cycle (future escalations may
    do I/O here — e.g., embed the triple to short-circuit reflection).
    """
    return CurationCandidate(
        subject=subject,
        predicate=predicate,
        object=object,
        provenance=provenance,
        confidence=confidence,
        source_citation=source_citation,
        pii_tier=pii_tier,
        attributes=dict(attributes or {}),
    )


def _hit_triple_text(hit: MemoryHit) -> str:
    """Best-effort triple text from a ``MemoryHit`` payload.

    ``search_semantic`` hits carry the full stored payload, which per
    ADR-021 D1 includes ``subject`` / ``predicate`` / ``object``.
    Missing fields collapse to empty strings so the string-overlap
    check simply won't match — that's the safe direction (a malformed
    hit never causes a false-positive ``discard``).
    """
    payload = hit.payload or {}
    return " ".join(
        str(payload.get(k, "")).strip().lower()
        for k in ("subject", "predicate", "object")
    )


async def reflect_on_candidate(
    candidate: CurationCandidate,
    existing_related_memories: Iterable[MemoryHit],
) -> str:
    """Deterministic string-overlap reflection.

    Returns:
        - ``"No related memory found — novel information."`` if
          ``existing_related_memories`` is empty.
        - ``"Exact duplicate of existing memory."`` if any hit's
          normalized triple text equals the candidate's.
        - ``"Related but distinct — may refine existing memory."``
          otherwise.

    The strings are keyed on substrings that :func:`curate` inspects
    (``"duplicate"``, ``"refine"``); do not rewrite them without
    updating :func:`curate`.
    """
    hits = list(existing_related_memories)
    if not hits:
        return "No related memory found — novel information."
    candidate_text = candidate.triple_text()
    if any(_hit_triple_text(h) == candidate_text for h in hits):
        return "Exact duplicate of existing memory."
    return "Related but distinct — may refine existing memory."


async def curate(
    candidate: CurationCandidate,
    existing_related_memories: Iterable[MemoryHit],
) -> CurationResult:
    """Turn a reflection into a :class:`CurationResult`.

    Mirrors the plan §5.5.1 sketch: substring-keyed dispatch on the
    reflection string. Keeps LLM/embedding escalations drop-in
    (they just return a different string).
    """
    reflection = await reflect_on_candidate(candidate, existing_related_memories)
    lowered = reflection.lower()
    if "duplicate" in lowered:
        return CurationResult(action="discard", reason=reflection, final_event=None)
    if "refine" in lowered:
        return CurationResult(action="merge", reason=reflection, final_event=candidate)
    return CurationResult(action="keep", reason=reflection, final_event=candidate)


# ── Orchestrator ────────────────────────────────────────────────────────────


async def curated_write(
    adapter: MemoryPort,
    *,
    subject: str,
    predicate: str,
    object: str,
    provenance: str,
    confidence: float,
    source_citation: str | None = None,
    pii_tier: str = "Public",
    attributes: dict[str, Any] | None = None,
    top_k: int = 5,
    corpus: str | None = None,
) -> CurationResult:
    """Full ACE cycle over a ``MemoryPort`` adapter.

    1. Generate the candidate.
    2. Look up related memories via ``adapter.search_semantic``
       (per Stage 5.5 scope decision B1). The query text is the
       candidate's normalized triple text.
    3. Curate → decide ``keep`` / ``merge`` / ``discard``.
    4. On ``keep`` / ``merge``, call ``adapter.write_event`` with the
       full candidate. On ``discard``, return without touching the
       adapter's write path.

    The zero-trust floor
    (``ports.memory.validate_zero_trust_write``) runs inside
    ``adapter.write_event``; this function must NOT wrap or swallow
    the resulting ``ValueError`` (ADR-023 D3).

    Returns:
        :class:`CurationResult` — same object on both success and
        discard. On ``keep`` / ``merge``, the persistence side effect
        has already happened. The returned ``final_event`` is the
        exact triple that was persisted.
    """
    candidate = await generate_candidate(
        subject=subject,
        predicate=predicate,
        object=object,
        provenance=provenance,
        confidence=confidence,
        source_citation=source_citation,
        pii_tier=pii_tier,
        attributes=attributes,
    )

    related = await adapter.search_semantic(
        candidate.triple_text(),
        corpus=corpus,
        limit=top_k,
    )

    result = await curate(candidate, related)

    if result.action == "discard" or result.final_event is None:
        return result

    # Do not swallow ValueError from the port-level zero-trust guard.
    await adapter.write_event(
        result.final_event.subject,
        result.final_event.predicate,
        result.final_event.object,
        **result.final_event.to_write_kwargs(),
    )
    return result
