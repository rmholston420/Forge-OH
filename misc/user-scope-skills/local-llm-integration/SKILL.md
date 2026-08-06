---
name: local-llm-integration
description: Integrating with locally-hosted LLMs via OpenAI-compatible APIs (Ollama, vLLM, llama.cpp, SGLang). Use whenever writing client code that hits a local model endpoint, choosing between streaming and non-streaming, handling reasoning-mode outputs, wiring tool-calls, or debugging model-name/base-url misconfiguration. Covers per-runtime quirks that generic OpenAI clients don't warn about.
license: MIT
triggers:
  - Ollama
  - vLLM
  - llama.cpp
  - SGLang
  - "localhost:11434"
  - "localhost:8000"
  - "localhost:8080"
  - "/v1/chat/completions"
  - "openai.OpenAI"
  - "AsyncOpenAI"
  - "base_url"
  - streaming
  - "<think>"
  - reasoning
  - tool call
  - tool_calls
  - function calling
---

# Local LLM Integration

Applies whenever code talks to a locally-hosted LLM behind an OpenAI-compatible or native REST API.

## Runtime Cheat Sheet

| Runtime | Default port | OpenAI base URL | Native API | Notes |
|---|---|---|---|---|
| Ollama | 11434 | `http://localhost:11434/v1` | `/api/generate`, `/api/chat` | GGUF-native. Native API has per-role options, `think` toggle. |
| vLLM (Docker) | 8000 | `http://localhost:8000/v1` | OpenAI-compat only | Requires `--served-model-name`. |
| llama.cpp server | 8080 | `http://localhost:8080/v1` | `/completion` | GGUF-only. Faster warm-start than Ollama for tiny models. |
| SGLang | 30000 | `http://localhost:30000/v1` | native `sgl` API | Strongest structured-output support. |

## Base URL Discipline

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="http://127.0.0.1:11434/v1",   # NOTE: trailing /v1 is required
    api_key="ollama",                        # local runtimes ignore this but the SDK requires a non-empty string
)
```

Never point an OpenAI client at `http://localhost:11434` (without `/v1`). The SDK appends `/chat/completions` to whatever base_url you gave it, and Ollama's native API is at `/api/chat` — you get 404s and confusing errors.

## Model Names — Runtime-Specific

The same model has different names in different runtimes:

| Runtime | Typical model name string |
|---|---|
| Ollama | `qwen3-coder:30b`, `llama3.1:8b`, `qwen3-thinking-2507-awq:latest` |
| vLLM | Whatever you passed to `--served-model-name` (e.g., `qwen3-coder-30b`) |
| llama.cpp | Ignored — one model per server; pass anything |

Always list before you POST:

```bash
curl -sf http://localhost:8000/v1/models | jq -r '.data[].id'
curl -sf http://localhost:11434/api/tags | jq -r '.models[].name'
```

## OpenAI-Compat vs Native APIs

### When to use OpenAI-compat (`/v1/chat/completions`)

- You need portable client code that works against multiple runtimes
- Standard `messages`, `tools`, `stream`, `temperature`, `max_tokens` are enough
- You're using LangChain / LlamaIndex / any SDK that speaks OpenAI

### When to use native (`/api/chat` on Ollama)

- Per-role sampling params (`num_ctx`, `num_predict`, `top_k`, `min_p`, `repeat_penalty`)
- The `think: true/false` toggle for reasoning models
- Server-side prompt caching hints

Example — Ollama native call with per-role options:

```python
import httpx

async def ollama_chat(role: str, prompt: str) -> str:
    body = {
        "model": "qwen3-coder:30b" if role == "coder" else "qwen3-planner:30b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": role == "planner",   # only planner gets thinking
        "options": (
            {"num_ctx": 8192, "num_predict": 2048, "temperature": 0.0}
            if role == "coder"
            else {"num_ctx": 32768, "num_predict": 4096, "temperature": 0.7}
        ),
    }
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post("http://127.0.0.1:11434/api/chat", json=body)
    r.raise_for_status()
    return r.json()["message"]["content"]
```

## Reasoning Mode — `<think>` Blocks

Qwen3.6+, R1-family, o1-style models emit `<think>...</think>` before the answer. In OpenAI-compat mode, the raw content field contains both.

**Strip before displaying / scoring:**

