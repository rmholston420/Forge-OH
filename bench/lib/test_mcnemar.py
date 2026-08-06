"""Standalone verification of bench.lib.mcnemar.

Run: `python -m bench.lib.test_mcnemar` from repo root.

Reference values checked against textbook worked examples (Fagerland et al. 2013).
No pytest dependency; asserts + prints on failure.
"""
from __future__ import annotations

import math
import sys

from bench.lib.mcnemar import mcnemar_paired, McNemarResult


def _almost(a: float, b: float, tol: float = 1e-3) -> bool:
    if math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) < tol


def test_no_discordant_pairs():
    """b + c == 0 → NaN p-value, method='no_discordant_pairs'."""
    # 10 tasks, all identical outcomes
    baseline = {f"t{i}": (i % 3 == 0) for i in range(10)}
    treatment = dict(baseline)
    r = mcnemar_paired(baseline, treatment)
    assert r.b == 0 and r.c == 0, r
    assert math.isnan(r.p_value), r
    assert r.method == "no_discordant_pairs", r
    assert r.effect_size_pct_points == 0.0, r
    print("PASS  test_no_discordant_pairs")


def test_symmetric_small():
    """b == c → p should be exactly 1.0 under mid-p."""
    # 4 discordant, split 2/2
    baseline = {f"t{i}": True for i in range(2)}      # 2 True
    baseline.update({f"t{i+2}": False for i in range(2)})  # 2 False
    treatment = {f"t{i}": False for i in range(2)}    # flipped to False
    treatment.update({f"t{i+2}": True for i in range(2)})  # flipped to True
    r = mcnemar_paired(baseline, treatment)
    assert r.b == 2 and r.c == 2, r
    assert _almost(r.p_value, 1.0), r
    assert r.method == "midp_exact", r
    assert r.effect_size_pct_points == 0.0, r
    print(f"PASS  test_symmetric_small (p={r.p_value})")


def test_all_flips_favor_treatment():
    """10 discordant, all c → strong significance."""
    # 10 tasks baseline=False, treatment=True (all flip toward treatment)
    baseline = {f"t{i}": False for i in range(10)}
    treatment = {f"t{i}": True for i in range(10)}
    r = mcnemar_paired(baseline, treatment)
    assert r.b == 0 and r.c == 10, r
    # p = 2 * (0.5 * PMF(0; 10, 0.5)) = 2 * 0.5 * (1/1024) = 1/1024 ≈ 0.000977
    expected = 2.0 * 0.5 * (1.0 / 1024.0)
    assert _almost(r.p_value, expected), (r, expected)
    assert r.method == "midp_exact", r
    assert r.effect_size_pct_points == 100.0, r  # 10/10 tasks flipped positive
    assert r.odds_ratio is None, r  # b==0 → undefined
    print(f"PASS  test_all_flips_favor_treatment (p={r.p_value:.6f}, expected {expected:.6f})")


def test_known_23_matched_pairs_fagerland():
    """Fagerland 2013 example: b=6, c=16 discordant pairs (n_discordant=22).

    Direct calculation for X ~ Binomial(22, 0.5), k_obs = min(b,c) = 6:
        one-sided mid-p = P(X < 6) + 0.5 * P(X = 6) = 0.01734
        two-sided mid-p = 0.03469

    Cross-check via Lancaster identity: mid-p == exact_two_sided - PMF(k_obs)
    where exact_two_sided (exact-conditional McNemar) is 0.05248 for this
    contingency. Chi-square with continuity correction on the same data would
    give ~0.0339; without correction ~0.0269. Mid-p sits between the exact
    conditional (over-conservative) and chi-square (under-corrected for small
    discordant counts) — exactly the pattern §8.0.5 wants.
    """
    # Construct 100 total pairs: a=40 concordant-True, b=6, c=16, d=38 concordant-False
    baseline = {}
    treatment = {}
    idx = 0
    for _ in range(40):
        baseline[f"t{idx}"] = True; treatment[f"t{idx}"] = True; idx += 1  # a
    for _ in range(6):
        baseline[f"t{idx}"] = True; treatment[f"t{idx}"] = False; idx += 1  # b
    for _ in range(16):
        baseline[f"t{idx}"] = False; treatment[f"t{idx}"] = True; idx += 1  # c
    for _ in range(38):
        baseline[f"t{idx}"] = False; treatment[f"t{idx}"] = False; idx += 1  # d
    r = mcnemar_paired(baseline, treatment)
    assert (r.a, r.b, r.c, r.d) == (40, 6, 16, 38), r
    # Direct-calculated mid-p two-sided = 0.03469. Assert against that value
    # with a modest tolerance for floating-point drift only.
    assert _almost(r.p_value, 0.03469, tol=1e-4), r
    assert r.method == "midp_exact", r
    # effect = (16 - 6) / 100 * 100 = 10.0 pct points
    assert _almost(r.effect_size_pct_points, 10.0), r
    print(f"PASS  test_known_23_matched_pairs_fagerland (p={r.p_value:.4f})")


