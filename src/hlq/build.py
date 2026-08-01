"""Build one week's edition: fetch every source, assemble, persist.

Output is ``data/weeks/<week_id>.json`` (the committed, provenance-tracked
archive) plus ``data/raw/<week_id>.md`` (the LLM prompt+response, for audit).
Rendering is a separate step (:mod:`hlq.render`) so the site can be regenerated
from the archive without re-fetching.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from . import paths
from .fetch import aggregate, wikipedia
from .model import Edition
from .week import WeekRange

DEFAULT_TOP_LIST_TITLE = "The list of the day"
DEFAULT_STANDFIRST = (
    "Everything below is drawn fresh from the public record — births and deaths "
    "from Wikipedia's day-pages, the charts and box office from the week just gone."
)


def build_week(week: WeekRange) -> Edition:
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Building {week.week_id} (edition {week.edition_no}) — {week.label()}")

    print("- Wikipedia births & deaths…")
    wiki = wikipedia.collect(week, retrieved_at)
    print(f"    {len(wiki['births'])} births, {len(wiki['deaths'])} deaths")

    print("- Free-source aggregation (charts, trivia, lists, geography)…")
    agg = aggregate.aggregate(week, retrieved_at)
    print(f"    {'PLACEHOLDER' if agg.placeholder else agg.model}: "
          f"{len(agg.charts)} charts, {len(agg.top_list)} top-list, "
          f"{len(agg.trivia)} trivia, {len(agg.geography)} geography")

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
        births=wiki["births"],
        deaths=wiki["deaths"],
        charts=agg.charts,
        box_office=agg.box_office,
        top_list=agg.top_list,
        trivia=agg.trivia,
        geography=agg.geography,
        chart_history=agg.chart_history,
    )
    _persist(edition, agg)
    return edition


def _persist(edition: Edition, agg: aggregate.Aggregation) -> None:
    paths.WEEKS.mkdir(parents=True, exist_ok=True)
    paths.RAW.mkdir(parents=True, exist_ok=True)

    out = paths.WEEKS / f"{edition.week_id}.json"
    out.write_text(json.dumps(edition.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"- Wrote {out.relative_to(paths.ROOT)}")

    raw = paths.RAW / f"{edition.week_id}.md"
    raw.write_text(
        f"# {edition.week_id} raw aggregation\n\n"
        f"model: {agg.model or 'placeholder'}\n"
        f"generated_at: {edition.generated_at}\n\n"
        f"## Prompt\n\n{agg.raw_prompt}\n\n## Response\n\n{agg.raw_response}\n",
        encoding="utf-8",
    )


def run(sunday: date | None) -> Edition:
    week = WeekRange.for_sunday(sunday) if sunday else WeekRange.most_recent(date.today())
    return build_week(week)
