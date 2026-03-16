# LiteLLM Proxy Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a LiteLLM Proxy Docker service as the single LLM gateway for FlowForge, routing to Mistral (primary) and Azure OpenAI (fallback), and update `LLMClient` to call it via the standard OpenAI-compatible HTTP API.

**Architecture:** A `litellm` container (port 4000) is added to `docker-compose.yml`. It reads provider credentials from `.env` and routing config from `litellm.config.yaml`. The `LLMClient` in `backend/flowforge/llm/client.py` switches from calling `litellm.acompletion()` directly to calling the proxy via `openai.AsyncOpenAI`. The `LLMClient` public interface (`chat(messages, model) → LLMResponse`) stays identical so no callers change.

**Tech Stack:** LiteLLM Proxy (`ghcr.io/berriai/litellm:main-latest`), `openai` Python SDK (already a transitive dep of `litellm`), Mistral API, Azure OpenAI API.

---

## Task 1: Proxy config file and credentials template

**Files:**
- Create: `litellm.config.yaml`
- Create: `.env.example`
- Modify: `.gitignore`

**Step 1: Create `litellm.config.yaml` at the repo root**

```yaml
# LiteLLM Proxy configuration
# Docs: https://docs.litellm.ai/docs/proxy/configs

model_list:
  # Primary: Mistral
  - model_name: default
    litellm_params:
      model: mistral/mistral-large-latest
      api_key: os.environ/MISTRAL_API_KEY

  # Fallback: Azure OpenAI
  - model_name: azure-fallback
    litellm_params:
      model: azure/gpt-4o
      api_key: os.environ/AZURE_OPENAI_API_KEY
      api_base: os.environ/AZURE_OPENAI_API_BASE
      api_version: "2024-02-01"

router_settings:
  # Automatically failover from default → azure-fallback on error
  fallbacks: [{"default": ["azure-fallback"]}]
  num_retries: 3
  retry_after: 1

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

**Step 2: Create `.env.example` at the repo root**

```env
# LiteLLM Proxy credentials — copy to .env and fill in real values
# .env is gitignored and must NEVER be committed

# Mistral (primary LLM provider)
MISTRAL_API_KEY=your-mistral-api-key-here

# Azure OpenAI (fallback provider)
AZURE_OPENAI_API_KEY=your-azure-api-key-here
AZURE_OPENAI_API_BASE=https://your-resource-name.openai.azure.com

# LiteLLM Proxy master key — used by FlowForge to authenticate to the proxy
# Can be any string for local dev; use a strong random value in production
LITELLM_MASTER_KEY=sk-flowforge-local
```

**Step 3: Ensure `.env` is gitignored**

Open `.gitignore` (or create it at the repo root if absent). Add these lines if not already present:

```
.env
*.env
```

**Step 4: Create your local `.env` file**

Copy `.env.example` to `.env` and fill in your real Mistral and Azure credentials. You will need:
- Mistral API key from https://console.mistral.ai
- Azure OpenAI API key and endpoint from your Azure portal

```bash
cp .env.example .env
# Now edit .env with your real keys
```

**Step 5: Commit config file and template (NOT .env)**

```bash
git add litellm.config.yaml .env.example .gitignore
git commit -m "feat: add LiteLLM proxy config and credentials template"
```

Expected: commit succeeds; `.env` does NOT appear in `git status`.

---

## Task 2: Add LiteLLM Proxy service to docker-compose

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Read the current docker-compose.yml**

Note the existing structure. We will add one new service (`litellm`) and update `backend` and `worker` to depend on it.

**Step 2: Add the `litellm` service**

In `docker-compose.yml`, add the following service block between `qdrant` and `backend`:

```yaml
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    ports:
      - "4000:4000"
    volumes:
      - ./litellm.config.yaml:/app/config.yaml
    command: ["--config", "/app/config.yaml", "--port", "4000", "--detailed_debug"]
    env_file: .env
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:4000/health/liveliness || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
```

**Step 3: Add litellm dependency to backend and worker**

In the `backend` service's `depends_on` block, add:
```yaml
      litellm:
        condition: service_healthy
