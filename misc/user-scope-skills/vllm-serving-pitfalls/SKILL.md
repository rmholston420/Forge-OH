---
name: vllm-serving-pitfalls
description: Practical hazards of serving quantized LLMs with vLLM on consumer / prosumer NVIDIA GPUs (RTX 4090 / 5090, Blackwell / Ada). Use whenever launching vLLM, choosing a quantization, adjusting KV-cache dtype, or debugging OOM / cold-start / health-check issues. Covers weight-format detection, VRAM budgeting, mandatory flags, health check timing, and the runtime-handoff dance with Ollama on a single-GPU box.
license: MIT
triggers:
  - vllm
  - "docker run vllm"
  - "vllm-openai"
  - quantization
  - AWQ
  - GPTQ
  - NVFP4
  - FP8
  - GGUF
  - "compressed-tensors"
  - "--gpu-memory-utilization"
  - "--max-model-len"
  - "--served-model-name"
  - "--reasoning-parser"
  - kv-cache
  - trust-remote-code
  - "port 8000"
  - OOM
  - CUDA out of memory
---

# vLLM Serving Pitfalls

Field-tested on RTX 5090 (32 GB, Blackwell SM_120) + vLLM 0.10.2 (`vllm/vllm-openai:v0.10.2`). Most of it applies to any consumer/prosumer NVIDIA GPU.

## Hard Rules

1. **Only one runtime owns the GPU at a time.** Stop Ollama before starting vLLM (and vice versa). No dual-stack on a single card.
2. **Auto-detect quantization first; only pass `--quantization` if auto-detect fails.** vLLM reads `hf_quant_config.json` / `recipe.yaml` / `config.json` and picks the right method. Passing the wrong flag causes a hard `ValidationError`.
3. **`--served-model-name` is mandatory.** Without it, `/v1/models` returns the full local path as the model ID and every OpenAI-compat client breaks.
4. **`--trust-remote-code` is mandatory for Qwen3 family.** Custom modeling code lives in the repo.
5. **Health-check by `curl /v1/models`, not by uvicorn log line.** The `Uvicorn running` message fires before the model finishes loading. Model load takes 30–90s more.
6. **Never emit a paste block starting with `set -e`.** A `docker rm -f` on a nonexistent container will kill the user's shell.

## VRAM Budget Cheatsheet

Rule: **weight bytes ≤ (GPU VRAM − 2 GB CUDA overhead − KV cache budget)**.

For a 32 GB card:
- 2 GB reserved for CUDA/driver
- KV cache budget depends on `max-model-len` and batch size; reserve 4–10 GB
- Weight budget: 20–26 GB

| Model class | Weight footprint | Verdict on 32 GB |
|---|---:|---|
| 30B MoE Q4_K_M / AWQ-4 | 17–18 GB | ✅ 12 GB KV headroom |
| 30B MoE Q6_K | ~24 GB | ⚠️ small context only |
| 35B MoE Q4 / NVFP4 | 22–24 GB | ✅ 6–8 GB KV headroom |
| 35B MoE FP8 | ~35 GB | ❌ OOM — use NVFP4 or AWQ |
| 70B dense Q4 | ~40 GB | ❌ OOM |
| 70B MoE Q4 (3–8B active) | ~40 GB weight | ❌ OOM |

Check exact weight bytes before pulling:

```bash
REPO="cyankiwi/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit"
curl -sL "https://huggingface.co/api/models/$REPO/tree/main" \
  | jq '[.[] | select(.path | endswith(".safetensors")) | (.size // .lfs.size // 0)] | add / 1073741824'
```

## Weight-Format Detection

**HuggingFace repo names lie about format.** `AWQ-4bit` in a repo name may be `compressed-tensors` under the hood. Always verify before assuming:

```bash
MODEL_DIR=~/models/qwen3-coder-30b-awq

# compressed-tensors indicator
[ -f "$MODEL_DIR/recipe.yaml" ] && echo "compressed-tensors (or omit --quantization)"

# config-declared method
jq -r '.quantization_config.quant_method // .quant_method // "none"' "$MODEL_DIR/config.json"

# NVFP4 indicator
[ -f "$MODEL_DIR/hf_quant_config.json" ] && \
  jq -r '.quantization.quant_algo // "unknown"' "$MODEL_DIR/hf_quant_config.json"
```

## Quantization Flag Matrix

Default: **omit `--quantization`** and let vLLM auto-detect. Only specify when auto-detect fails.

