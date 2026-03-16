#!/usr/bin/env python3
"""
LiteLLM smoke test — verifies both model aliases are reachable.

Usage:
    python scripts/test_litellm.py

Reads LITELLM_MASTER_KEY from environment or .env file.
Exit 0 if both models respond successfully, exit 1 otherwise.
"""

import os
import sys
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — rely on env vars

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-flowforge-local")
PROMPT = "Say hello in one sentence."

MODELS_TO_TEST = [
    ("default", "Mistral (primary)"),
    ("azure-fallback", "Azure GPT-4o (fallback)"),
]


def test_model(model_id: str, model_label: str) -> bool:
    """Send a chat completion request to model_id. Returns True on success."""
    url = f"{LITELLM_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {LITELLM_MASTER_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": PROMPT}],
    }

    print(f"\n{'=' * 50}")
    print(f"Testing: {model_label} (model={model_id!r})")

    start = time.monotonic()
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        print(f"  FAIL: HTTP {e.response.status_code} — {e.response.text[:200]}")
        return False
    except httpx.RequestError as e:
        print(f"  FAIL: Connection error — {e}")
        return False

    latency_ms = int((time.monotonic() - start) * 1000)
    choice = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    input_tokens = usage.get("prompt_tokens", "?")
    output_tokens = usage.get("completion_tokens", "?")

    print(f"  OK in {latency_ms}ms")
    print(f"  Tokens: {input_tokens} in / {output_tokens} out")
    print(f"  Response: {choice[:120]!r}")
    return True


def main():
    print(f"LiteLLM Smoke Test — {LITELLM_URL}")
    print(f"Master key: {LITELLM_MASTER_KEY[:8]}...")

    results = []
    for model_id, label in MODELS_TO_TEST:
        ok = test_model(model_id, label)
        results.append((label, ok))

    print(f"\n{'=' * 50}")
    print("Summary:")
    all_ok = True
    for label, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\nAll models OK.")
        sys.exit(0)
    else:
        print("\nOne or more models FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