```

Do the same for the `worker` service.

**Step 4: Add LITELLM env vars to backend and worker environment blocks**

In both `backend` and `worker` `environment:` sections, add:
```yaml
      FLOWFORGE_LITELLM_URL: http://litellm:4000
      FLOWFORGE_LITELLM_MASTER_KEY: sk-flowforge-local
```

**Step 5: Verify the YAML is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('ok')"
```

Expected: `ok`

**Step 6: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add LiteLLM proxy service to docker-compose"
```

---

## Task 3: Add LiteLLM settings to config.py

**Files:**
- Modify: `backend/flowforge/config.py`

**Step 1: Read the current config.py**

Current content:
```python
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://flowforge:flowforge@localhost:5432/flowforge"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "dev-secret-change-in-production"
    jwt_secret: str = "dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    health_port: int = 8081
    allowed_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "env_prefix": "FLOWFORGE_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Step 2: Add two new settings fields**

Add `litellm_url` and `litellm_master_key` after `allowed_origins`:

```python
    litellm_url: str = "http://localhost:4000"
    litellm_master_key: str = "sk-flowforge-local"
```

The full updated file:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://flowforge:flowforge@localhost:5432/flowforge"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "dev-secret-change-in-production"
    jwt_secret: str = "dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    health_port: int = 8081
    allowed_origins: list[str] = ["http://localhost:5173"]
    litellm_url: str = "http://localhost:4000"
    litellm_master_key: str = "sk-flowforge-local"

    model_config = {"env_file": ".env", "env_prefix": "FLOWFORGE_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Step 3: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('backend/flowforge/config.py').read()); print('ok')"
```

Expected: `ok`

**Step 4: Commit**

```bash
git add backend/flowforge/config.py
git commit -m "feat: add litellm_url and litellm_master_key to Settings"
```

---

## Task 4: Rewrite LLMClient to call the proxy

**Files:**
- Modify: `backend/flowforge/llm/client.py`
- Modify: `backend/tests/llm/test_client.py`

**Step 1: Write the updated tests first (TDD)**

The existing tests patch `flowforge.llm.client.litellm.acompletion`. After the change, `LLMClient` will use `openai.AsyncOpenAI` instead. We need to:
1. Update the mock target
2. Update `LLMClient()` constructor call to pass `base_url` and `api_key`
3. Keep all assertions on `LLMResponse` fields unchanged (the public contract doesn't change)

Replace `backend/tests/llm/test_client.py` with:

```python
"""Tests for LLMClient — proxy-based implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import is_dataclass

from flowforge.llm.client import LLMClient, LLMResponse

BASE_URL = "http://localhost:4000"
API_KEY = "sk-test"


def make_openai_response(content: str, model: str, prompt_tokens: int, completion_tokens: int):
    """Build a mock openai ChatCompletion response."""
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


class TestLLMResponse:
    def test_is_dataclass(self):
        assert is_dataclass(LLMResponse)

    def test_fields(self):
        resp = LLMResponse(
            content="hello",
            model="default",
            input_tokens=10,
            output_tokens=5,
        )
        assert resp.content == "hello"
        assert resp.model == "default"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5


class TestLLMClientChat:
    def _make_client(self, default_model: str = "default") -> LLMClient:
        return LLMClient(base_url=BASE_URL, api_key=API_KEY, default_model=default_model)

    @pytest.mark.asyncio
    async def test_calls_openai_create(self):
        """chat() should call the openai client's chat.completions.create."""
        mock_response = make_openai_response("Hi there", "default", 10, 5)
        messages = [{"role": "user", "content": "Hello"}]

        with patch(
            "flowforge.llm.client.openai.AsyncOpenAI"
        ) as MockAsyncOpenAI:
            mock_create = AsyncMock(return_value=mock_response)
            MockAsyncOpenAI.return_value.chat.completions.create = mock_create

            client = self._make_client()
            await client.chat(messages)

        mock_create.assert_awaited_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "default"
        assert call_kwargs["messages"] == messages
        assert call_kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_returns_llm_response(self):
        """chat() should return a properly mapped LLMResponse."""
        mock_response = make_openai_response("Result text", "default", 20, 8)

        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value.chat.completions.create = AsyncMock(
                return_value=mock_response
            )
            client = self._make_client()
            result = await client.chat([{"role": "user", "content": "test"}])

        assert isinstance(result, LLMResponse)
        assert result.content == "Result text"
        assert result.model == "default"
        assert result.input_tokens == 20
        assert result.output_tokens == 8

    @pytest.mark.asyncio
    async def test_model_override(self):
        """Passing model= should override the default."""
        mock_response = make_openai_response("ok", "azure-fallback", 5, 3)

        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            mock_create = AsyncMock(return_value=mock_response)
            MockAsyncOpenAI.return_value.chat.completions.create = mock_create

            client = self._make_client(default_model="default")
            result = await client.chat(
                [{"role": "user", "content": "hi"}], model="azure-fallback"
            )

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "azure-fallback"
        assert result.model == "azure-fallback"

    @pytest.mark.asyncio
    async def test_default_model_used_when_not_specified(self):
        """When model= is not passed, default_model should be used."""
        mock_response = make_openai_response("response", "default", 1, 1)

        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            mock_create = AsyncMock(return_value=mock_response)
            MockAsyncOpenAI.return_value.chat.completions.create = mock_create

            client = self._make_client(default_model="default")
            await client.chat([{"role": "user", "content": "hi"}])

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "default"

    @pytest.mark.asyncio
    async def test_token_counts_mapped_correctly(self):
        """input_tokens/output_tokens should come from prompt/completion tokens."""
        mock_response = make_openai_response("text", "default", 100, 50)

        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value.chat.completions.create = AsyncMock(
                return_value=mock_response
            )
            client = self._make_client()
            result = await client.chat([{"role": "user", "content": "test"}])

        assert result.input_tokens == 100
        assert result.output_tokens == 50

    @pytest.mark.asyncio
    async def test_proxy_base_url_and_key_passed_to_client(self):
        """LLMClient must pass base_url and api_key to openai.AsyncOpenAI."""
        mock_response = make_openai_response("ok", "default", 1, 1)

        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value.chat.completions.create = AsyncMock(
                return_value=mock_response
            )
            LLMClient(base_url="http://proxy:4000", api_key="sk-secret")

        MockAsyncOpenAI.assert_called_once_with(
            base_url="http://proxy:4000", api_key="sk-secret"
        )
```

**Step 2: Run tests to confirm they fail**

```bash
cd backend && python3 -m pytest tests/llm/test_client.py -v
```

Expected: all 6 tests FAIL (LLMClient still uses old litellm-direct implementation).

**Step 3: Rewrite `backend/flowforge/llm/client.py`**

```python
"""LLM client — calls the LiteLLM Proxy via the OpenAI-compatible HTTP API."""

import openai
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Typed wrapper around a chat completion response."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient:
    """Async LLM client that calls a LiteLLM Proxy endpoint.

    The proxy is OpenAI-API-compatible, so we use the standard openai SDK
    pointed at the proxy's base URL.  The proxy handles provider routing,
    retries, and fallback — this client stays credential-free.

    Args:
        base_url:      Full URL of the LiteLLM Proxy, e.g. ``http://litellm:4000``.
        api_key:       LiteLLM master key (set in the proxy's general_settings).
        default_model: Virtual model name declared in ``litellm.config.yaml``.
                       Defaults to ``"default"`` (Mistral primary → Azure fallback).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:4000",
        api_key: str = "sk-flowforge-local",
        default_model: str = "default",
    ):
        self._client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.default_model = default_model

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request via the LiteLLM Proxy.

        Args:
            messages: OpenAI-style message list, e.g.
                      [{"role": "system", "content": "..."}, ...]
            model:    Override the virtual model name for this request.
                      Must match a ``model_name`` in ``litellm.config.yaml``.
        """
        target_model = model or self.default_model
        response = await self._client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=0.3,
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=target_model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
```

**Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/llm/test_client.py -v
```

Expected: all 6 tests PASS.

**Step 5: Run the full test suite**

```bash
python3 -m pytest --tb=short -q
```

Expected: 385+ tests pass (same count as before, none broken).

**Step 6: Commit**

```bash
git add backend/flowforge/llm/client.py backend/tests/llm/test_client.py
git commit -m "feat: switch LLMClient to call LiteLLM Proxy via openai SDK"
```

---

## Task 5: Wire LLMClient to settings in graph_cache

**Files:**
- Modify: `backend/flowforge/worker/graph_cache.py`
- Modify: `backend/tests/worker/test_graph_cache.py` (if it exists; otherwise skip)

**Step 1: Read current graph_cache.py**

The relevant section is `_get_runtime_deps()`:

```python
if _llm_client is None:
    _llm_client = LLMClient()
```

This uses the default `LLMClient()` constructor which hardcodes `http://localhost:4000` and `sk-flowforge-local`. In production (K8s/Docker), the proxy URL and key come from env vars via Settings. We need to pull them from `get_settings()`.

**Step 2: Update `_get_runtime_deps()` in `graph_cache.py`**

Add the settings import at the top of the file:

```python
from flowforge.config import get_settings
```

Then update the `_llm_client` creation inside `_get_runtime_deps()`:

```python
    if _llm_client is None:
        settings = get_settings()
        _llm_client = LLMClient(
            base_url=settings.litellm_url,
            api_key=settings.litellm_master_key,
        )
```

**Step 3: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('backend/flowforge/worker/graph_cache.py').read()); print('ok')"
```

Expected: `ok`

**Step 4: Run the full test suite**

```bash
cd backend && python3 -m pytest --tb=short -q
```

Expected: all tests pass.

**Step 5: Commit**

```bash
git add backend/flowforge/worker/graph_cache.py
git commit -m "feat: wire LLMClient to litellm_url/litellm_master_key from Settings"
```

---

## Task 6: K8s manifests — LiteLLM deployment

**Files:**
- Create: `k8s/litellm-deployment.yaml`
- Modify: `k8s/configmap.yaml`
- Modify: `k8s/secrets.yaml`

**Step 1: Add LiteLLM URL and master key to ConfigMap**

Read `k8s/configmap.yaml`. Add two entries to the `data:` section:

```yaml
  FLOWFORGE_LITELLM_URL: http://litellm:4000
  FLOWFORGE_LITELLM_MASTER_KEY: sk-flowforge-local
