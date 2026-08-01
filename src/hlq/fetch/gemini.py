"""Gemini provider — Google-Search-grounded chat completion.

Note: Google Search grounding requires a **billing-enabled** project (it stays
$0 under the free grounded-query allotment, but a pure free-tier key returns
429 on every grounded call). Plain generation is free; grounding is not. Select
this provider with ``HLQ_AGGREGATOR=gemini``.

Returns ``(raw_text, grounding_urls, model)``.
"""

from __future__ import annotations

import os

NAME = "gemini"
DEFAULT_MODEL = "gemini-3.6-flash"  # verified available 2026-08; override via HLQ_GEMINI_MODEL


def has_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def _grounding_urls(response) -> list[str]:
    """Pull cited web URLs out of a grounded response's metadata."""
    urls: list[str] = []
    try:
        for cand in response.candidates or []:
            meta = getattr(cand, "grounding_metadata", None)
            for chunk in (getattr(meta, "grounding_chunks", None) or []):
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    urls.append(web.uri)
    except Exception:  # metadata shape varies by model/SDK; citations are a bonus
        pass
    return urls


def call(prompt: str, timeout: float) -> tuple[str, list[str], str]:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
    model = os.environ.get("HLQ_GEMINI_MODEL", DEFAULT_MODEL)
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
        ),
    )
    return response.text or "", _grounding_urls(response), model
