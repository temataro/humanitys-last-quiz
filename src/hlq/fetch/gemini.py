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


def _evidence(interaction):
    """The current API exposes search calls and citations on interaction steps."""
    data = interaction.model_dump(mode="json", exclude_none=True)
    steps = data.get("steps", [])
    urls = []

    def citations(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if (
                    key in {"url", "uri"}
                    and isinstance(item, str)
                    and item.startswith("https://")
                ):
                    urls.append(item)
                else:
                    citations(item)
        elif isinstance(value, list):
            for item in value:
                citations(item)

    citations(steps)
    return {
        "urls": list(dict.fromkeys(urls)),
        "steps": steps,
        "usage": data.get("usage", {}),
    }


def call(prompt, timeout):
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
    model = os.environ.get("HLQ_GEMINI_MODEL", DEFAULT_MODEL)
    client = genai.Client(api_key=api_key)
    started = time.monotonic()
    interaction = client.interactions.create(
        model=model,
        input=prompt,
        tools=[{"type": "google_search", "search_types": ["web_search"]}],
        system_instruction=(
            "Use Google Search to research current factual claims before answering. "
            "Cite the pages you actually searched. Never invent URLs or evidence. "
            "If search cannot verify a claim, omit it."
        ),
        generation_config={"max_output_tokens": 12000},
        store=False,
        timeout=timeout,
    )
    evidence = _evidence(interaction)
    evidence["elapsed_seconds"] = round(time.monotonic() - started, 2)
    return interaction.output_text or "", evidence, model
