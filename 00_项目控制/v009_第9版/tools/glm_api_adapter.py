"""Bounded GLM API adapter for experimental research calls.

No network request is made unless explicitly enabled by the caller. No secrets are
persisted. This adapter does not change academic reviewer/model assignments.
"""
from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ALLOWED_HOSTS = {"open.bigmodel.cn", "api.z.ai"}


class GLMError(RuntimeError):
    pass


def _endpoint():
    from urllib.parse import urlparse
    endpoint = os.environ.get("AI_PAPER_GLM_ENDPOINT", DEFAULT_ENDPOINT)
    parsed = urlparse(endpoint)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username or parsed.password
            or parsed.path != "/api/paas/v4/chat/completions"
            or parsed.query or parsed.fragment):
        raise GLMError("Unapproved GLM API endpoint")
    return endpoint


def call_glm(messages, *, model="glm-4.7-flash", max_output_tokens=256,
             max_input_chars=12000, timeout=30, allow_paid=False, transport=None):
    """Single bounded call; explicit opt-in prevents accidental paid requests.

    transport(request, timeout) can be injected for deterministic offline tests.
    No automatic retry: 429 and network failures must not incur silent charges.
    """
    if not allow_paid:
        raise GLMError("Live GLM API use requires explicit allow_paid=True")
    key = os.environ.get("ZHIPUAI_API_KEY") or os.environ.get("ZAI_API_KEY")
    if not key:
        raise GLMError("Missing ZHIPUAI_API_KEY or ZAI_API_KEY")
    if not isinstance(model, str) or not model.startswith("glm-") or len(model) > 64:
        raise GLMError("Invalid model")
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 4096:
        raise GLMError("Invalid output limit")
    if type(timeout) not in (int, float) or not 1 <= timeout <= 120:
        raise GLMError("Invalid timeout")
    if not isinstance(messages, list) or not messages or len(messages) > 20:
        raise GLMError("Invalid messages")
    if any(not isinstance(m, dict) or m.get("role") not in ("system", "user", "assistant")
           or not isinstance(m.get("content"), str) for m in messages):
        raise GLMError("Invalid message schema")
    if sum(len(m["content"]) for m in messages) > max_input_chars:
        raise GLMError("Input character budget exceeded")
    payload = json.dumps({"model": model, "messages": messages,
                          "max_tokens": max_output_tokens, "stream": False},
                         ensure_ascii=False).encode("utf-8")
    req = Request(_endpoint(), data=payload, method="POST",
                  headers={"Authorization": "Bearer " + key,
                           "Content-Type": "application/json"})
    try:
        if transport is None:
            transport = urlopen
        with transport(req, timeout=timeout) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise GLMError("GLM HTTP status " + str(exc.code)) from None
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise GLMError("GLM request failed: " + type(exc).__name__) from None
    try:
        answer = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        if not isinstance(answer, str):
            raise ValueError("nontext answer")
    except (KeyError, IndexError, TypeError, ValueError):
        raise GLMError("Malformed GLM response") from None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    details = usage.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens") if isinstance(details, dict) else None
    return {"status": "ok", "provider": "zhipu_api", "model": data.get("model", model),
            "provider_id": data.get("id"), "answer": answer,
            "input_tokens": prompt if type(prompt) is int else None,
            "cached_input_tokens": cached if type(cached) is int else None,
            "output_tokens": completion if type(completion) is int else None,
            "actual_fee": None, "academic_approval": False}


def smoke_test(*, live=False, model="glm-4.7-flash", transport=None):
    """Offline by default; live mode makes exactly one small real request."""
    if not live:
        return {"status": "dry_run", "live_calls": 0, "model": model,
                "endpoint": _endpoint()}
    return call_glm([{"role": "user", "content": "只回复 OK"}], model=model,
                    max_output_tokens=16, allow_paid=True, transport=transport)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Experimental GLM API smoke test")
    parser.add_argument("--live", action="store_true",
                        help="Make one real potentially billable request")
    parser.add_argument("--model", default="glm-4.7-flash")
    args = parser.parse_args()
    try:
        result = smoke_test(live=args.live, model=args.model)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except GLMError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
