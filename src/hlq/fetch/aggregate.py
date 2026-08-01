"""Weekly aggregation — Gemini primary, free sources as fallback, then placeholder.

The non-Wikipedia categories (charts, box office, Top-10, trivia, geography) are
filled by, in order:

  1. an LLM provider with web search — default Gemini (`HLQ_AGGREGATOR`, needs a
     billing-enabled key; one grounded prompt/week, JSON with a source_url per
     fact). See `gemini.py` / `groq.py`.
  2. free, keyless data sources if the LLM is unavailable/errors — Open Trivia DB,
     Billboard Hot 100, World Bank. Robust and authoritative; a dead source just
     leaves its section empty.
  3. clearly-labelled placeholder data only if everything above fails.

So main produces real editions even before a key is added (via the free
fallback), and upgrades to grounded LLM coverage once the key is in. The pure
free-source pipeline lives, unmixed, on the `no-llm-provenance` branch.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from importlib import resources
from urllib.parse import urlparse

from ..provenance import Fact, Source
from ..week import WeekRange
from . import billboard, gemini, groq, opentdb, worldbank

LLM_PROVIDERS = {"gemini": gemini, "groq": groq}
DEFAULT_PROVIDER = "gemini"
GENERIC_SOURCE = "web search"
# HLQ_AGGREGATOR values that skip the LLM and go straight to free sources.
FREE_ONLY = {"free", "none", "sources", "free-sources"}


@dataclass
class Aggregation:
    """The non-Wikipedia sections plus the raw exchange / source log (archived)."""

    standfirst: str = ""
    banker: str = ""
    top_list_title: str = ""
    placeholder: bool = False
    model: str = ""
    raw_prompt: str = ""
    raw_response: str = ""
    charts: list[Fact] = field(default_factory=list)
    box_office: list[Fact] = field(default_factory=list)
    top_list: list[Fact] = field(default_factory=list)
    trivia: list[Fact] = field(default_factory=list)
    geography: list[Fact] = field(default_factory=list)
    chart_history: list[Fact] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# LLM path
# --------------------------------------------------------------------------- #
def _load_prompt(week: WeekRange) -> str:
    tmpl = resources.files("hlq.prompts").joinpath("aggregate.md").read_text(encoding="utf-8")
    # Plain replace, not str.format — the prompt is full of literal JSON braces.
    return (
        tmpl.replace("{range_label}", week.label())
        .replace("{range_start}", week.start.isoformat())
        .replace("{range_end}", week.end.isoformat())
    )


def _host(url: str) -> str:
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _source(url: str, grounding: list[str], name_hint: str = "") -> Source:
    url = (url or "").strip()
    if not url and grounding:
        url = grounding[0]
    return Source(name=name_hint or _host(url) or GENERIC_SOURCE, url=url, license="")


def _extract_json(text: str) -> dict:
    """Best-effort parse: raw JSON, a ```json fence, or the first {...} block."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError("no JSON object found in model response")


def _to_facts(data: dict, retrieved_at: str, grounding: list[str]) -> Aggregation:
    def src(item: dict) -> Source:
        return _source(item.get("source_url", ""), grounding)

    agg = Aggregation(
        standfirst=data.get("standfirst", ""),
        banker=data.get("banker", ""),
        top_list_title=data.get("top_list_title", ""),
    )
    for c in data.get("charts", []):
        agg.charts.append(Fact(
            {"territory": c.get("territory", ""), "chart": c.get("chart", ""),
             "title": c.get("title", ""), "artist": c.get("artist", "")}, src(c), retrieved_at))
    for b in data.get("box_office", []):
        agg.box_office.append(Fact(
            {"region": b.get("region", ""), "title": b.get("title", ""), "note": b.get("note", "")},
            src(b), retrieved_at))
    list_src = _source(data.get("top_list_source_url", ""), grounding)
    for it in data.get("top_list", []):
        agg.top_list.append(Fact(
            {"label": it.get("label", ""), "value": it.get("value", "")}, list_src, retrieved_at))
    for t in data.get("trivia", []):
        agg.trivia.append(Fact({"q": t.get("q", ""), "a": t.get("a", "")}, src(t), retrieved_at))
    for g in data.get("geography", []):
        agg.geography.append(Fact({"fact": g.get("fact", "")}, src(g), retrieved_at))
    for h in data.get("chart_history", []):
        agg.chart_history.append(Fact(
            {"year": h.get("year", 0), "territory": h.get("territory", ""),
             "title": h.get("title", ""), "artist": h.get("artist", "")}, src(h), retrieved_at))
    return agg


def _try_llm(name, provider, week: WeekRange, retrieved_at: str, timeout: float) -> Aggregation | None:
    prompt = _load_prompt(week)
    try:
        raw, grounding, model = provider.call(prompt, timeout)
        agg = _to_facts(_extract_json(raw), retrieved_at, grounding)
        agg.model = f"{name}:{model}"
        agg.raw_prompt = prompt
        agg.raw_response = raw
        print(f"  [aggregate] {name} ok ({model})")
        return agg
    except Exception as exc:
        print(f"  [aggregate] {name} failed ({type(exc).__name__}: {str(exc)[:120]}); "
              f"falling back to free sources")
        return None


# --------------------------------------------------------------------------- #
# Free-source path
# --------------------------------------------------------------------------- #
def _free_sources(week: WeekRange, retrieved_at: str, timeout: float) -> Aggregation:
    agg = Aggregation(model="free-sources")
    log: list[str] = []

    def _try(name: str, fn):
        try:
            fn()
            log.append(f"{name}: ok")
        except Exception as exc:  # one dead source must not sink the edition
            log.append(f"{name}: FAILED ({type(exc).__name__}: {str(exc)[:100]})")
            print(f"  [aggregate] {name} failed: {type(exc).__name__}: {str(exc)[:100]}")

    _try("opentdb", lambda: setattr(agg, "trivia", opentdb.collect(retrieved_at, timeout=timeout)))

    def _charts():
        b = billboard.collect(retrieved_at, timeout=timeout)
        agg.charts, agg.banker = b["charts"], b["banker"]

    def _worldbank():
        w = worldbank.collect(week, retrieved_at, timeout=timeout)
        agg.top_list, agg.top_list_title, agg.geography = w["top_list"], w["top_list_title"], w["geography"]

    _try("billboard", _charts)
    _try("worldbank", _worldbank)
    agg.raw_response = "free-source aggregation\n" + "\n".join(log)
    return agg


def _has_data(agg: Aggregation) -> bool:
    return bool(agg.trivia or agg.charts or agg.top_list or agg.geography or agg.box_office)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def aggregate(week: WeekRange, retrieved_at: str, timeout: float = 60.0) -> Aggregation:
    name = os.environ.get("HLQ_AGGREGATOR", DEFAULT_PROVIDER).lower()

    if name not in FREE_ONLY:
        provider = LLM_PROVIDERS.get(name)
        if provider is None:
            print(f"  [aggregate] unknown HLQ_AGGREGATOR={name!r}; using free sources")
        elif not provider.has_key():
            print(f"  [aggregate] no key for '{name}' — using free sources")
        else:
            agg = _try_llm(name, provider, week, retrieved_at, timeout)
            if agg is not None and _has_data(agg):
                return agg

    agg = _free_sources(week, retrieved_at, timeout)
    if _has_data(agg):
        return agg
    print("  [aggregate] every free source failed — using placeholder")
    return _placeholder(week, retrieved_at, agg.raw_response)


def _placeholder(week: WeekRange, retrieved_at: str, raw: str = "") -> Aggregation:
    """Sample data, flagged, used only when the LLM and every live source fail."""
    s = Source("Sample data", "", "")
    f = lambda v: Fact(v, s, retrieved_at)  # noqa: E731
    return Aggregation(
        placeholder=True,
        model="placeholder",
        raw_response=raw,
        standfirst=(
            "Sample edition — the LLM and every live data source were unavailable at "
            "build time, so the categories below are placeholder data for design review."
        ),
        banker="Placeholder: the safe #1-artist answer would be derived here.",
        top_list_title="Ten largest countries by land area",
        charts=[
            f({"territory": "US", "chart": "Billboard Hot 100", "title": "Birds of a Feather", "artist": "Billie Eilish"}),
        ],
        top_list=[
            f({"label": "Russia", "value": "16.38M km²"}),
            f({"label": "China", "value": "9.39M km²"}),
            f({"label": "United States", "value": "9.15M km²"}),
        ],
        trivia=[
            f({"q": "Which element has the chemical symbol W?", "a": "Tungsten"}),
            f({"q": "In which modern country lies the ancient city of Petra?", "a": "Jordan"}),
        ],
        geography=[
            f({"fact": "Vatican City is the smallest sovereign state, at just 0.49 km²."}),
        ],
    )
