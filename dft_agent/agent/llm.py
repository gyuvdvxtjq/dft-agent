"""LLM client: OpenAI-compatible chat completions against Discovery token-plan.

Structured outputs are extracted from the first JSON object in the reply and
validated with Pydantic; on validation failure the caller may retry once.
"""

from __future__ import annotations

import json
import re

import httpx
from pydantic import BaseModel, ValidationError

from dft_agent.config import settings


class LLMError(RuntimeError):
    pass


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.2,
         max_tokens: int = 2000, timeout: float = 120.0) -> str:
    if not settings.LLM_API_KEY:
        raise LLMError("DFT_LLM_API_KEY not configured (.env)")
    body = {
        "model": model or settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    r = httpx.post(
        f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
        json=body, timeout=timeout,
    )
    if r.status_code != 200:
        raise LLMError(f"LLM {r.status_code}: {r.text[:200]}")
    data = r.json()
    usage = data.get("usage", {}) or {}
    content = data["choices"][0]["message"]["content"]
    # token accounting is surfaced to the caller via attribute-ish return
    return content, usage.get("total_tokens", 0)


def structured(messages: list[dict], schema: type[BaseModel], model: str | None = None,
               temperature: float = 0.2) -> BaseModel:
    """Ask the LLM for JSON conforming to `schema`; tolerant to markdown fences."""
    content, tokens = chat(messages + [
        {"role": "system", "content": f"Reply with a single JSON object only. Schema keys: "
                                       f"{list(schema.model_fields.keys())}. No prose, no markdown fences."}
    ], model=model, temperature=temperature)
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        raise LLMError(f"no JSON object in reply: {content[:200]}")
    try:
        return schema.model_validate_json(m.group(0))
    except ValidationError as e:
        raise LLMError(f"schema validation failed: {e.errors()[:3]}") from e
