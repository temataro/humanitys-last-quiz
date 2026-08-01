"""Groq provider — genuinely free web search via the Compound system.

Groq's ``compound`` models run agentic web search + code execution server-side,
so a plain chat completion against the OpenAI-compatible endpoint comes back
already grounded — no tool wiring, no billing. We use ``requests`` (already a
dependency) rather than the Groq SDK.

Returns ``(raw_text, grounding_urls, model)``. ``grounding_urls`` are best-effort
citations pulled from the ``executed_tools`` the compound system reports.
"""

from __future__ import annotations

import os

import requests

NAME = "groq"
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "groq/compound"  # override via HLQ_GROQ_MODEL


def has_key() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def _grounding_urls(message: dict) -> list[str]:
    """Pull any cited URLs out of the compound system's executed_tools."""
    urls: list[str] = []
    for tool in message.get("executed_tools") or []:
        output = tool.get("output")
        results = None
        if isinstance(output, dict):
            results = output.get("results") or output.get("organic") or output.get("sources")
        if isinstance(results, list):
            for r in results:
                if isinstance(r, dict) and r.get("url"):
                    urls.append(r["url"])
    return urls


def call(prompt: str, timeout: float) -> tuple[str, list[str], str]:
    model = os.environ.get("HLQ_GROQ_MODEL", DEFAULT_MODEL)
    resp = requests.post(
        ENDPOINT,
        headers={
            "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    message = data["choices"][0]["message"]
    return message.get("content") or "", _grounding_urls(message), model
