"""Paired mid-p McNemar test for pass@1 A/B comparisons.

Slice 8.0.5 (measurement hardening). See docs/reconciliation-plan-stage-8.md §8.0.5.

Why McNemar (paired)?
---------------------
A bench pair (baseline, treatment) shares seed, task order, prompts, and only differs
in the config under test. Every task therefore appears in BOTH runs, producing a
paired binary outcome (resolved True/False). McNemar's test targets exactly this
2×2 contingency:

                   treatment=True   treatment=False
    baseline=True        a               b
    baseline=False       c               d

The test statistic depends only on the DISCORDANT pairs (b + c). The relevant
question is: "of the tasks whose outcome changed, did significantly more flip in
one direction than the other?"

Why mid-p correction?
---------------------
For small-to-medium n (b + c ≤ 25), the exact binomial two-tailed p-value is
conservative — the discrete probability mass at the observed threshold pushes p
too high, hurting power. The mid-p correction subtracts HALF the point mass at
the observed count, which is the standard remedy in the code-eval literature
(and matches the recommendation in Fagerland, Lydersen, Laake 2013). For
b + c ≥ 25 we fall back to the continuity-corrected chi-square, matching common
usage. See DoD §8.0.5 item 1 (Council-Synthesis line 117 + ADR-029 §D5).

References:
- Council-Synthesis line 105: "pass@1 with McNemar's test"
- Fagerland MW, Lydersen S, Laake P. 2013. "The McNemar test for binary
  matched-pairs data: mid-p and asymptotic are better than exact conditional."
  BMC Med Res Methodol. 13:91.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


# Discordant-pair cutoff: below this, use mid-p exact; at/above, use chi-square
# with continuity correction. Standard cutoff in the McNemar literature.
_EXACT_CUTOFF = 25


@dataclass(frozen=True)
class McNemarResult:
    """Outcome of a paired McNemar test on pass@1 outcomes.

    Fields:
        n_paired: number of tasks present in both runs
        a: both resolved (concordant, positive)
        b: baseline resolved, treatment NOT (discordant against treatment)
        c: treatment resolved, baseline NOT (discordant for treatment)
        d: both unresolved (concordant, negative)
        p_value: two-tailed p-value; NaN when b+c == 0 (nothing to test)
        method: "midp_exact" or "chi_square_continuity"
        odds_ratio: c/b (ratio of favorable to unfavorable flips); None when
                    either b or c is 0 (undefined / infinite)
        effect_size_pct_points: (c - b) / n_paired * 100 — absolute pass@1
                                delta attributable to the treatment
        interpretation: short human-readable string
    """
    n_paired: int
    a: int
    b: int
    c: int
    d: int
    p_value: float
    method: str
    odds_ratio: float | None
    effect_size_pct_points: float
    interpretation: str

    def to_dict(self) -> dict:
        return asdict(self)


def _binomial_pmf(k: int, n: int, p: float) -> float:
    """Standalone binomial PMF (no scipy dep)."""
    if k < 0 or k > n:
        return 0.0
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def _midp_two_sided(b: int, c: int) -> float:
    """Two-sided mid-p exact test.

    Under H0 (no treatment effect), each discordant pair is independently
    equally likely to flip either way, so b ~ Binomial(b+c, 0.5). The mid-p
    correction takes P(X < k_obs) + 0.5 * P(X == k_obs), then doubles for
    two-sided.
    """
    n = b + c
    if n == 0:
        return float("nan")
    k_obs = min(b, c)
    # Two-sided: sum probability of outcomes at least as extreme as observed
    # in EITHER direction. Because binomial(n, 0.5) is symmetric, this equals
    # 2 * one-sided lower tail with mid-p correction at the observed count.
    lower_tail = sum(_binomial_pmf(k, n, 0.5) for k in range(k_obs))
    at_obs = _binomial_pmf(k_obs, n, 0.5)
    p_one_sided_midp = lower_tail + 0.5 * at_obs
    p_two_sided = min(1.0, 2.0 * p_one_sided_midp)
    return p_two_sided


def _erf(x: float) -> float:
    """math.erf, wrapped for readability."""
    return math.erf(x)


def _chi_sq_p_1df_continuity(b: int, c: int) -> float:
    """Two-sided p-value from continuity-corrected chi-square, 1 df.

    Statistic: (|b - c| - 1)^2 / (b + c). Under H0, ~ chi-square(1) which is
    (Z^2) for Z ~ Normal(0,1). Two-sided p = 2 * (1 - Phi(sqrt(chi_sq))).
    """
    n = b + c
    if n == 0:
        return float("nan")
    numer = max(0, abs(b - c) - 1) ** 2
    chi_sq = numer / n
    z = math.sqrt(chi_sq)
    # Survival function of standard normal
    sf = 0.5 * (1 - _erf(z / math.sqrt(2.0)))
    return min(1.0, 2.0 * sf)


def _load_pass_map(run_dir: Path) -> dict[str, bool]:
    """Read a bench run dir and return {instance_id: resolved_bool}.

    Skips tasks with resolved=None (unknown/stubbed, dry-plan, etc.). Also
    skips manifest.json, summary.json, progress.json, pair_comparison.json.
    """
    result: dict[str, bool] = {}
    for p in sorted(run_dir.glob("*.json")):
        if p.name in ("manifest.json", "summary.json", "progress.json",
                      "pair_comparison.json"):
            continue
        if p.name.startswith("manifest_") or p.name.startswith("pair_comparison_"):
            continue
        try:
            rec = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        inst = rec.get("instance_id")
        resolved = rec.get("resolved")
        if inst and isinstance(resolved, bool):
            result[inst] = resolved
    return result


def _interpret(p: float, b: int, c: int, alpha: float = 0.05) -> str:
    if math.isnan(p):
        return "no discordant pairs; test not applicable"
    direction = "treatment better" if c > b else ("baseline better" if b > c else "identical flips")
    if p < alpha:
        return f"significant at alpha={alpha}: {direction}"
    return f"NOT significant at alpha={alpha} (p={p:.4f}); {direction}"


def mcnemar_paired(
    baseline: dict[str, bool] | Iterable[tuple[str, bool]],
    treatment: dict[str, bool] | Iterable[tuple[str, bool]],
) -> McNemarResult:
    """Run the paired McNemar test on two {instance_id: resolved} dicts.

    Tasks present in only one run are silently dropped from the pairing set.
    Ordering does not matter — the test is symmetric-labeled up to which side
    is called "baseline" vs "treatment" (only sign of effect_size_pct_points
    changes).
    """
    b_map = dict(baseline)
    t_map = dict(treatment)
    common = sorted(set(b_map) & set(t_map))
    a = b = c = d = 0
    for inst in common:
        bv, tv = b_map[inst], t_map[inst]
        if bv and tv:
            a += 1
        elif bv and not tv:
            b += 1
        elif not bv and tv:
            c += 1
        else:
            d += 1
    n = a + b + c + d
    discordant = b + c

    if discordant == 0:
        p = float("nan")
        method = "no_discordant_pairs"
    elif discordant < _EXACT_CUTOFF:
        p = _midp_two_sided(b, c)
        method = "midp_exact"
    else:
        p = _chi_sq_p_1df_continuity(b, c)
        method = "chi_square_continuity"

    odds_ratio: float | None
    if b == 0 or c == 0:
        odds_ratio = None
    else:
        odds_ratio = round(c / b, 4)

    effect = round(((c - b) / n) * 100.0, 3) if n else 0.0
    interp = _interpret(p, b, c)

    return McNemarResult(
        n_paired=n, a=a, b=b, c=c, d=d,
        p_value=(round(p, 6) if not math.isnan(p) else float("nan")),
        method=method,
        odds_ratio=odds_ratio,
        effect_size_pct_points=effect,
        interpretation=interp,
    )


def pair_runs(baseline_dir: Path, treatment_dir: Path) -> dict:
    """Compare two bench run dirs and return a JSON-serializable comparison.

    The returned dict has:
        baseline: {run_dir, task_count, resolved_count, pass_at_1}
        treatment: same shape
        mcnemar: McNemarResult.to_dict()
        tasks_baseline_only: [instance_ids] (excluded from pairing)
        tasks_treatment_only: [instance_ids] (excluded from pairing)
    """
    b_map = _load_pass_map(baseline_dir)
    t_map = _load_pass_map(treatment_dir)
    common = set(b_map) & set(t_map)
    result = mcnemar_paired(b_map, t_map)
    return {
        "baseline": {
            "run_dir": str(baseline_dir),
            "task_count": len(b_map),
            "resolved_count": sum(1 for v in b_map.values() if v),
            "pass_at_1": round(sum(1 for v in b_map.values() if v) / len(b_map), 4) if b_map else 0.0,
        },
        "treatment": {
            "run_dir": str(treatment_dir),
            "task_count": len(t_map),
            "resolved_count": sum(1 for v in t_map.values() if v),
            "pass_at_1": round(sum(1 for v in t_map.values() if v) / len(t_map), 4) if t_map else 0.0,
        },
        "mcnemar": result.to_dict(),
        "tasks_baseline_only": sorted(set(b_map) - common),
        "tasks_treatment_only": sorted(set(t_map) - common),
    }


if __name__ == "__main__":
    # Smoke: `python -m bench.lib.mcnemar <baseline_run> <treatment_run>`
    import sys
    if len(sys.argv) != 3:
        print("usage: python -m bench.lib.mcnemar <baseline_run_dir> <treatment_run_dir>", file=sys.stderr)
        sys.exit(2)
    baseline = Path(sys.argv[1]).expanduser().resolve()
    treatment = Path(sys.argv[2]).expanduser().resolve()
    if not baseline.is_dir() or not treatment.is_dir():
        print(f"one or both dirs missing: {baseline}, {treatment}", file=sys.stderr)
        sys.exit(2)
    result = pair_runs(baseline, treatment)
    print(json.dumps(result, indent=2))
