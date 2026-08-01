"""Weekly aggregation from free, authoritative data sources (no LLM, no key).

After free-tier LLM web search proved unusable (Gemini grounding needs billing;
Groq Compound hits 413/TPM — see the project memo), the softer categories are
pulled straight from free structured sources, each fact keeping its citation:

    trivia      → Open Trivia DB        (opentdb.py)
    US charts   → Billboard Hot 100     (billboard.py)   + derived "banker"
    Top-10 list → World Bank            (worldbank.py, rotates weekly)
    geography   → World Bank            (worldbank.py, derived)

Births/deaths come from Wikipedia in build.py. Still stubbed (no clean free
source yet, so intentionally empty rather than faked): UK charts, Billboard 200
albums, box office, and the "on this date in the charts" history. Each section
fails independently — a dead source leaves its section empty, never crashing the
build. Only if *every* source fails do we fall back to full placeholder data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..provenance import Fact, Source
from ..week import WeekRange
from . import billboard, opentdb, worldbank


@dataclass
class Aggregation:
    """The non-Wikipedia sections plus a short provenance log (archived)."""

    standfirst: str = ""
    banker: str = ""
    top_list_title: str = ""
    placeholder: bool = False
    model: str = ""          # data-mode label, surfaced in the raw archive
    raw_prompt: str = ""
    raw_response: str = ""
    charts: list[Fact] = field(default_factory=list)
    box_office: list[Fact] = field(default_factory=list)
    top_list: list[Fact] = field(default_factory=list)
    trivia: list[Fact] = field(default_factory=list)
    geography: list[Fact] = field(default_factory=list)
    chart_history: list[Fact] = field(default_factory=list)


def aggregate(week: WeekRange, retrieved_at: str, timeout: float = 25.0) -> Aggregation:
    agg = Aggregation(model="free-sources")
    log: list[str] = []

    def _try(name: str, fn):
        try:
            fn()
            log.append(f"{name}: ok")
        except Exception as exc:  # one dead source must not sink the edition
            log.append(f"{name}: FAILED ({type(exc).__name__}: {str(exc)[:100]})")
            print(f"  [aggregate] {name} failed: {type(exc).__name__}: {str(exc)[:100]}")

    def _trivia():
        agg.trivia = opentdb.collect(retrieved_at, timeout=timeout)

    def _charts():
        b = billboard.collect(retrieved_at, timeout=timeout)
        agg.charts = b["charts"]
        agg.banker = b["banker"]

    def _worldbank():
        w = worldbank.collect(week, retrieved_at, timeout=timeout)
        agg.top_list = w["top_list"]
        agg.top_list_title = w["top_list_title"]
        agg.geography = w["geography"]

    _try("opentdb", _trivia)
    _try("billboard", _charts)
    _try("worldbank", _worldbank)

    agg.raw_response = "free-source aggregation\n" + "\n".join(log)

    got_any = bool(agg.trivia or agg.charts or agg.top_list or agg.geography)
    if not got_any:
        print("  [aggregate] every source failed — using labelled placeholder data")
        return _placeholder(week, retrieved_at, agg.raw_response)
    return agg


def _placeholder(week: WeekRange, retrieved_at: str, raw: str = "") -> Aggregation:
    """Sample data, flagged, used only when every live source fails."""
    s = Source("Sample data", "", "")
    f = lambda v: Fact(v, s, retrieved_at)  # noqa: E731
    return Aggregation(
        placeholder=True,
        model="placeholder",
        raw_response=raw,
        standfirst=(
            "Sample edition — every live data source was unreachable at build time, "
            "so the categories below are placeholder data for design review."
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
