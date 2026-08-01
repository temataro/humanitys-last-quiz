"""Charts — the current Billboard Hot 100 (free, no key).

Data from the public ``mhollingshead/billboard-hot-100`` dataset (daily JSON
mirror of Billboard's chart). We take the current #1 single as the US singles
chart row and derive the "banker" (safest #1-artist answer) from it.

Albums (Billboard 200) and the UK Official Charts have no equally-clean free
JSON source yet — see ``build.py`` stubs / PLAN.md. Adding them means finding a
comparable dataset or scraping officialcharts.com.
"""

from __future__ import annotations

import requests

from ..provenance import Fact, Source

RECENT = "https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main/recent.json"
SOURCE = Source("Billboard Hot 100", "https://www.billboard.com/charts/hot-100/", "")


def collect(retrieved_at: str, timeout: float = 20.0) -> dict:
    """Return ``{"charts": [Fact], "banker": str}`` for the current Hot 100 #1."""
    resp = requests.get(
        RECENT,
        headers={"User-Agent": "HumanitysLastQuiz/0.1 (tal@kamar.com)"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    rows = data.get("data") or []
    if not rows:
        raise RuntimeError("billboard dataset returned no rows")

    top = next((r for r in rows if r.get("rank") == 1), rows[0])
    song, artist = top.get("song", ""), top.get("artist", "")
    chart = Fact(
        value={"territory": "US", "chart": "Billboard Hot 100",
               "title": song, "artist": artist},
        source=SOURCE,
        retrieved_at=retrieved_at,
    )
    banker = (
        f"the US #1 single is “{song}” by {artist} "
        f"(Billboard Hot 100, chart dated {data.get('date', 'this week')})."
    ) if song else ""
    return {"charts": [chart], "banker": banker}
