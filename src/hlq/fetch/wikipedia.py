# =============================================================================
# wikipedia.py — Source and rank dated birthday and recent-death candidates.
#
# Part of Humanity's Last Quiz; see ARCHITECTURE.md for the data flow.
#
# Copyright (c) 2026 Temesgen Ataro <ataro.temesgen@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# =============================================================================

"""Source birthdays across eras and actual recent deaths around publication Sunday."""

from datetime import date, timedelta
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from ..provenance import Fact, Source
from ..utils import get_json

API = "https://en.wikipedia.org/w/api.php"
FEED = "https://en.wikipedia.org/api/rest_v1/feed/onthisday"
LICENSE = "CC BY-SA 4.0"


def window(week):
    return [week.sunday + timedelta(days=i) for i in range(-5, 6)]


def query(**params):
    return get_json(
        API, {"action": "query", "format": "json", "formatversion": 2, **params}
    )


def birthdays(week, retrieved_at):
    facts = {}
    for day in window(week):
        try:
            entries = get_json(f"{FEED}/births/{day:%m/%d}").get("births", [])
        except requests.RequestException as exc:
            print(f"  [wikipedia] birthdays {day}: {exc}")
            continue
        for entry in entries:
            pages = entry.get("pages") or []
            if not pages or entry.get("year") is None:
                continue
            page = pages[0]
            who = page.get("titles", {}).get("normalized", "")
            url = page.get("content_urls", {}).get("desktop", {}).get("page", "")
            if not who or not url:
                continue
            text = entry.get("text", "")
            if text.casefold().startswith(who.casefold()):
                text = text[len(who) :].lstrip(" ,–—-")
            facts[who] = Fact(
                {
                    "year": entry["year"],
                    "who": who,
                    "what": text,
                    "on": day.isoformat(),
                },
                Source("Wikipedia", url, LICENSE),
                retrieved_at,
            )
    return list(facts.values())


def parse_deaths(html, month, allowed, retrieved_at):
    """Parse day lists in monthly pages or redirects to the current year page."""
    soup = BeautifulSoup(html, "html.parser")
    active_month = month.month
    current = None
    facts = []
    # Headings can be wrapped in .mw-heading; walking document order also handles
    # older unwrapped markup. Only direct list entries with a biography link count.
    for node in soup.find_all(["h2", "h3", "h4", "li"]):
        if node.name == "h2":
            heading = node.get_text(" ", strip=True).split("[")[0].strip()
            if heading in [date(2000, i, 1).strftime("%B") for i in range(1, 13)]:
                active_month = next(
                    i
                    for i in range(1, 13)
                    if date(2000, i, 1).strftime("%B") == heading
                )
            current = None
        elif node.name in {"h3", "h4"}:
            heading = node.get_text(" ", strip=True).split("[")[0].strip()
            current = (
                date(month.year, active_month, int(heading))
                if heading.isdigit() and 1 <= int(heading) <= 31
                else None
            )
        elif current in allowed and not node.find_parent("li"):
            link = node.find("a")
            if (
                not link
                or not link.get("href", "").startswith("/wiki/")
                or "new" in link.get("class", [])
            ):
                continue
            for ref in node.select("sup.reference"):
                ref.decompose()
            who = link.get("title") or unquote(link["href"].split("/wiki/")[1]).replace(
                "_", " "
            )
            facts.append(
                Fact(
                    {
                        "year": current.year,
                        "who": who,
                        "what": node.get_text(" ", strip=True)
                        .removeprefix(link.get_text())
                        .lstrip(" ,"),
                        "on": current.isoformat(),
                    },
                    Source(
                        "Wikipedia recent deaths",
                        f"https://en.wikipedia.org/wiki/Deaths_in_{month:%B_%Y}#{current.day}",
                        LICENSE,
                    ),
                    retrieved_at,
                )
            )
    return facts


def deaths(week, retrieved_at):
    # Never confuse a historical anniversary or an upcoming date with a death.
    cutoff = min(date.fromisoformat(retrieved_at[:10]), date.today())
    allowed = {day for day in window(week) if day <= cutoff}
    facts = []
    for month in sorted({day.replace(day=1) for day in allowed}):
        try:
            data = get_json(
                API,
                {
                    "action": "parse",
                    "page": f"Deaths_in_{month:%B_%Y}",
                    "redirects": 1,
                    "prop": "text",
                    "format": "json",
                    "formatversion": 2,
                },
            )
            facts.extend(
                parse_deaths(
                    data.get("parse", {}).get("text", ""), month, allowed, retrieved_at
                )
            )
        except requests.RequestException as exc:
            print(f"  [wikipedia] recent deaths {month:%B %Y}: {exc}")
    return list({f.value["who"]: f for f in facts}.values())


def ranked(facts):
    """Pageviews are a recognisability signal, never a date or identity source."""
    scores = {}
    names = [f.value["who"] for f in facts]
    for start in range(0, len(names), 50):
        try:
            continuation = {}
            while True:
                result = query(
                    prop="pageviews",
                    titles="|".join(names[start : start + 50]),
                    pvipdays=30,
                    **continuation,
                )
                for page in result.get("query", {}).get("pages", []):
                    if page.get("pageviews"):
                        scores[page["title"]] = sum(
                            n or 0 for n in page["pageviews"].values()
                        )
                continuation = result.get("continue")
                if not continuation:
                    break
        except requests.RequestException as exc:
            print(f"  [wikipedia] popularity unavailable: {exc}")
    return sorted(facts, key=lambda f: scores.get(f.value["who"], 0), reverse=True)


def collect(week, retrieved_at):
    ordered = ranked(birthdays(week, retrieved_at))
    # Present candidates from EVERY day before filling remaining slots by interest.
    candidates = []
    for day in window(week):
        candidates.extend([f for f in ordered if f.value["on"] == day.isoformat()][:2])
    return {"births": candidates, "deaths": ranked(deaths(week, retrieved_at))[:20]}
