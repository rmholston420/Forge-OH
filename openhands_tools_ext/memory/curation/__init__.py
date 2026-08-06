"""ACE-style memory curation (Stage 5.5).

Generate → reflect → curate cycle for memory writes. See:

- `Forge-OH-reconciliation-plan-v1-stage-5.md` §5.5
- ADR-023 (curation cycle: triple-shaped, deterministic first pass,
  library-only until a caller exists)

Public surface:

- :class:`CurationCandidate` — the triple + provenance/confidence + attrs
  that flows through the cycle. Triple-shaped per ADR-021 / ADR-023 D1
  (NOT the plan's free-string sketch).
- :class:`CurationResult` — the outcome (``keep`` | ``merge`` | ``discard``)
  and the ``final_event`` to persist (if any).
- :func:`generate_candidate` — pure constructor for the cycle's input.
- :func:`reflect_on_candidate` — deterministic string-overlap reflection
  over ``f"{subject} {predicate} {object}"``. Returns a natural-language
  reflection string keyed on the substrings the curator inspects
  ("duplicate", "refine", "novel").
- :func:`curate` — turn a reflection into a :class:`CurationResult`.
- :func:`curated_write` — orchestrator: search_semantic → curate →
  adapter.write_event (only on ``keep`` / ``merge``).

The zero-trust floor (``validate_zero_trust_write``) is enforced by the
underlying adapter's ``write_event``; curation never swallows a
``ValueError`` from it (ADR-023 D3).
"""

from openhands_tools_ext.memory.curation.ace_cycle import (
    CurationCandidate,
    CurationResult,
    curate,
    curated_write,
    generate_candidate,
    reflect_on_candidate,
)

__all__ = [
    "CurationCandidate",
    "CurationResult",
    "curate",
    "curated_write",
    "generate_candidate",
    "reflect_on_candidate",
]
