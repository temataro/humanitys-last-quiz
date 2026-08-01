"""Wikipedia "On this day" — the deterministic backbone.

Births and deaths are the highest-stakes, most hallucination-prone category (an
exact year is either right or it costs a point), so they never touch the LLM.
They come straight from Wikimedia's public On-this-day REST feed, one call per
covered day, with the citing article URL kept on every fact.

Endpoint (no API key; a descriptive User-Agent is required):
    https://en.wikipedia.org/api/rest_v1/feed/onthisday/{births|deaths}/{MM}/{DD}
"""

from __future__ import annotations

from datetime import date

import requests

from ..provenance import Fact, Source
from ..week import WeekRange

API = "https://en.wikipedia.org/api/rest_v1/feed/onthisday"
# Wikimedia asks for a real UA that identifies the app and a contact.
USER_AGENT = "HumanitysLastQuiz/0.1 (https://github.com/temataro/humanitys-last-quiz; tal@kamar.com)"
LICENSE = "CC BY-SA 4.0"

# Per-day and per-section caps keep an edition to a readable, quiz-sized handful
# rather than the dozens the feed returns for every date.
PER_DAY = 4
SECTION_CAP = 10


def _get(kind: str, day: date, timeout: float) -> list[dict]:
    url = f"{API}/{kind}/{day.month:02d}/{day.day:02d}"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=timeout)
    resp.raise_for_status()
    return resp.json().get(kind, [])


def _page_url(entry: dict) -> str:
    pages = entry.get("pages") or []
    if not pages:
        return ""
    return (pages[0].get("content_urls", {}).get("desktop", {}).get("page")) or ""


def _who(entry: dict) -> str:
    pages = entry.get("pages") or []
    if pages:
        titles = pages[0].get("titles") or {}
        return titles.get("normalized") or pages[0].get("normalizedtitle") or ""
    return ""


def _what(entry: dict, who: str) -> str:
    """The description, with the leading name stripped so it isn't shown twice."""
    text = (entry.get("text") or "").strip()
    if who and text.lower().startswith(who.lower()):
        text = text[len(who):].lstrip(" ,–—-")
    return text


def _collect(kind: str, week: WeekRange, retrieved_at: str, timeout: float) -> list[Fact]:
    facts: list[Fact] = []
    seen: set[str] = set()  # dedupe the same person recurring across the window
    for day in week.dates():
        try:
            entries = _get(kind, day, timeout)
        except requests.RequestException as exc:  # resilient: skip a bad day, keep going
            print(f"  [wikipedia] {kind} {day:%m-%d} failed: {exc}")
            continue
        taken = 0
        for entry in entries:
            if taken >= PER_DAY or len(facts) >= SECTION_CAP:
                break
            who = _who(entry)
            year = entry.get("year")
            if not who or year is None or who in seen:
                continue
            seen.add(who)
            taken += 1
            facts.append(
                Fact(
                    value={"year": year, "who": who, "what": _what(entry, who), "on": day.isoformat()},
                    source=Source("Wikipedia", _page_url(entry), LICENSE),
                    retrieved_at=retrieved_at,
                )
            )
        if len(facts) >= SECTION_CAP:
            break
    facts.sort(key=lambda f: f.value["year"])
    return facts


def collect(week: WeekRange, retrieved_at: str, timeout: float = 15.0) -> dict[str, list[Fact]]:
    """Return ``{"births": [...], "deaths": [...]}`` for the covered week."""
    return {
        "births": _collect("births", week, retrieved_at, timeout),
        "deaths": _collect("deaths", week, retrieved_at, timeout),
    }
