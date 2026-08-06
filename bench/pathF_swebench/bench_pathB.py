#!/usr/bin/env python3
"""F.3 Path B — SWE-bench Verified 30-task pass@1 through the Forge-OH stack.

Companion to bench_pathF_swebench.py (Path A, direct-to-vLLM). Path B drives
each task through the Forge-OH BFF → agent-server → same c01 vLLM backend, so
we can attribute score/token deltas to the Stage 3-6 middleware:

  * Stage 3 approval gates + risk classifier
  * Stage 4 RepoGraph / Serena LSP
  * Stage 5 four-tier memory (consult_memory)
  * Stage 6.1 SearXNG web-research
  * Stage 6.3 idempotency ledger
  * Stage 6.6 skills auto-loader
  * Stage 6.7 code_execute + progressive disclosure

Bench methodology (mirrors Path A):
  - Same 30-task calibrated smoke set (SMOKE_TASK_IDS in bench_pathF_swebench).
  - Same oracle-retrieval prompt (ground-truth files in context).
  - Same apply_and_test docker path.
  - One JSON per task, directory-per-run with UTC timestamp.
  - <think>...</think> stripped before dump.
  - Wall time + prompt/completion tokens + tool_call breakdown captured.

Isolation:
  - Fresh agent-server workspace per task (POST /api/workspaces on the BFF).
    Cleaned up on task end via DELETE /api/workspaces/{id}. Failure to clean
    up is logged, not fatal — a stray workspace is discoverable and reapable.
  - Fresh run per task (POST /api/runs). Deleted on task end via
    DELETE /api/runs/{id} which cascade-reaps the git worktree.
  - The SWE-bench docker sandbox already isolates code execution — Path B
    only shares the vLLM backend + the middleware stack with concurrent runs.

Budgets (verified in ADR-013 amendment #2 discussion 2026-08-06 12:xx EDT):
  - Wall cap per task: 3600s (1h). Path A c01 tasks average ~3-6s; agent
    trajectories with tool loops can take much longer, but 1h catches
    runaway loops without cutting off legitimate multi-turn work.
  - Tool-call cap: 30. Oracle retrieval means files are already in the
    prompt; more than 30 tool calls is almost certainly thrashing.

Usage
-----
    # Dry-run (no docker apply_and_test):
    python -m bench.pathF_swebench.bench_pathB \\
        --smoke --dry-plan-only

    # Full smoke set through the Forge-OH stack:
    python -m bench.pathF_swebench.bench_pathB \\
        --smoke

    # Single task for shakeout:
    python -m bench.pathF_swebench.bench_pathB \\
        --tasks django__django-11099

    # Compare against a Path A run:
    python -m bench.pathF_swebench.compare_tokens \\
        --path-a ~/.forge-oh/bench_pathF_swebench/<pathA_run_dir> \\
        --path-b ~/.forge-oh/bench_pathB_swebench/<pathB_run_dir>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urlerr, request as urlreq

from bench.pathF_swebench.apply_and_test import normalize_patch
from bench.pathF_swebench.load_verified import dump_task_summary, load_tasks
from bench.pathF_swebench.oracle_prompt import (
    build_prompt,
    files_touched_by_patch,
    read_files_at_commit,
)
from bench.pathF_swebench.bench_pathF_swebench import (
    SMOKE_TASK_IDS,
    _repo_checkout_path,
    _fmt_dur,
    _empty_gpu_stats,
)

# NVML sampler for the wall-clock GPU window (same shape as Path A).
try:
    from bench._common.nvml_sampler import GpuSampler  # type: ignore
    _GPU_SAMPLER_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    _GPU_SAMPLER_AVAILABLE = False
    print(f"[F.3 Path B] warn: NVML sampler unavailable: {_e}", flush=True)


REPO = Path.home() / "dev" / "forge-oh"
BENCH_ROOT = Path.home() / ".forge-oh" / "bench_pathB_swebench"

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

# ---------- Path B constants ----------

BFF_URL = os.getenv("PATHB_BFF_URL", "http://127.0.0.1:8081")
GPU_SAMPLE_INTERVAL_S = 0.5

# Per-task budgets. Wall cap catches runaway agents; tool cap catches
# thrashing on oracle-retrieval where files are already in the prompt.
WALL_CAP_S = int(os.getenv("PATHB_WALL_CAP_S", "3600"))
TOOL_CALL_CAP = int(os.getenv("PATHB_TOOL_CALL_CAP", "30"))
POLL_INTERVAL_S = float(os.getenv("PATHB_POLL_INTERVAL_S", "3.0"))

# Terminal states from _STATUS_MAP in bff/routers/runs.py.
TERMINAL_STATES = {"succeeded", "failed", "stopped"}

# ---------- BFF HTTP helpers ----------


def http_json(method: str, path: str, body: dict | None = None, timeout: int = 60) -> tuple[dict, int, float]:
    """Call the BFF. Returns (json_body, status_code, wall_seconds).

    On network error returns ({"error": "..."}, 0, wall). On non-2xx keeps the
    parsed JSON body when available so callers can inspect error detail.
    """
    url = f"{BFF_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urlreq.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    t0 = time.time()
    try:
        with urlreq.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return (json.loads(raw) if raw else {}), r.status, time.time() - t0
    except urlerr.HTTPError as e:
        try:
            body_json = json.loads(e.read().decode(errors="ignore"))
        except Exception:
            body_json = {"error": f"HTTPError {e.code}"}
        return body_json, e.code, time.time() - t0
    except urlerr.URLError as e:
        return {"error": f"URLError: {e.reason}"}, 0, time.time() - t0


# ---------- Workspace lifecycle ----------


def create_workspace(instance_id: str, repo_root: Path, base_commit: str) -> tuple[str, str] | None:
    """Create a fresh agent-server workspace pointing at repo_root.

    The bench harness assumes the caller has already checked out the repo
    at base_commit under `repo_root` — Path A's `_repo_checkout_path` does
    this and we reuse it. Returns (workspace_id, working_dir_path) on
    success, None on failure.
    """
    body = {
        "name": f"pathB-{instance_id}-{datetime.now().strftime('%H%M%S')}",
        "path": str(repo_root),
        "kind": "local",
    }
    resp, code, _ = http_json("POST", "/api/workspaces", body=body, timeout=60)
    if code >= 400:
        print(f"  [ws-create] FAILED ({code}): {json.dumps(resp)[:400]}", flush=True)
        return None
    ws = resp if isinstance(resp, dict) and "id" in resp else (resp.get("data") or {})
    ws_id = ws.get("id")
    ws_path = ws.get("path") or str(repo_root)
    if not ws_id:
        print(f"  [ws-create] response missing id: {json.dumps(resp)[:400]}", flush=True)
        return None
    return ws_id, ws_path


def delete_workspace(ws_id: str) -> None:
    _resp, code, _ = http_json("DELETE", f"/api/workspaces/{ws_id}", timeout=30)
    if code >= 400 and code != 404:
        print(f"  [ws-cleanup] warn: DELETE workspace {ws_id} returned {code}", flush=True)


# ---------- Run lifecycle ----------


def create_run(instance_id: str, ws_id: str, prompt: str) -> tuple[str, dict] | None:
    """POST /api/runs. Returns (run_id, initial_summary) on success."""
    body = {
        "title": f"pathB · {instance_id}",
        "agentPresetId": "ap-1",   # default preset (bff/routers/agent_presets.py)
        "workspaceId": ws_id,
        "taskPrompt": prompt,
        "role": "coder",           # F.19.2b: explicit role beats taskComplexity mapping
        "backendId": "vllm-coder", # Stage 2.1.7: pin the vLLM coder backend
        "requireApproval": False,  # Bench must not stall on HITL; use default ConfirmRisky
    }
    resp, code, _ = http_json("POST", "/api/runs", body=body, timeout=120)
    if code >= 400:
        return None, {"error": f"create_run HTTP {code}", "detail": resp}
    run = resp.get("data") if isinstance(resp, dict) else None
    if not run or not run.get("id"):
        if run and run.get("status") == "blocked":
            return None, {"error": "blocked", "detail": run.get("routing", {})}
        return None, {"error": "no run id", "raw": resp}
    return run["id"], run


def poll_until_terminal(run_id: str, wall_cap_s: int, tool_cap: int) -> dict:
    """Poll GET /api/runs/{id} until terminal, wall cap, or tool cap.

    Returns a dict with keys: status, terminal_reason, poll_count, wall_seconds,
    tool_call_count (best-effort — read from metrics on final poll), and the
    final run summary in `summary`.
    """
    t0 = time.time()
    poll_count = 0
    last_summary: dict = {}
    while True:
        poll_count += 1
        elapsed = time.time() - t0

        resp, code, _ = http_json("GET", f"/api/runs/{run_id}", timeout=30)
        if code >= 400:
            # Transient BFF/agent-server hiccup; keep polling until wall cap.
            time.sleep(POLL_INTERVAL_S)
            if elapsed > wall_cap_s:
                return {
                    "status": "unknown",
                    "terminal_reason": "wall_cap_after_get_error",
                    "poll_count": poll_count,
                    "wall_seconds": elapsed,
                    "summary": last_summary,
                }
            continue

        summary = (resp or {}).get("data") or {}
        last_summary = summary
        status = summary.get("status")

        # Best-effort tool-call cap: read metrics; skip if endpoint missing.
        tool_calls = 0
        try:
            m_resp, m_code, _ = http_json("GET", f"/api/runs/{run_id}/metrics", timeout=15)
            if m_code < 400:
                tool_calls = int(((m_resp or {}).get("data") or {}).get("tool_call_count", 0) or 0)
        except Exception:
            pass

        if status in TERMINAL_STATES:
            return {
                "status": status,
                "terminal_reason": "terminal",
                "poll_count": poll_count,
                "wall_seconds": elapsed,
                "tool_call_count": tool_calls,
                "summary": summary,
            }
        if tool_calls >= tool_cap:
            # Force-stop the run so we don't burn more resources.
            http_json("POST", f"/api/runs/{run_id}/stop", timeout=15)
            return {
                "status": "stopped",
                "terminal_reason": "tool_cap",
                "poll_count": poll_count,
                "wall_seconds": elapsed,
                "tool_call_count": tool_calls,
                "summary": summary,
            }
        if elapsed >= wall_cap_s:
            http_json("POST", f"/api/runs/{run_id}/stop", timeout=15)
            return {
                "status": "stopped",
                "terminal_reason": "wall_cap",
                "poll_count": poll_count,
                "wall_seconds": elapsed,
                "tool_call_count": tool_calls,
                "summary": summary,
            }

        time.sleep(POLL_INTERVAL_S)


# ---------- Patch reconstruction ----------


def reconstruct_patch_from_run(run_id: str, oracle_files: list[str]) -> tuple[str, dict]:
    """Reconstruct a git patch from the agent-server run's per-file diffs.

    Strategy: GET /api/runs/{id}/files/{path} for each oracle file returns
    the diff; concatenate. Non-oracle files touched by the agent are also
    included (agent might have edited additional files during exploration).

    Returns (patch_text, diagnostics). diagnostics includes the list of
    files pulled and per-file result codes.
    """
    files_resp, code, _ = http_json("GET", f"/api/runs/{run_id}/files", timeout=30)
    if code >= 400:
        return "", {"error": f"files list HTTP {code}", "detail": files_resp}

    file_summaries = ((files_resp or {}).get("data") or {}).get("files") or []
    if isinstance(files_resp.get("data"), list):
        file_summaries = files_resp["data"]

    touched_paths: list[str] = []
    for entry in file_summaries:
        if not isinstance(entry, dict):
            continue
        p = entry.get("path") or entry.get("file_path")
        if isinstance(p, str) and p:
            touched_paths.append(p)

    # Union: agent-touched ∪ oracle. If agent touched none but oracle files
    # were expected to change, this will surface as an empty patch.
    to_pull = list(dict.fromkeys(touched_paths + oracle_files))

    diagnostics: dict = {
        "agent_touched_paths": touched_paths,
        "oracle_paths": oracle_files,
        "pulled_paths": to_pull,
        "per_file_status": {},
    }

    diff_chunks: list[str] = []
    for path in to_pull:
        # BFF supports both `foo/bar.py` and `%2Ffoo%2Fbar.py` — quote to be safe.
        from urllib.parse import quote
        encoded = quote(path, safe="")
        resp, code, _ = http_json(
            "GET", f"/api/runs/{run_id}/files/{encoded}", timeout=30,
        )
        diagnostics["per_file_status"][path] = code
        if code >= 400:
            continue
        data = (resp or {}).get("data") or {}
        diff = data.get("diff") or data.get("patch") or ""
        if isinstance(diff, str) and diff.strip():
            diff_chunks.append(diff)

    return "\n".join(diff_chunks), diagnostics


# ---------- Per-task driver ----------


def run_task(
    task: dict,
    out_dir: Path,
    dry_plan_only: bool,
    keep_sandbox: bool,
    task_idx: int,
    task_total: int,
) -> dict:
    instance_id = task["instance_id"]
    print(f"[task {task_idx}/{task_total}] {dump_task_summary(task)}", flush=True)

    # 1. Oracle files + repo checkout (same as Path A).
    files = files_touched_by_patch(task["patch"])
    print(f"  oracle files: {files}", flush=True)
    repo_root = _repo_checkout_path(task)
    file_contents = read_files_at_commit(repo_root, task["base_commit"], files)

    # 2. Same oracle prompt as Path A.
    prompt = build_prompt(task, file_contents)

    # 3. Create workspace.
    ws_result = create_workspace(instance_id, repo_root, task["base_commit"])
    if ws_result is None:
        err_record = {
            "instance_id": instance_id,
            "path": "B",
            "phase": "workspace_create",
            "error": "workspace create failed",
            "resolved": False,
        }
        (out_dir / f"{instance_id}.json").write_text(json.dumps(err_record, indent=2))
        return err_record
    ws_id, ws_path = ws_result

    # 4. Create run.
    sampler = GpuSampler(interval_s=GPU_SAMPLE_INTERVAL_S) if _GPU_SAMPLER_AVAILABLE else None
    if sampler is not None:
        sampler.start()
    t0 = time.time()
    print(f"  driving run via BFF (workspace={ws_id})...", flush=True)
    run_result = create_run(instance_id, ws_id, prompt)
    run_id: str | None
    if isinstance(run_result, tuple) and len(run_result) == 2 and run_result[0]:
        run_id, initial_summary = run_result
    else:
        run_id, initial_summary = None, (run_result[1] if isinstance(run_result, tuple) else {})

    if not run_id:
        gpu_stats = sampler.stop().to_dict() if sampler is not None else _empty_gpu_stats()
        delete_workspace(ws_id)
        err_record = {
            "instance_id": instance_id,
            "path": "B",
            "phase": "run_create",
            "error": initial_summary,
            "wall_seconds": round(time.time() - t0, 2),
            "gpu_inference": gpu_stats,
            "resolved": False,
        }
        (out_dir / f"{instance_id}.json").write_text(json.dumps(err_record, indent=2))
        return err_record

    # 5. Poll to terminal or budget cap.
    poll_result = poll_until_terminal(run_id, WALL_CAP_S, TOOL_CALL_CAP)
    inference_gpu = sampler.stop().to_dict() if sampler is not None else _empty_gpu_stats()

    # 6. Metrics (best-effort).
    metrics: dict = {}
    m_resp, m_code, _ = http_json("GET", f"/api/runs/{run_id}/metrics", timeout=30)
    if m_code < 400:
        metrics = (m_resp or {}).get("data") or {}

    # 7. Reconstruct patch from per-file diffs.
    patch_raw, patch_diagnostics = reconstruct_patch_from_run(run_id, files)
    patch_text = normalize_patch(patch_raw) if patch_raw else ""

    # 8. Apply patch + run tests (or dry-plan-only).
    result_payload: dict = {}
    gpu_harness_stats: dict = _empty_gpu_stats()
    if dry_plan_only or not patch_text.strip():
        result_payload = {
            "resolved": None if dry_plan_only else False,
            "phase": (
                "dry-plan-only-skipped-docker"
                if dry_plan_only
                else "empty-patch-skipped-docker"
            ),
        }
    else:
        from bench.pathF_swebench.apply_and_test import apply_patch_and_run_tests
        swebench_root = out_dir.parent.parent / "swebench_runs_pathB"
        swebench_root.mkdir(parents=True, exist_ok=True)
        harness_run_id = f"{out_dir.name}__{instance_id}"
        harness_sampler = GpuSampler(interval_s=GPU_SAMPLE_INTERVAL_S) if _GPU_SAMPLER_AVAILABLE else None
        if harness_sampler is not None:
            harness_sampler.start()
        try:
            test_result = apply_patch_and_run_tests(
                instance_id=instance_id,
                patch=patch_text,
                model_name="c01_pathB_forge_oh",
                artifacts_root=swebench_root,
                run_id=harness_run_id,
                keep_sandbox=keep_sandbox,
            )
        finally:
            gpu_harness_stats = (
                harness_sampler.stop().to_dict() if harness_sampler is not None else _empty_gpu_stats()
            )
        result_payload = {
            "resolved": test_result.resolved,
            "phase": "swebench-harness",
            "harness_return_code": test_result.harness_return_code,
            "harness_run_id": harness_run_id,
            "harness_artifacts_dir": str(swebench_root / harness_run_id),
            "harness_error": test_result.error,
            "harness_stdout_tail": test_result.stdout_tail,
            "harness_stderr_tail": test_result.stderr_tail,
            "harness_report": test_result.report,
        }

    # 9. Cleanup — delete run (reaps worktree) then workspace.
    #    DELETE /api/runs/{id} is idempotent (409/404 handled server-side).
    del_resp, del_code, _ = http_json("DELETE", f"/api/runs/{run_id}", timeout=30)
    if del_code >= 400 and del_code not in (404, 409):
        print(f"  [run-cleanup] warn: DELETE run {run_id} returned {del_code}", flush=True)
    delete_workspace(ws_id)

    task_record = {
        "instance_id": instance_id,
        "path": "B",
        "run_id": run_id,
        "workspace_id": ws_id,
        "workspace_path": ws_path,
        "task_index": task_idx,
        "task_total": task_total,
        "mode": "oracle-retrieval",
        "wall_seconds": round(poll_result["wall_seconds"], 2),
        "poll_count": poll_result["poll_count"],
        "terminal_status": poll_result["status"],
        "terminal_reason": poll_result["terminal_reason"],
        "tool_call_count": poll_result.get("tool_call_count", metrics.get("tool_call_count", 0)),
        "metrics": metrics,
        "oracle_files": files,
        "fail_to_pass": task.get("FAIL_TO_PASS", []) or [],
        "pass_to_pass": task.get("PASS_TO_PASS", []) or [],
        "patch": patch_text,
        "patch_raw": patch_raw,
        "patch_diagnostics": patch_diagnostics,
        "gpu_inference": inference_gpu,
        "gpu_harness": gpu_harness_stats,
        **result_payload,
    }

    out_file = out_dir / f"{instance_id}.json"
    out_file.write_text(json.dumps(task_record, indent=2))

    print(
        f"  [{task_idx}/{task_total}] ok  wall={task_record['wall_seconds']}s "
        f"tools={task_record['tool_call_count']} "
        f"toks={metrics.get('token_count', '?')} "
        f"resolved={result_payload.get('resolved')} "
        f"term={poll_result['terminal_reason']}",
        flush=True,
    )
    return task_record


# ---------- Summary ----------


def _emit_summary(out_dir: Path, records: list[dict], total_wall: float) -> None:
    walls = [r["wall_seconds"] for r in records if isinstance(r.get("wall_seconds"), (int, float)) and r["wall_seconds"] > 0]
    tool_calls = [r.get("tool_call_count", 0) for r in records]
    tokens = [((r.get("metrics") or {}).get("token_count") or 0) for r in records]
    resolved_count = sum(1 for r in records if r.get("resolved") is True)
    failed_count = sum(1 for r in records if r.get("resolved") is False)

    summary = {
        "path": "B",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(out_dir),
        "task_count": len(records),
        "resolved_count": resolved_count,
        "failed_count": failed_count,
        "pass_at_1_raw": (round(resolved_count / len(records), 4) if records else 0.0),
        "wall_total_s": round(total_wall, 2),
        "wall_total_hms": _fmt_dur(total_wall),
        "wall_mean_s": round(statistics.mean(walls), 2) if walls else 0.0,
        "wall_median_s": round(statistics.median(walls), 2) if walls else 0.0,
        "wall_max_s": round(max(walls), 2) if walls else 0.0,
        "tool_calls_mean": round(statistics.mean(tool_calls), 2) if tool_calls else 0.0,
        "tool_calls_max": max(tool_calls) if tool_calls else 0,
        "tokens_total": sum(tokens),
        "tokens_mean_per_task": round(statistics.mean(tokens), 2) if tokens else 0.0,
        "estimated_full_500_wall_hours": (
            round((statistics.mean(walls) * 500 / 3600), 2) if walls else 0.0
        ),
    }
    (out_dir / "_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


# ---------- Entrypoint ----------


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    task_group = ap.add_mutually_exclusive_group(required=True)
    task_group.add_argument(
        "--tasks", help="instance_id, comma-separated list, or 'all'",
    )
    task_group.add_argument(
        "--smoke", action="store_true",
        help="calibrated 30-task smoke stratified from F.3 full-500",
    )
    ap.add_argument("--dry-plan-only", action="store_true")
    ap.add_argument("--keep-sandbox", action="store_true")
    ap.add_argument("--resume-run", metavar="DIR")
    args = ap.parse_args(argv)

    if args.resume_run:
        out_dir = Path(args.resume_run).expanduser().resolve()
        if not out_dir.exists():
            print(f"[F.3 Path B] resume dir does not exist: {out_dir}", file=sys.stderr)
            return 2
    else:
        BENCH_ROOT.mkdir(parents=True, exist_ok=True)
        out_dir = BENCH_ROOT / f"{datetime.now().strftime('%Y%m%d_%H%M')}_run"
        out_dir.mkdir(parents=True, exist_ok=True)

    if args.smoke:
        task_ids = SMOKE_TASK_IDS
        smoke = True
    elif args.tasks == "all":
        task_ids = None
        smoke = False
    else:
        task_ids = [t.strip() for t in args.tasks.split(",")]
        smoke = False

    tasks = load_tasks(task_ids)
    print(f"[F.3 Path B] resolved {len(tasks)} task(s); dry_plan_only={args.dry_plan_only}", flush=True)

    manifest = {
        "path": "B",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "bff_url": BFF_URL,
        "wall_cap_s": WALL_CAP_S,
        "tool_call_cap": TOOL_CALL_CAP,
        "poll_interval_s": POLL_INTERVAL_S,
        "smoke": smoke,
        "smoke_task_count": len(SMOKE_TASK_IDS) if smoke else 0,
        "task_ids": [t["instance_id"] for t in tasks],
        "dry_plan_only": args.dry_plan_only,
        "keep_sandbox": args.keep_sandbox,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Resume: skip tasks whose per-task JSON already exists in out_dir.
    if args.resume_run:
        existing = {p.stem for p in out_dir.glob("*.json") if p.name != "manifest.json"}
        remaining = [t for t in tasks if t["instance_id"] not in existing]
        print(f"[F.3 Path B] resume: {len(existing)} done, {len(remaining)} remaining", flush=True)
    else:
        remaining = tasks

    t0 = time.time()
    records: list[dict] = []

    # Restore any prior records so summary math is complete on resume.
    if args.resume_run:
        for p in sorted(out_dir.glob("*.json")):
            if p.name in ("manifest.json", "_summary.json"):
                continue
            try:
                records.append(json.loads(p.read_text()))
            except Exception:
                pass

    for i, task in enumerate(remaining, start=1):
        try:
            rec = run_task(
                task=task,
                out_dir=out_dir,
                dry_plan_only=args.dry_plan_only,
                keep_sandbox=args.keep_sandbox,
                task_idx=len(records) + 1,
                task_total=len(tasks),
            )
            records.append(rec)
        except KeyboardInterrupt:
            print("[F.3 Path B] interrupted; partial summary follows", flush=True)
            break
        except Exception as exc:  # pragma: no cover — belt & suspenders
            print(f"[F.3 Path B] task {task['instance_id']} raised: {exc}", flush=True)
            err_record = {
                "instance_id": task["instance_id"],
                "path": "B",
                "error": f"harness exception: {exc}",
                "resolved": False,
            }
            (out_dir / f"{task['instance_id']}.json").write_text(json.dumps(err_record, indent=2))
            records.append(err_record)

    total_wall = time.time() - t0
    _emit_summary(out_dir, records, total_wall)
    print(f"[F.3 Path B] done. results: {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
