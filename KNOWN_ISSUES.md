# Forge-OH — KNOWN_ISSUES

Open, unresolved issues that do not block current-stage progress. Each entry
names the blocker scope, the affected stage/plugin/port, and the plan for
resolution. When resolved, move the entry into DEBUG_LOG.md as a closed
diagnosis (with fix) and delete from here.

Timestamp format: `YYYY-MM-DD HH:MM EDT`.

---

## 2026-08-05 — pnpm workspace CI check fails on every PR (Node 20 + workspace config)

- **Blocks:** none. `mergeable: true` on all merged PRs (#5, #6, #7, closeout).
- **Symptom:** GitHub Actions `pnpm store path --silent` step exits non-zero with `packages field missing or empty`. Every push to `main` shows 2 red checks including check runs against `main` itself.
- **Root cause:** pnpm v11 + Node 20 deprecation interaction with the workspace configuration. Not code-related; the failure is in the CI action's pre-flight step, before any repo command runs.
- **Attempted fixes:** none. Discovered during PR #5-#7 merges.
- **Next investigation:** pin pnpm setup-action version, or set explicit `packages` field in `pnpm-workspace.yaml` if one exists, or migrate the CI check to a different step order that survives the pnpm store bootstrap.
- **Related DEBUG_LOG search terms:** `pnpm store path`, `packages field missing`, `pnpm-lock`, `CI red`.

---

## 2026-08-05 — c01 context-budget-skip ceiling at `max_model_len=32768` (INFORMATIONAL)

- **Blocks:** none. Informational ceiling documenting an honest limit of c01's context window.
- **Symptom:** 35/500 tasks (7.0%) in F.3 full-500 skipped by harness with `ERROR: context-budget-skip: prompt_tokens=N leaves only Xt room (< floor 512)`. All skipped tasks had oracle-file `prompt_tokens > 32k` (matplotlib, sympy, xarray dominant repos). Harness correctly counts these against pass@1 as unresolved-with-error (conservative). Raw pass@1 = 0.266 / attempted-only pass@1 = 0.286 — the 2pt spread reflects the ceiling.
- **Smoke-30 v2 skip rate:** 4/30 tasks (13.3%) skipped in `20260805_2106_run` — **intentionally over-sampled vs the 7.0% full-500 base rate.** The smoke's 30-task budget quantizes small proportions harshly; sampling proportionally would have yielded 2 skips (6.7%), but 4 was chosen to reliably exercise the context-budget-skip code path on every regression run. This is a smoke-design property, not a signal that skip rate is rising. The skipped tasks in smoke-30 v2 are: `django-15629`, `matplotlib-26208`, `sphinx-7590`, `sympy-14248` — all confirmed skips in the full-500 ground truth.
- **Root cause:** c01 (`c01_coder_vllm_qwen36_27b_int4`) launched with `--max-model-len 32768`. Oracle-retrieval loads full ground-truth file contents; matplotlib `axes/_axes.py`, sympy multi-file oracle sets, xarray large modules exceed 32k tokens at 4k output reserve. Model itself (Qwen3.6-27B) supports 128k context natively.
- **Attempted fixes:** none — this is an informational entry, not a bug. F.3 was deliberately kept at 32k `max_model_len` per launcher config.
- **Next investigation:** if Stage 2+ requires raising `max_model_len`, factor in VRAM budget (F.3 already saturated at 99.98% / 32,599 MiB peak). Options: (a) raise `max_model_len` to 65536 or 131072 with `kv-cache-dtype=fp8` retention and reduced `max-num-seqs`, (b) implement oracle-file compression (modified-regions-plus-context) in `oracle_prompt.py`, (c) accept as honest capability ceiling. Path B (Stage 1H.5 agent loop with iterative test-run-fix) may be higher-leverage than raising context alone.
- **Related DEBUG_LOG search terms:** `context-budget-skip`, `max-model-len`, `oracle_prompt`, `prompt_tokens exceeds`, `KV cache VRAM`, `smoke-30`, `smoke skip rate`.
