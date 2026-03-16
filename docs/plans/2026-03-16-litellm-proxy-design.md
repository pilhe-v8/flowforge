# LiteLLM Proxy Integration — Design

**Date:** 2026-03-16
**Status:** Approved

---

## Overview

Introduce a LiteLLM Proxy container as the single LLM gateway for FlowForge. All agent nodes call the proxy via a standard OpenAI-compatible HTTP API. The proxy holds all provider credentials and handles routing, retries, and fallback — FlowForge itself becomes credential-free at the application level.

---

## Providers

| Provider | Models | Role |
|----------|--------|------|
| Mistral | `mistral-large-latest` | Primary (default) |
| Azure OpenAI | `gpt-4o` (standard deployment name) | Fallback |

Routing: Mistral → Azure on failure (3 retries, then cross-provider fallback).

---

## Architecture

```
FlowForge Worker (LLMClient)
         │
         │  OpenAI-compatible HTTP  (http://litellm:4000)
         ▼
   LiteLLM Proxy
         ├── primary  ──▶  Mistral  (mistral-large-latest)
         └── fallback ──▶  Azure OpenAI  (gpt-4o)
```

The LiteLLM Proxy exposes a standard OpenAI API (`/chat/completions`). The FlowForge `LLMClient` switches from calling `litellm.acompletion()` directly to calling the proxy via `openai.AsyncOpenAI(base_url="http://litellm:4000", api_key=master_key)`.

---

## Components

### 1. `litellm.config.yaml` (new, repo root)

Declares two model entries under virtual names. The `fallbacks` router setting tells LiteLLM to try `azure-fallback` automatically whenever the `default` model fails after retries.

```yaml
model_list:
  - model_name: default
    litellm_params:
      model: mistral/mistral-large-latest
      api_key: os.environ/MISTRAL_API_KEY

  - model_name: azure-fallback
    litellm_params:
      model: azure/gpt-4o
      api_key: os.environ/AZURE_OPENAI_API_KEY
      api_base: os.environ/AZURE_OPENAI_API_BASE
      api_version: "2024-02-01"

router_settings:
  fallbacks: [{"default": ["azure-fallback"]}]
  num_retries: 3
  retry_after: 1

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

### 2. `.env` (new, gitignored)

Holds all secrets for local development. Never committed.

```env
MISTRAL_API_KEY=your-mistral-key-here
AZURE_OPENAI_API_KEY=your-azure-key-here
AZURE_OPENAI_API_BASE=https://your-resource.openai.azure.com
LITELLM_MASTER_KEY=sk-flowforge-local
```

### 3. `.env.example` (new, committed)

Safe template showing which vars are needed, with no real values.

### 4. `docker-compose.yml` — add `litellm` service

```yaml
litellm:
  image: ghcr.io/berriai/litellm:main-latest
  ports:
    - "4000:4000"
  volumes:
    - ./litellm.config.yaml:/app/config.yaml
  command: ["--config", "/app/config.yaml", "--port", "4000", "--detailed_debug"]
  env_file: .env
```

Backend and worker gain `depends_on: litellm`.

### 5. `backend/flowforge/config.py` — add two settings

```python
litellm_url: str = "http://localhost:4000"
litellm_master_key: str = "sk-flowforge-local"
```

### 6. `backend/flowforge/llm/client.py` — call proxy instead of litellm directly

Replace `litellm.acompletion()` with `openai.AsyncOpenAI` pointed at the proxy. The `openai` package is already a transitive dependency of `litellm`.

```python
import openai

class LLMClient:
    def __init__(self, base_url: str, api_key: str, default_model: str = "default"):
        self._client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.default_model = default_model
```

The `chat()` method calls `self._client.chat.completions.create(...)` — same response shape, same `LLMResponse` returned.

### 7. `backend/flowforge/worker/graph_cache.py` — pass settings to LLMClient

`_get_runtime_deps()` already constructs `LLMClient`. Update to pass `base_url` and `api_key` from settings.

### 8. `k8s/litellm-deployment.yaml` (new)

K8s Deployment + Service for LiteLLM Proxy, plus a ConfigMap for `litellm.config.yaml` content. Secrets (`MISTRAL_API_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_BASE`, `LITELLM_MASTER_KEY`) added to `k8s/secrets.yaml`.

---

## What Does NOT Change

- `LLMClient.chat(messages, model)` → `LLMResponse` interface is identical
- All existing tests mock `LLMClient.chat` directly — no test changes needed
- All callers (worker, agent nodes) are unchanged

---

## Security

- `.env` is gitignored — real keys never committed
- LiteLLM master key is the only credential FlowForge needs at runtime
- In K8s, all keys live in the `flowforge-secrets` Secret (sealed-secrets in prod)