```python
import re

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

def strip_reasoning(text: str) -> tuple[str, str]:
    """Returns (visible_answer, thinking_content)."""
    thinks = _THINK_RE.findall(text)
    visible = _THINK_RE.sub("", text).lstrip()
    return visible, "\n".join(thinks)
```

Rules:
- Count `<think>` tokens toward tok/s (the model generated them)
- Strip them from user-facing output
- Never count them toward "useful output length" for cost analysis

## Streaming — When and How

Use streaming when the UI can render tokens as they arrive. Skip streaming for programmatic consumers that need the full response to parse.

OpenAI SDK streaming pattern:

```python
async def stream_answer(prompt: str):
    stream = await client.chat.completions.create(
        model="qwen3-coder-30b",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        yield delta
```

Ollama native streaming:

```python
async with client.stream("POST", "/api/chat", json={..., "stream": True}) as r:
    async for line in r.aiter_lines():
        if not line:
            continue
        obj = json.loads(line)
        yield obj["message"]["content"]
```

**Streaming trap**: usage tokens (total_tokens, prompt_tokens, completion_tokens) usually come only on the FINAL chunk. If you close the stream early, you lose the usage report.

## Tool Calling

Two paradigms:

### OpenAI-compat tools

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]

resp = await client.chat.completions.create(
    model="qwen3-coder-30b",
    messages=messages,
    tools=tools,
    tool_choice="auto",
)
```

For vLLM: launch with `--enable-auto-tool-choice --tool-call-parser qwen3_coder` (Qwen family) — otherwise the model emits tool calls as raw text.

### Reading the response

```python
msg = resp.choices[0].message
if msg.tool_calls:
    for tc in msg.tool_calls:
        fn_name = tc.function.name
        fn_args = json.loads(tc.function.arguments)   # arguments is a JSON string
        # ... dispatch to your handler
```

## Common Failure Modes

### 404 on `/v1/chat/completions`

Wrong base URL — missing `/v1` at the end, or pointed at Ollama's native API path.

### `model not found` on vLLM

You used the HuggingFace repo path but `--served-model-name` was set. List models first: `curl /v1/models`.

### Timeout on first call, fine after

Model loading. First inference triggers weight load. Set client timeout to 180s+ for first call, or warm the runtime with a throwaway request.

### `context length exceeded`

Prompt + max_tokens > server's max-model-len. Either shrink the prompt, lower max_tokens, or relaunch the server with higher `--max-model-len`.

### Streaming works interactively but hangs in code

You're consuming the stream synchronously in an async context, or vice versa. Match the client type to the call: `AsyncOpenAI` + `async for`, or `OpenAI` + `for`.

### Empty `<think>` block on non-reasoning model

Some runtimes always emit the reasoning parser output even for non-thinking models. Strip unconditionally and don't rely on presence of `<think>` to detect thinking.

## Anti-Patterns

- ❌ Hardcoding `http://localhost:11434` as base URL (needs `/v1`)
- ❌ Reusing the same `OpenAI` client across event loops (create per-loop or use `AsyncOpenAI`)
- ❌ `client.chat.completions.create(...)` in sync code inside FastAPI async endpoint (blocks the loop)
- ❌ Not stripping `<think>` before parsing structured output — JSON parsers fail on `<think>{}</think>{"real": "json"}`
- ❌ Assuming Ollama and vLLM take the same model name
- ❌ Passing `api_key=""` to the OpenAI SDK (rejected as empty)
- ❌ Reading `.tool_calls[0].function.arguments` without `json.loads()` (it's a string, not a dict)
- ❌ Ignoring the final chunk's `usage` field, then wondering why cost tracking is empty

## Model Router Pattern

When switching between coder and planner roles:

```python
async def call_model(role: str, prompt: str) -> str:
    if role == "coder":
        return await call_ollama("qwen3-coder:30b", prompt, think=False,
                                  temperature=0.0)
    elif role == "planner":
        return await call_ollama("qwen3-planner:30b", prompt, think=True,
                                  temperature=0.7)
    else:
        raise ValueError(f"unknown role: {role}")
```

Rules:
- Role → model mapping lives in ONE place (a router, not scattered across call sites)
- Sampling params are role-specific, not caller-specific
- Never hardcode a model name at the call site
