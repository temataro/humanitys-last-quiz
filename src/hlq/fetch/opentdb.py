"""Trivia — the Open Trivia Database (free, no key).

https://opentdb.com/api.php?amount=N&type=multiple returns multiple-choice
questions with HTML-escaped text. We unescape and keep only the question and its
correct answer, each carrying an opentdb.com citation.
"""

from __future__ import annotations

import html

import requests

from ..provenance import Fact, Source

API = "https://opentdb.com/api.php"
SOURCE = Source("Open Trivia DB", "https://opentdb.com", "CC BY-SA 4.0")


def collect(retrieved_at: str, amount: int = 3, timeout: float = 15.0) -> list[Fact]:
    resp = requests.get(
        API,
        params={"amount": amount, "type": "multiple"},
        headers={"User-Agent": "HumanitysLastQuiz/0.1 (tal@kamar.com)"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("response_code") != 0:
        raise RuntimeError(f"opentdb response_code={data.get('response_code')}")

    facts: list[Fact] = []
    for r in data.get("results", []):
        facts.append(Fact(
            value={"q": html.unescape(r["question"]), "a": html.unescape(r["correct_answer"])},
            source=SOURCE,
            retrieved_at=retrieved_at,
        ))
    return facts
