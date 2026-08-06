"""Unit tests for MODEL_ROUTER_CATALOG (ADR-012 §3 completion, 2026-08-06).

Covers the compatibility oracle consumed by Stage 6.5.2 model-switch and
by preset validation (Stage 1.5.3 when it lands).
"""

from __future__ import annotations

import pytest

from bff.services.model_router import (
    MODEL_ROUTER_CATALOG,
    RoleCatalog,
    canonical_model_for_role,
    is_model_compatible_with_role,
)


def test_catalog_has_coder_and_planner() -> None:
    assert set(MODEL_ROUTER_CATALOG.keys()) == {"coder", "planner"}


def test_catalog_canonicals_match_adr013_ratification() -> None:
    """ADR-013 ratified coder = qwen3.6-27b-int4-autoround (2026-08-05
    04:55 EDT) and planner = deepseek-r1-distill-32b-awq (2026-08-05
    03:52 EDT). If either canonical drifts, ADR-013 must be amended
    first, then this test updated in the same commit."""
    assert MODEL_ROUTER_CATALOG["coder"].canonical == "qwen3.6-27b-int4-autoround"
    assert MODEL_ROUTER_CATALOG["planner"].canonical == "deepseek-r1-distill-32b-awq"


def test_canonical_is_always_in_compatible_set() -> None:
    for role, catalog in MODEL_ROUTER_CATALOG.items():
        assert catalog.canonical in catalog.compatible, (
            f"role={role!r}: canonical {catalog.canonical!r} not in compatible "
            f"set {sorted(catalog.compatible)!r}"
        )


def test_rolecatalog_post_init_widens_compatible_to_include_canonical() -> None:
    """Constructing RoleCatalog with a canonical outside compatible must
    silently widen compatible, not raise."""
    c = RoleCatalog(canonical="model-a", compatible=frozenset({"model-b"}))
    assert "model-a" in c.compatible
    assert "model-b" in c.compatible


def test_is_model_compatible_happy_paths() -> None:
    assert is_model_compatible_with_role("qwen3.6-27b-int4-autoround", "coder")
    assert is_model_compatible_with_role("qwen3-coder:32k", "coder")
    assert is_model_compatible_with_role("deepseek-r1-distill-32b-awq", "planner")


def test_is_model_compatible_rejects_cross_role() -> None:
    """Planner canonical must NOT be legal for coder role, and vice versa."""
    assert not is_model_compatible_with_role("deepseek-r1-distill-32b-awq", "coder")
    assert not is_model_compatible_with_role("qwen3.6-27b-int4-autoround", "planner")


def test_is_model_compatible_rejects_unknown_role() -> None:
    """Unknown role returns False rather than raising, so HTTP callers
    can convert to 422 without a try/except wrapper."""
    assert not is_model_compatible_with_role("qwen3.6-27b-int4-autoround", "unknown-role")


def test_is_model_compatible_rejects_unknown_model() -> None:
    assert not is_model_compatible_with_role("gpt-9000", "coder")
    assert not is_model_compatible_with_role("", "coder")


def test_canonical_model_for_role_returns_none_for_unknown_role() -> None:
    assert canonical_model_for_role("coder") == "qwen3.6-27b-int4-autoround"
    assert canonical_model_for_role("planner") == "deepseek-r1-distill-32b-awq"
    assert canonical_model_for_role("unknown-role") is None


@pytest.mark.parametrize(
    "role,model,expected",
    [
        ("coder", "qwen3.6-27b-int4-autoround", True),
        ("coder", "qwen3-coder:32k", True),
        ("coder", "deepseek-r1-distill-32b-awq", False),
        ("planner", "deepseek-r1-distill-32b-awq", True),
        ("planner", "qwen3.6-27b-int4-autoround", False),
        ("planner", "qwen3-coder:32k", False),
        ("", "qwen3.6-27b-int4-autoround", False),
        ("coder", "", False),
    ],
)
def test_compatibility_matrix(role: str, model: str, expected: bool) -> None:
    assert is_model_compatible_with_role(model, role) is expected


def test_seed_presets_all_pass_compatibility() -> None:
    """Every model in the seed AgentPreset registry must be compatible
    with its declared role. Guards against seed drift between
    agent_presets.py and MODEL_ROUTER_CATALOG."""
    from bff.routers.agent_presets import _PRESETS

    for preset in _PRESETS.values():
        if preset.role is None:
            # role=None means "let route_by_role decide" — no gate to check.
            continue
        if not preset.model:
            continue
        assert is_model_compatible_with_role(preset.model, preset.role), (
            f"seed preset {preset.id!r} declares model={preset.model!r} "
            f"role={preset.role!r} but that pair is not in MODEL_ROUTER_CATALOG"
        )
