"""Render the static site from the committed week archive.

Reads every ``data/weeks/*.json`` and writes a flat set of pages into ``site/``:
one ``<week_id>.html`` per edition, ``index.html`` (the latest), and
``archive.html`` (the tab for scrolling older weeks). Flat output keeps every
inter-page link simple — just ``<week_id>.html``.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import paths
from .model import Edition
from .provenance import Source

FACT_COUNT_SECTIONS = (
    "births", "deaths", "charts", "box_office",
    "top_list", "trivia", "geography", "chart_history",
)


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
        "generated_at": latest.generated_at,   # when the latest edition was built
        "mode": "placeholder" if latest.placeholder else "live",
        "editions": len(editions),
        "counts": {name: len(getattr(latest, name)) for name in FACT_COUNT_SECTIONS},
        "sources": [s.name for s in latest.sources()],
    }
    (paths.SITE / "status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _uses_tmdb(sources: list[Source]) -> bool:
    return any("tmdb" in (s.name + s.url).lower() or "themoviedb" in s.url.lower() for s in sources)


def _load_editions() -> list[Edition]:
    files = sorted(paths.WEEKS.glob("*.json"))
    editions = [Edition.from_dict(json.loads(f.read_text(encoding="utf-8"))) for f in files]
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
    edition_tmpl = env.get_template("edition.html.j2")
    archive_tmpl = env.get_template("archive.html.j2")
    paths.SITE.mkdir(parents=True, exist_ok=True)

    # editions[0] is newest. "next" = newer (toward index), "prev" = older.
    for i, ed in enumerate(editions):
        newer = editions[i - 1].week_id if i > 0 else None
        older = editions[i + 1].week_id if i + 1 < len(editions) else None
        srcs = ed.sources()
        html = edition_tmpl.render(
            edition=ed,
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

    print(f"Rendered {len(editions)} edition(s) → {paths.SITE.relative_to(paths.ROOT)}/")
    print(f"  latest: {latest.week_id} (edition {latest.edition_no})")
    return len(editions)
