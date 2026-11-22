"""Optional development-only Zhipu assistant. Research runners do not import it."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODELS = {"simple": "glm-4.7-flash", "development": "glm-5.3-flash"}
ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def assist(prompt, task, *, confirmed_free_models=(), max_output=512):
    """Return an untrusted suggestion and provider usage, or a reason to retain Codex."""
    if task not in MODELS or not 1 <= max_output <= 2048:
        raise ValueError("Invalid development task or output limit")
    model = MODELS[task]
    key = os.environ.get("ZHIPUAI_API_KEY")
    if not key or model not in confirmed_free_models:
        return {"status": "codex_takeover", "model": model,
                "reason": "Credential or confirmed zero-cost entitlement unavailable"}
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output, "stream": False}
    request = Request(ENDPOINT, data=json.dumps(body).encode(),
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=45) as response:
            result = json.load(response)
    except HTTPError as error:
        return {"status": "codex_takeover", "model": model, "http_status": error.code}
    except (URLError, TimeoutError, ValueError):
        return {"status": "codex_takeover", "model": model, "reason": "Provider response unavailable"}
    usage = result.get("usage", {})
    total = usage.get("prompt_tokens")
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
    return {"status": "candidate", "task": task, "model": result.get("model"),
            "provider_id": result.get("id"), "input_tokens": total, "cached_tokens": cached,
            "uncached_tokens": total - cached if type(total) is int and type(cached) is int else None,
            "output_tokens": usage.get("completion_tokens"), "actual_fee": None,
            "answer": result["choices"][0]["message"]["content"]}
