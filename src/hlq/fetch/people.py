# =============================================================================
# people.py — Curate sourced people and research cultural dates.
#
# Part of Humanity's Last Quiz; see ARCHITECTURE.md for the data flow.
#
# Copyright (c) 2026 Temesgen Ataro <ataro.temesgen@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# =============================================================================

"""One bounded research call curates sourced people and the cultural calendar."""

import json
import os

from . import aggregate, wikipedia
from ..provenance import Fact
from ..utils import verify_excerpt


def collect(week, retrieved_at, candidates):
    start, end = wikipedia.window(week)[0], wikipedia.window(week)[-1]
    compact = {name: [f.value for f in facts] for name, facts in candidates.items()}
    prompt = f"""You curate a celebrity-focused pub trivia briefing for {start} to {end}, inclusive.
Today/retrieval date: {retrieved_at[:10]}. Publication Sunday: {week.sunday}.
Select recognisable entertainers, musicians and sportspeople first, with major writers,
scientists, political and historical figures too. Birthdays must span different eras.
Candidates below have dates from Wikipedia; select by exact who string only.
Do not invent people, dates or deaths. Deaths are actual recent deaths, not anniversaries.
Choose up to 16 birthdays, covering as many of the eleven days as possible, and up to
10 deaths; omit obscure candidates. Return their exact who strings in births/deaths arrays.
Also use web search to find up to 8 cultural events, holidays or celebrations occurring
in the same date window in the publication year. Include a global mix. Verify movable
holidays for that YEAR against organisers, national calendars or religious authorities.
Use the date the celebration occurs, not article publication dates. Do not guess dates.
Include ongoing festivals only with an actual occurrence date within the window.
Each event needs a specific source_url and a verbatim evidence quote of at least five words supporting its date.
Return only JSON:
{{"births": ["exact candidate name"], "deaths": ["exact candidate name"],
"events": [{{"name": "", "on": "YYYY-MM-DD", "where": "", "what": "one useful quiz fact",
"source_url": "https://...", "evidence": "short excerpt confirming the date"}}]}}
Candidates:
{json.dumps(compact, ensure_ascii=False)}"""
    raw, grounding, model = "", {}, "deterministic"
    result = {}
    name = os.environ.get("HLQ_AGGREGATOR", aggregate.DEFAULT_PROVIDER).lower()
    provider = aggregate.LLM_PROVIDERS.get(name)
    if provider and provider.has_key():
        try:
            raw, grounding, model = provider.call(prompt, 120)
            result = aggregate._extract_json(raw)
        except Exception as exc:
            print(
                f"  [people] research unavailable: {type(exc).__name__}: {str(exc)[:120]}"
            )
    selected = {}
    for section in ("births", "deaths"):
        facts = candidates[section]
        if section in result:
            names = set(result[section])
            selected[section] = [f for f in facts if f.value["who"] in names]
        else:
            selected[section] = facts if section == "births" else facts[:10]
        selected[section].sort(key=lambda f: (f.value["on"], f.value["year"]))
    selected["events"] = []
    for event in result.get("events", [])[:8]:
        if not (str(start) <= event.get("on", "") <= str(end)):
            continue
        source = aggregate._source(event.get("source_url", ""))
        if not source.url or not event.get("evidence") or not event.get("name"):
            continue
        if not verify_excerpt(source.url, event["evidence"]):
            print(f"  [calendar] omitted unverifiable date: {event['name']}")
            continue
        selected["events"].append(Fact(event, source, retrieved_at))
    selected["events"].sort(key=lambda f: f.value["on"])
    selected["audit"] = {
        "model": model,
        "prompt": prompt,
        "response": raw,
        "grounding": grounding,
        "candidate_counts": {k: len(v) for k, v in candidates.items()},
    }
    return selected
