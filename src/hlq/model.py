"""The Edition data model — the source of truth for one week.

An ``Edition`` serialises to ``data/weeks/<week_id>.json`` (the committed,
provenance-tracked archive) and is what the templates render. Every section is a
list of :class:`~hlq.provenance.Fact`, so the footer's source credits can be
derived (``sources()``) instead of hand-maintained.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .provenance import Fact, Source, dedupe_sources

# Sections that are plain lists of facts, in render order. Kept in one place so
# to_dict/from_dict/all_facts stay in sync as sections are added.
FACT_SECTIONS = (
    "births",
    "deaths",
    "charts",
    "box_office",
    "top_list",
    "trivia",
    "geography",
    "chart_history",
)


@dataclass
class Edition:
    week_id: str
    edition_no: int
    sunday: str          # ISO date, e.g. "2026-07-26"
    range_start: str
    range_end: str
    range_label: str     # "20 – 26 July 2026"
    generated_at: str    # ISO-8601 UTC

    # Free-text scalars (the LLM may rewrite these; sensible defaults otherwise).
    standfirst: str = ""      # the Quizmaster's Note
    top_list_title: str = ""  # heading for the List of the Day
    banker: str = ""          # the derived "#1 artist" one-liner

    # True when the web-search categories are unverified sample data (no API key
    # at build time). The template surfaces this so a placeholder edition is
    # never mistaken for a real one.
    placeholder: bool = False

    # Fact sections (see FACT_SECTIONS).
    births: list[Fact] = field(default_factory=list)
    deaths: list[Fact] = field(default_factory=list)
    charts: list[Fact] = field(default_factory=list)
    box_office: list[Fact] = field(default_factory=list)
    top_list: list[Fact] = field(default_factory=list)
    trivia: list[Fact] = field(default_factory=list)
    geography: list[Fact] = field(default_factory=list)
    chart_history: list[Fact] = field(default_factory=list)

    def all_facts(self) -> list[Fact]:
        out: list[Fact] = []
        for name in FACT_SECTIONS:
            out.extend(getattr(self, name))
        return out

    def sources(self) -> list[Source]:
        """Footer-ready, de-duplicated credits for everything actually used."""
        return dedupe_sources(self.all_facts())

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "week_id": self.week_id,
            "edition_no": self.edition_no,
            "sunday": self.sunday,
            "range_start": self.range_start,
            "range_end": self.range_end,
            "range_label": self.range_label,
            "generated_at": self.generated_at,
            "standfirst": self.standfirst,
            "top_list_title": self.top_list_title,
            "banker": self.banker,
            "placeholder": self.placeholder,
        }
        for name in FACT_SECTIONS:
            d[name] = [f.to_dict() for f in getattr(self, name)]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Edition":
        kwargs: dict[str, Any] = {
            "week_id": d["week_id"],
            "edition_no": d["edition_no"],
            "sunday": d["sunday"],
            "range_start": d["range_start"],
            "range_end": d["range_end"],
            "range_label": d["range_label"],
            "generated_at": d["generated_at"],
            "standfirst": d.get("standfirst", ""),
            "top_list_title": d.get("top_list_title", ""),
            "banker": d.get("banker", ""),
            "placeholder": d.get("placeholder", False),
        }
        for name in FACT_SECTIONS:
            kwargs[name] = [Fact.from_dict(x) for x in d.get(name, [])]
        return cls(**kwargs)
