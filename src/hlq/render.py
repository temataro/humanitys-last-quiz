# =============================================================================
# render.py — Render editions, calendars, portraits, and map rounds.
#
# Part of Humanity's Last Quiz; see ARCHITECTURE.md for the data flow.
#
# Copyright (c) 2026 Temesgen Ataro <ataro.temesgen@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# =============================================================================

"""Render the static site from the committed week archive.

Reads every ``data/weeks/*.json`` and writes a flat set of pages into ``site/``:
one ``<week_id>.html`` per edition, ``index.html`` (the latest), and
``archive.html`` (the tab for scrolling older weeks). Flat output keeps every
inter-page link simple — just ``<week_id>.html``.
"""

from __future__ import annotations

import json
import re
import shutil
from markupsafe import Markup, escape
from datetime import date, datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import paths
from .model import Edition
from .geography import regional_round
from .provenance import Source

FACT_COUNT_SECTIONS = (
    "births",
    "deaths",
    "charts",
    "box_office",
    "top_list",
    "trivia",
    "geography",
    "events",
)


def emphasize(text, edition, portraits=True):
    names = set(edition.portraits) | set(edition.proper_nouns)
    for fact in edition.births + edition.deaths:
        names.add(fact.value["who"])
        names.update(fact.value.get("proper_nouns", []))
    for fact in edition.charts:
        names.update([fact.value.get("title", ""), fact.value.get("artist", "")])
    for fact in edition.box_office:
        names.add(fact.value.get("title", ""))
    for fact in edition.events:
        names.add(fact.value.get("name", ""))
    # Match collaborators individually so one combined artist label cannot hide
    # the portraits of its individual performers.
    for fact in edition.charts:
        artist = fact.value.get("artist", "")
        if any(name != artist and name in artist for name in edition.portraits):
            names.discard(artist)
    # Longest first avoids partial matches; boundaries avoid e.g. 'Us' in 'music'.
    names.discard("")
    if not names:
        return escape(text)
    pattern = re.compile(
        r"(?<!\w)("
        + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        + r")(?!\w)"
    )
    output, start = [], 0
    for match in pattern.finditer(str(text)):
        output.append(str(escape(str(text)[start : match.start()])))
        name = match.group()
        portrait = edition.portraits.get(name) if portraits else None
        if portrait:
            output.append(
                f'<button class="portrait" type="button" data-image="{escape(portrait.get("large_url") or portrait["url"])}" '
                f'data-name="{escape(name)}" data-credit="{escape(portrait["credit"])}" '
                f'data-source="{escape(portrait["page_url"])}" aria-label="Enlarge portrait of {escape(name)}">'
                f'<img src="{escape(portrait["url"])}" alt="{escape(name)}" width="48" height="48" loading="lazy"></button>'
            )
        output.append(f"<strong>{escape(name)}</strong>")
        start = match.end()
    output.append(str(escape(str(text)[start:])))
    return Markup("".join(output))


def _pub_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%A, %-d %B %Y")


def _write_status(editions: list[Edition]) -> None:
    """Snapshot of the last successful build — read by the footer heartbeat widget."""
    latest = editions[0]
    status = {
        "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "week_id": latest.week_id,
        "edition_no": latest.edition_no,
        "generated_at": latest.generated_at,  # when the latest edition was built
        "mode": "placeholder" if latest.placeholder else "live",
        "editions": len(editions),
        "counts": {name: len(getattr(latest, name)) for name in FACT_COUNT_SECTIONS},
        "sources": [s.name for s in latest.sources()],
    }
    (paths.SITE / "status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _uses_tmdb(sources: list[Source]) -> bool:
    return any(
        "tmdb" in (s.name + s.url).lower() or "themoviedb" in s.url.lower()
        for s in sources
    )


def _load_editions() -> list[Edition]:
    files = sorted(paths.WEEKS.glob("*.json"))
    editions = [
        Edition.from_dict(json.loads(f.read_text(encoding="utf-8"))) for f in files
    ]
    # Newest first — week_id sorts chronologically (YYYY-Www).
    editions.sort(key=lambda e: e.week_id, reverse=True)
    return editions


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(paths.TEMPLATES)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render() -> int:
    editions = _load_editions()
    if not editions:
        print("No editions in data/weeks/ — run `make week` first.")
        return 0

    env = _env()
    env.filters["emphasize"] = emphasize
    calendar_tmpl = env.get_template("calendar.html.j2")
    edition_tmpl = env.get_template("edition.html.j2")
    archive_tmpl = env.get_template("archive.html.j2")
    paths.SITE.mkdir(parents=True, exist_ok=True)
    if (paths.DATA / "media").exists():
        shutil.copytree(
            paths.DATA / "media",
            paths.SITE / "media",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("*.json"),
        )

    # editions[0] is newest. "next" = newer (toward index), "prev" = older.
    for i, ed in enumerate(editions):
        newer = editions[i - 1].week_id if i > 0 else None
        older = editions[i + 1].week_id if i + 1 < len(editions) else None
        srcs = ed.sources()
        calendar_html = calendar_tmpl.render(edition=ed, is_latest=(i == 0))
        (paths.SITE / f"{ed.week_id}-calendar.html").write_text(
            calendar_html, encoding="utf-8"
        )
        if i == 0:
            (paths.SITE / "calendar.html").write_text(calendar_html, encoding="utf-8")
        html = edition_tmpl.render(
            edition=ed,
            map_round=regional_round(ed.edition_no),
            sources=srcs,
            pub_date=_pub_date(ed.sunday),
            uses_tmdb=_uses_tmdb(srcs),
            newer_id=newer,
            older_id=older,
            is_latest=(i == 0),
        )
        (paths.SITE / f"{ed.week_id}.html").write_text(html, encoding="utf-8")

    # index.html mirrors the latest edition.
    latest = editions[0]
    latest_srcs = latest.sources()
    index_html = edition_tmpl.render(
        edition=latest,
        map_round=regional_round(latest.edition_no),
        sources=latest_srcs,
        pub_date=_pub_date(latest.sunday),
        uses_tmdb=_uses_tmdb(latest_srcs),
        newer_id=None,
        older_id=editions[1].week_id if len(editions) > 1 else None,
        is_latest=True,
    )
    (paths.SITE / "index.html").write_text(index_html, encoding="utf-8")

    (paths.SITE / "archive.html").write_text(
        archive_tmpl.render(editions=editions), encoding="utf-8"
    )

    _write_status(editions)
    (paths.SITE / ".nojekyll").write_text(
        "", encoding="utf-8"
    )  # serve files as-is on Pages

    print(
        f"Rendered {len(editions)} edition(s) → {paths.SITE.relative_to(paths.ROOT)}/"
    )
    print(f"  latest: {latest.week_id} (edition {latest.edition_no})")
    return len(editions)