```

Note: `LITELLM_MASTER_KEY` is used directly by the proxy container (no `FLOWFORGE_` prefix needed for it), but `FLOWFORGE_LITELLM_MASTER_KEY` is the value FlowForge's Python settings reads. Keep both separate.

**Step 2: Add provider secrets to secrets.yaml**

Read `k8s/secrets.yaml`. Add three placeholder entries to `data:`:

```yaml
  # LiteLLM provider credentials — replace with real base64-encoded values
  MISTRAL_API_KEY: cGxhY2Vob2xkZXI=
  AZURE_OPENAI_API_KEY: cGxhY2Vob2xkZXI=
  AZURE_OPENAI_API_BASE: cGxhY2Vob2xkZXI=
  LITELLM_MASTER_KEY: cGxhY2Vob2xkZXI=
```

(`cGxhY2Vob2xkZXI=` is base64 of `"placeholder"`)

**Step 3: Create `k8s/litellm-deployment.yaml`**

```yaml
# Build: docker pull ghcr.io/berriai/litellm:main-latest
# LiteLLM Proxy — single LLM gateway for all FlowForge services
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flowforge-litellm
  namespace: flowforge
  labels:
    app: litellm
spec:
  replicas: 1
  selector:
    matchLabels:
      app: litellm
  template:
    metadata:
      labels:
        app: litellm
    spec:
      containers:
        - name: litellm
          image: ghcr.io/berriai/litellm:main-latest
          args: ["--config", "/app/config.yaml", "--port", "4000"]
          ports:
            - containerPort: 4000
          env:
            - name: MISTRAL_API_KEY
              valueFrom:
                secretKeyRef:
                  name: flowforge-secrets
                  key: MISTRAL_API_KEY
            - name: AZURE_OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: flowforge-secrets
                  key: AZURE_OPENAI_API_KEY
            - name: AZURE_OPENAI_API_BASE
              valueFrom:
                secretKeyRef:
                  name: flowforge-secrets
                  key: AZURE_OPENAI_API_BASE
            - name: LITELLM_MASTER_KEY
              valueFrom:
                secretKeyRef:
                  name: flowforge-secrets
                  key: LITELLM_MASTER_KEY
          volumeMounts:
            - name: config
              mountPath: /app/config.yaml
              subPath: config.yaml
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          readinessProbe:
            httpGet:
              path: /health/liveliness
              port: 4000
            initialDelaySeconds: 15
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health/liveliness
              port: 4000
            initialDelaySeconds: 30
            periodSeconds: 30
      volumes:
        - name: config
          configMap:
            name: litellm-config
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: litellm-config
  namespace: flowforge
