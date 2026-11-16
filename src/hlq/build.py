# =============================================================================
# build.py — Assemble and persist a sourced weekly edition.
#
# Part of Humanity's Last Quiz; see ARCHITECTURE.md for the data flow.
#
# Copyright (c) 2026 Temesgen Ataro <ataro.temesgen@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# =============================================================================

"""Build one week's edition: fetch every source, assemble, persist.

Output is ``data/weeks/<week_id>.json`` (the committed, provenance-tracked
archive) plus ``data/raw/<week_id>.md`` (the LLM prompt+response, for audit).
Rendering is a separate step (:mod:`hlq.render`) so the site can be regenerated
from the archive without re-fetching.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone

from . import paths
from .fetch import aggregate, wikipedia, people, portraits
from .model import Edition
from .week import WeekRange

DEFAULT_TOP_LIST_TITLE = "The list of the day"
DEFAULT_STANDFIRST = "A fresh selection of sourced facts for the next quiz night."


def build_week(week: WeekRange) -> Edition:
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Building {week.week_id} (edition {week.edition_no}) — {week.label()}")

    print("- Wikipedia births & deaths…")
    wiki = wikipedia.collect(week, retrieved_at)
    print(f"    {len(wiki['births'])} births, {len(wiki['deaths'])} deaths")

    curated = people.collect(week, retrieved_at, wiki)

    print(
        "- Aggregating charts/trivia/lists/geography (LLM if configured, else free sources)…"
    )
    agg = aggregate.aggregate(week, retrieved_at)
    print(
        f"    {'PLACEHOLDER' if agg.placeholder else agg.model}: "
        f"{len(agg.charts)} charts, {len(agg.top_list)} top-list, "
        f"{len(agg.trivia)} trivia, {len(agg.geography)} geography"
    )

    edition = Edition(
        week_id=week.week_id,
        edition_no=week.edition_no,
        sunday=week.sunday.isoformat(),
        range_start=week.start.isoformat(),
        range_end=week.end.isoformat(),
        range_label=week.label(),
        generated_at=retrieved_at,
        standfirst=agg.standfirst or DEFAULT_STANDFIRST,
        top_list_title=agg.top_list_title or DEFAULT_TOP_LIST_TITLE,
        banker=agg.banker,
        placeholder=agg.placeholder,
        births=curated["births"],
        deaths=curated["deaths"],
        charts=agg.charts,
        box_office=agg.box_office,
        top_list=agg.top_list,
        trivia=agg.trivia,
        geography=agg.geography,
        events=curated["events"],
        proper_nouns=agg.proper_nouns + [p["name"] for p in agg.people],
        people_window=f"{wikipedia.window(week)[0]:%-d %B %Y} – {wikipedia.window(week)[-1]:%-d %B %Y}",
    )
    identities = [
        {"name": f.value["who"], "wikipedia_title": f.value["who"]}
        for f in edition.births + edition.deaths
    ]
    identities.extend(
        {"name": f.value["artist"], "wikipedia_title": f.value["artist"]}
        for f in edition.charts
        if f.value.get("artist")
    )
    identities.extend(agg.people)
    edition.portraits = portraits.collect(identities)
    _persist(edition, agg, curated["audit"])
    return edition


def _persist(edition: Edition, agg: aggregate.Aggregation, people_audit=None) -> None:
    paths.WEEKS.mkdir(parents=True, exist_ok=True)
    paths.RAW.mkdir(parents=True, exist_ok=True)

    audit = {
        "aggregation": {"model": agg.model, "grounding": agg.grounding},
        "people_calendar": people_audit or {},
        "accepted": {
            name: len(getattr(edition, name))
            for name in ("births", "deaths", "charts", "events")
        },
        "portraits": len(edition.portraits),
    }
    (paths.RAW / f"{edition.week_id}.audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    raw = paths.RAW / f"{edition.week_id}.md"
    raw.write_text(
        f"# {edition.week_id} raw aggregation\n\n"
        f"model: {agg.model or 'placeholder'}\n"
        f"generated_at: {edition.generated_at}\n\n"
        f"## Prompt\n\n{agg.raw_prompt}\n\n## Response\n\n{agg.raw_response}\n",
        encoding="utf-8",
    )

    if os.environ.get("HLQ_REQUIRE_RESEARCH"):
        assert (
            edition.events
        ), "No verified cultural dates; keeping the previous published edition."
        assert (
            edition.charts
        ), "No verified charts; keeping the previous published edition."
        assert (
            not edition.placeholder
        ), "Placeholder data cannot replace the published edition."

    out = paths.WEEKS / f"{edition.week_id}.json"
    out.write_text(
        json.dumps(edition.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"- Wrote {out.relative_to(paths.ROOT)}")


def run(sunday: date | None) -> Edition:
    week = (
        WeekRange.for_sunday(sunday) if sunday else WeekRange.most_recent(date.today())
    )
    return build_week(week)