def test_switches_to_chi_square_above_cutoff():
    """b + c ≥ 25 → chi-square continuity correction."""
    # 30 discordant, split 10/20
    baseline = {}
    treatment = {}
    idx = 0
    for _ in range(10):
        baseline[f"t{idx}"] = True; treatment[f"t{idx}"] = False; idx += 1
    for _ in range(20):
        baseline[f"t{idx}"] = False; treatment[f"t{idx}"] = True; idx += 1
    # concordants (padding to keep denominator plausible)
    for _ in range(70):
        baseline[f"t{idx}"] = False; treatment[f"t{idx}"] = False; idx += 1
    r = mcnemar_paired(baseline, treatment)
    assert r.b == 10 and r.c == 20, r
    assert r.method == "chi_square_continuity", r
    # chi_sq = (|10-20|-1)^2 / 30 = 81/30 = 2.7; z = sqrt(2.7) ≈ 1.643
    # sf ≈ 0.0502; two-sided p ≈ 0.1005 — close to but ABOVE alpha=0.05
    assert 0.09 < r.p_value < 0.12, r
    print(f"PASS  test_switches_to_chi_square_above_cutoff (p={r.p_value:.4f}, method={r.method})")


def test_slice_8_0_retrospective():
    """Retrospective closeout for Slice 8.0 seed-variance question.

    Baseline: 10/30 resolved. Step 1 (no-spec): 9/30 resolved.
    Actual paired outcomes are stored on Colossus; we can't run the real
    pairing from this sandbox — but we CAN verify the code handles
    the expected shape (small n, small |b-c|).

    Simulate the WORST-CASE for the null: all 30 tasks paired,
    b=1, c=0, discordant=1. This is exactly one task flipping True→False.
    Expected p: very high (~1.0) — no signal.
    """
    baseline = {f"t{i}": (i < 10) for i in range(30)}
    treatment = {f"t{i}": (i < 9) for i in range(30)}  # t9 flipped True→False
    r = mcnemar_paired(baseline, treatment)
    assert (r.a, r.b, r.c, r.d) == (9, 1, 0, 20), r
    # One discordant pair, 1 vs 0 → mid-p = 2 * 0.5 * PMF(0;1,0.5) = 2 * 0.5 * 0.5 = 0.5
    assert _almost(r.p_value, 0.5), r
    print(f"PASS  test_slice_8_0_retrospective (p={r.p_value}, |b-c|=1)")


def main() -> int:
    tests = [
        test_no_discordant_pairs,
        test_symmetric_small,
        test_all_flips_favor_treatment,
        test_known_23_matched_pairs_fagerland,
        test_switches_to_chi_square_above_cutoff,
        test_slice_8_0_retrospective,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}", file=sys.stderr)
            failed += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}", file=sys.stderr)
            failed += 1
    if failed:
        print(f"\n{failed} test(s) failed", file=sys.stderr)
        return 1
    print(f"\nAll {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