| Weight format | `--quantization <value>` | Notes |
|---|---|---|
| compressed-tensors (modern AWQ/GPTQ repos) | `compressed-tensors` | Auto-detected via `recipe.yaml`. Do NOT use `awq_marlin`. |
| AWQ 4-bit (legacy repos, Marlin kernel) | `awq_marlin` | Only if config.json declares `quant_method: awq`. |
| AWQ 4-bit (generic fallback) | `awq` | Slower. |
| GPTQ 4-bit | `gptq_marlin` or `gptq` | Marlin is faster. |
| NVFP4 (Blackwell-native) | `modelopt_fp4` | vLLM v0.10.2+; near-FP8 quality, 2× INT4 compute. |
| FP8 (E4M3 weights) | `fp8` | Weights only. Beware: 35B FP8 = OOM on 32 GB. |
| MoE WNA16 | `moe_wna16` | Official Qwen quants sometimes ship this. |
| GGUF | not supported | Use Ollama or llama.cpp. |

When a flag fails at launch:

```bash
docker logs vllm-bench 2>&1 | grep -iE "(quant|not supported|invalid choice)"
```

The error usually lists accepted enum values. Never guess a replacement.

## Canonical Docker Launch

```bash
sudo systemctl stop ollama 2>/dev/null || true
sleep 3
docker rm -f vllm-bench 2>/dev/null || true

docker run -d --name vllm-bench --gpus all \
  --ipc=host --shm-size=8g \
  -v ~/models:/models:ro \
  -p 8000:8000 \
  -e HF_HUB_OFFLINE=1 \
  vllm/vllm-openai:v0.10.2 \
  --model /models/qwen3-coder-30b-awq \
  --served-model-name qwen3-coder-30b \
  --host 0.0.0.0 --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 32768 \
  --dtype auto \
  --trust-remote-code
```

Wait for `/v1/models`, not for uvicorn:

```bash
for i in $(seq 1 90); do
  curl -sf http://localhost:8000/v1/models >/dev/null 2>&1 && { echo "READY (${i}s)"; break; }
  sleep 2
done
```

## Qwen3-Specific Flags

- `--trust-remote-code` — always
- `--reasoning-parser qwen3` — when thinking mode is enabled (planner cells). Not needed for coder role.
- `--enable-auto-tool-choice --tool-call-parser qwen3_coder` — when tool calls are expected

## KV Cache Compression

Independent of weight quantization:

```
--kv-cache-dtype fp8
```

Saves ~46% of KV memory, verified >97% quality recovery on Qwen3-30B. Safe to combine with any weight quant.

## Common Failure Modes

### `torch.OutOfMemoryError` at model load

Weight bytes exceed available VRAM. Options:
1. Smaller quant (Q4 instead of Q6)
2. Lower `--gpu-memory-utilization` won't help — you're OOM on weights, not KV
3. Reduce `--max-model-len` won't help either — same reason
4. Different model entirely

### `Quantization method X does not match Y`

You passed `--quantization X` but the model config says `Y`. Solution: remove `--quantization` and let auto-detect handle it.

### `/v1/models` never becomes ready

- Container may still be loading weights (30–90s normal, up to 5 min for cold-cache 30B+)
- Check `docker logs vllm-bench 2>&1 | tail -30` — look for `Loading model weights` progress or a stack trace
- If it exited: `docker ps -a | grep vllm-bench`

### Silent CPU-only inference

Missing `--gpus all` on `docker run`. Verify:

```bash
docker exec vllm-bench nvidia-smi
```

Should list the GPU. If it says "No devices found," you launched without `--gpus all`.

### Container OOM-killed by Docker (not by CUDA)

Add `--shm-size=8g`. PyTorch multiprocessing needs shared memory; default 64 MB isn't enough.

### `--host 127.0.0.1` blocks external access

Docker's port mapping needs the container to listen on `0.0.0.0`. Use `--host 0.0.0.0` and map with `-p 127.0.0.1:8000:8000` if you want to restrict host binding.

## Anti-Patterns

- ❌ Running Ollama and vLLM concurrently on the same GPU
- ❌ Launching vLLM without `--served-model-name`
- ❌ Guessing quantization flag names from repo names
- ❌ Assuming GPU is free immediately after `docker rm` / `systemctl stop` (verify `nvidia-smi`)
- ❌ Pulling FP8 35B onto a single 32 GB card
- ❌ `--gpu-memory-utilization 0.95+` (no room for CUDA workspace)
- ❌ Testing readiness by waiting for `Uvicorn running` log line
- ❌ `docker run` without `--gpus all`, `--ipc=host`, `--shm-size=8g`
- ❌ `--host 127.0.0.1` in a Docker context

## Verification After Launch

```bash
# Model registered under the right name
curl -sf http://localhost:8000/v1/models | jq '.data[].id'

# One-shot inference
curl -sf http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3-coder-30b","messages":[{"role":"user","content":"reply with the single word: hello"}],"max_tokens":10}' \
  | jq -r '.choices[0].message.content'

# GPU utilization
nvidia-smi --query-gpu=memory.used,memory.free,utilization.gpu --format=csv
```