data:
  config.yaml: |
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
---
apiVersion: v1
kind: Service
metadata:
  name: litellm
  namespace: flowforge
spec:
  selector:
    app: litellm
  ports:
    - port: 4000
      targetPort: 4000
```

**Step 4: Verify all YAML files parse**

```bash
python3 -c "
import yaml, glob
for f in glob.glob('k8s/*.yaml'):
    yaml.safe_load_all(open(f))
print('all ok')
"
```

Expected: `all ok`

**Step 5: Commit**

```bash
git add k8s/litellm-deployment.yaml k8s/configmap.yaml k8s/secrets.yaml
git commit -m "feat: add LiteLLM K8s deployment, update ConfigMap and Secrets"
```

---

## Task 7: Smoke test the local stack

> This task is manual verification — no code changes.

**Step 1: Populate your `.env` with real credentials**

```bash
# Edit .env with real keys — do NOT commit this file
```

**Step 2: Start the stack**

```bash
docker compose up litellm --build
```

Wait until you see `LiteLLM: Proxy initialized` in the logs (may take 30–60 seconds on first pull).

**Step 3: Verify the proxy is healthy**

```bash
curl http://localhost:4000/health/liveliness
```

Expected response: `{"status": "healthy"}`

**Step 4: Send a test completion via the proxy**

```bash
curl -s http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-flowforge-local" \
  -d '{
    "model": "default",
    "messages": [{"role": "user", "content": "Say hello in one word"}]
  }' | python3 -m json.tool
```

Expected: A JSON response with `choices[0].message.content` containing a greeting from Mistral.

**Step 5: Verify fallback (optional)**

Temporarily set `MISTRAL_API_KEY=invalid` in `.env`, restart the litellm container, and re-run the completion request. LiteLLM should transparently retry and then fall back to Azure. Check litellm logs for `Falling back to azure-fallback`. Restore the real key afterwards.

**Step 6: Start the full stack and confirm backend connects**

```bash
docker compose up --build
```

In another terminal:

```bash
curl http://localhost:8000/health
```

Expected: `{"status": "ok"}`

No code to commit — this is a verification step only.

---

## Task 8: Push to GitHub

**Step 1: Push all commits**

```bash
git push origin main
```

Expected: push succeeds, all commits land on GitHub.
