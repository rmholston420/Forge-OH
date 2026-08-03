# DEBUG LOG (append-only)

## 2026-08-02 22:32 EDT — ReactQuery ["runs","presets"] undefined + ZodError agentPresetId
- **Symptom:** Console: `Query data cannot be undefined ... key: ["runs","presets"]`, then `ZodError agentPresetId "expected string >=1 characters"` on run submit.
- **Affected stage/plugin/port:** Stage 3, BFF `bff/routers/agent_presets.py` HTTP contract vs frontend `src/features/runs/api.ts` envelope expectation.
- **Root cause:** BFF returned bare list; frontend `unwrap(result).data` expected `{data:[...]}` envelope. The Zod error is downstream: composer auto-selects `presets[0].id`, but presets never load → `agentPresetId` stays "" → schema min(1) fires.
- **Fix applied:** Wrap `list_presets()` in `{'data': [...]}` — matches every other BFF list endpoint contract.
- **Files changed:** `bff/routers/agent_presets.py`
