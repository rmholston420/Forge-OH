# Forge-OH — Session Handoff

## Current stage/plugin/port
**Stage 6.4c step 1e** — P1 Restart-from-here · BFF sha-capture scan fix.

## Completed this session
1. Diagnosed via live Colossus probe: `events/search?limit=20` returns a 13-event initial page with user MessageEvent at INDEX 3 (not 0).  Step 1d's `limit=1` never captured sha in reality.
2. Fixed both capture points in `bff/routers/runs.py`:
   - create_run §3b — scan `limit=20` TIMESTAMP-asc for first user MessageEvent.
   - send_run_message §3b — scan `limit=20` CREATED_AT_DESC for first user MessageEvent.
3. Rewrote `test_assistant_first_event_skips_record` → `test_no_user_message_in_page_skips_record` (semantic).
4. Added 3 new regression tests covering: user at later index, first-user-wins, DESC-interleaved status.
5. Fixed `scripts/stage-6.4c-verify.sh` envelope key (`items` → `data`).
6. Verify script bash syntax check green; both Python files parse.
7. Committed + pushed as `Stage 6.4c step 1e`.

## Remaining before DoD
- Run `.oh-venv/bin/pytest bff/tests/test_runs_sha_capture.py -x` on Colossus (expected: 15 passed, up from 12).
- Rerun `bash scripts/stage-6.4c-verify.sh` on Colossus (Ollama must be up with a `qwen3-coder` tag).  Expected: PASSED with all four checks green.

## Open questions
None.

## Exact next action
On Colossus:
```bash
cd ~/dev/forge-oh && git pull --ff-only
.oh-venv/bin/pytest bff/tests/test_runs_sha_capture.py -x -q
# then restart BFF so the new §3b code is live:
bash scripts/forge-restart.sh --bff-only
sleep 3
bash scripts/stage-6.4c-verify.sh
```
