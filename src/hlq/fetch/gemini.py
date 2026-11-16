# =============================================================================
# gemini.py — Grounded Gemini generation with usage and citation auditing.
#
# Part of Humanity's Last Quiz; see ARCHITECTURE.md for the data flow.
#
# Copyright (c) 2026 Temesgen Ataro <ataro.temesgen@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# =============================================================================

"""Google-Search-grounded Gemini generation.

Uses the existing configured model; billing and search allowances depend on the
Google project. Returns (raw_text, grounding_and_usage_metadata, model).
"""

from __future__ import annotations

import os
import time

NAME = "gemini"
DEFAULT_MODEL = (
    "gemini-3.6-flash"  # verified available 2026-08; override via HLQ_GEMINI_MODEL
)


def has_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def _evidence(response):
    """Retain claim-level grounding and usage for the raw audit archive."""
    metadata = []
    urls = []
    for candidate in response.candidates or []:
        grounding = getattr(candidate, "grounding_metadata", None)
        if grounding:
            metadata.append(grounding.model_dump(mode="json", exclude_none=True))
            for chunk in grounding.grounding_chunks or []:
                if chunk.web and chunk.web.uri:
                    urls.append(chunk.web.uri)
    usage = getattr(response, "usage_metadata", None)
    return {
        "urls": urls,
        "grounding": metadata,
        "usage": usage.model_dump(mode="json", exclude_none=True) if usage else {},
    }


def call(prompt, timeout):
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
    model = os.environ.get("HLQ_GEMINI_MODEL", DEFAULT_MODEL)
    client = genai.Client(api_key=api_key)
    started = time.monotonic()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.1,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
        ),
    )
    evidence = _evidence(response)
    evidence["elapsed_seconds"] = round(time.monotonic() - started, 2)
    return response.text or "", evidence, model
