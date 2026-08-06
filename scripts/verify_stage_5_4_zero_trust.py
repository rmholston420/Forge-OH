"""Stage 5.4 verification: plan §5.4.3 negative tests against Forge-OH's
existing port-layer zero-trust validators.

The Forge-OH port layer (ports/memory.py::validate_zero_trust_write and
ports/vector.py::validate_zero_trust_payload) enforces the exact rules the
reconciliation plan proposes for MemoryWriteEvent, plus stricter cases
(bool-as-confidence rejected, non-numeric confidence rejected). This script
proves that enforcement under the plan's own DoD wording:

    - empty provenance → rejected
    - out-of-range confidence → rejected
    - rejection fires at the live adapter write path, not just at the
      standalone validator

Exit code 0 iff every assertion passes. Intended to be run in .oh-venv on
Colossus (or any sandbox with the Forge-OH package importable).
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from typing import Callable

from openhands_tools_ext.memory.ports.memory import validate_zero_trust_write
from openhands_tools_ext.memory.ports.vector import validate_zero_trust_payload


def _expect_raises(label: str, fn: Callable[[], object]) -> bool:
    try:
        fn()
    except ValueError as e:
        print(f"PASS: {label} — {e}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: {label} — wrong exception type {type(e).__name__}: {e}")
        return False
    print(f"FAIL: {label} — validator accepted invalid input")
    return False


async def _adapter_write_rejects() -> list[bool]:
    """Confirm rejection at the live DozerDbMemoryAdapter.write_event call site.

    Uses the ported in-memory backends so this runs standalone (no DozerDB
    needed) — the enforcement point is the same code path the live adapter
    exercises against DozerDB.
    """
    from openhands_tools_ext.memory.adapters.dozerdb.adapter import (
        DozerDbMemoryAdapter,
        InMemoryGraphBackend,
        InMemoryTemporalIndex,
        NoOpAmgPolicy,
    )

    adapter = DozerDbMemoryAdapter(
        graph=InMemoryGraphBackend(),
        amg=NoOpAmgPolicy(),
        temporal=InMemoryTemporalIndex(),
    )

    results: list[bool] = []

    # Empty provenance at live adapter call
    try:
        await adapter.write_event(
            "s", "p", "o",
            provenance="", confidence=0.9,
        )
    except ValueError as e:
        print(f"PASS: adapter.write_event rejected empty provenance — {e}")
        results.append(True)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: adapter.write_event wrong exception on empty provenance — {type(e).__name__}: {e}")
        results.append(False)
    else:
        print("FAIL: adapter.write_event accepted empty provenance")
        results.append(False)

    # Out-of-range confidence at live adapter call
    try:
        await adapter.write_event(
            "s", "p", "o",
            provenance="agent-self-report", confidence=1.5,
        )
    except ValueError as e:
        print(f"PASS: adapter.write_event rejected confidence=1.5 — {e}")
        results.append(True)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: adapter.write_event wrong exception on out-of-range confidence — {type(e).__name__}: {e}")
        results.append(False)
    else:
        print("FAIL: adapter.write_event accepted confidence=1.5")
        results.append(False)

    return results


def main() -> int:
    print("=" * 72)
    print("Stage 5.4 verification — plan §5.4.3 negative tests")
    print("Target: existing port-layer validators (ADR-021 Consequences)")
    print("=" * 72)

    checks: list[bool] = []

    # Plan §5.4.3 model-level rejections, applied to validate_zero_trust_write
    checks.append(_expect_raises(
        "validate_zero_trust_write rejects empty provenance",
        lambda: validate_zero_trust_write(provenance="", confidence=0.9),
    ))
    checks.append(_expect_raises(
        "validate_zero_trust_write rejects None provenance",
        lambda: validate_zero_trust_write(provenance=None, confidence=0.9),  # type: ignore[arg-type]
    ))
    checks.append(_expect_raises(
        "validate_zero_trust_write rejects confidence=1.5",
        lambda: validate_zero_trust_write(provenance="agent-self-report", confidence=1.5),
    ))
    checks.append(_expect_raises(
        "validate_zero_trust_write rejects confidence=-0.1",
        lambda: validate_zero_trust_write(provenance="agent-self-report", confidence=-0.1),
    ))
    checks.append(_expect_raises(
        "validate_zero_trust_write rejects bool confidence (ADR-026 stricter-than-plan)",
        lambda: validate_zero_trust_write(provenance="agent-self-report", confidence=True),  # type: ignore[arg-type]
    ))

    # Plan §5.4.3 model-level rejections, applied to validate_zero_trust_payload
    checks.append(_expect_raises(
        "validate_zero_trust_payload rejects missing provenance",
        lambda: validate_zero_trust_payload({"confidence": 0.9}),
    ))
    checks.append(_expect_raises(
        "validate_zero_trust_payload rejects empty provenance",
        lambda: validate_zero_trust_payload({"provenance": "", "confidence": 0.9}),
    ))
    checks.append(_expect_raises(
        "validate_zero_trust_payload rejects confidence=1.5",
        lambda: validate_zero_trust_payload({"provenance": "agent", "confidence": 1.5}),
    ))
    checks.append(_expect_raises(
        "validate_zero_trust_payload rejects missing confidence",
        lambda: validate_zero_trust_payload({"provenance": "agent"}),
    ))

    # Boundary acceptance (validators must NOT reject valid inputs)
    try:
        validate_zero_trust_write(provenance="agent", confidence=0.0)
        validate_zero_trust_write(provenance="agent", confidence=1.0)
        validate_zero_trust_payload({"provenance": "agent", "confidence": 0.0})
        validate_zero_trust_payload({"provenance": "agent", "confidence": 1.0})
        print("PASS: boundary values [0.0, 1.0] accepted by both validators")
        checks.append(True)
    except Exception:  # noqa: BLE001
        print("FAIL: boundary value rejected —")
        traceback.print_exc()
        checks.append(False)

    # Plan §5.4.3 live-adapter check
    checks.extend(asyncio.run(_adapter_write_rejects()))

    passed = sum(1 for c in checks if c)
    total = len(checks)
    print("-" * 72)
    print(f"Stage 5.4 verification: {passed}/{total} checks passed")
    if passed == total:
        print("STAGE 5.4 DoD: SATISFIED by existing port-layer validators.")
        return 0
    print("STAGE 5.4 DoD: NOT SATISFIED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
