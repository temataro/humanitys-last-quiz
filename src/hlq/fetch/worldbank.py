"""Top-10 list + geography — the World Bank API (free, no key).

The indicator endpoints return one row per "country", but the list also includes
aggregate regions ("Sub-Saharan Africa", "World", …). We fetch the country
metadata once to keep only real sovereign countries, then rank.

The Top-10 theme rotates weekly (land area / population / GDP) off the edition
number, so it's deterministic and varied. A few geography facts are derived from
the same data, each cited to the World Bank series.
"""

from __future__ import annotations

import requests

from ..provenance import Fact, Source
from ..week import WeekRange

BASE = "https://api.worldbank.org/v2"
UA = {"User-Agent": "HumanitysLastQuiz/0.1 (tal@kamar.com)"}


def _src(indicator: str) -> Source:
    return Source("World Bank", f"{BASE}/indicator/{indicator}", "CC BY 4.0")


def _human(n: float, unit: str = "") -> str:
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= div:
            return f"{n / div:.2f}{suf}".rstrip("0").rstrip(".") + (f" {unit}" if unit else "")
    return f"{n:.0f}" + (f" {unit}" if unit else "")


# Rotating Top-10 themes. (indicator, title, unit, prefix)
THEMES = [
    ("AG.LND.TOTL.K2", "Ten largest countries by land area", "km²", ""),
    ("SP.POP.TOTL", "Ten most populous countries", "", ""),
    ("NY.GDP.MKTP.CD", "Ten largest economies by GDP", "", "$"),
]


def _real_country_codes(timeout: float) -> set[str]:
    r = requests.get(f"{BASE}/country", params={"format": "json", "per_page": "400"},
                     headers=UA, timeout=timeout)
    r.raise_for_status()
    rows = r.json()[1]
    return {c["id"] for c in rows if (c.get("region") or {}).get("value") != "Aggregates"}


def _ranked(indicator: str, real: set[str], timeout: float) -> list[tuple[str, float]]:
    """(country_name, value) for real countries, most-recent value, high to low."""
    r = requests.get(f"{BASE}/country/all/indicator/{indicator}",
                     params={"format": "json", "mrnev": "1", "per_page": "400"},
                     headers=UA, timeout=timeout)
    r.raise_for_status()
    out = []
    for row in r.json()[1]:
        # The indicator's country.id is a 2-char WB code; the ISO3 (matching the
        # /country metadata id) is in countryiso3code.
        code = row.get("countryiso3code") or (row.get("country") or {}).get("id")
        val = row.get("value")
        if code in real and val is not None:
            out.append((row["country"]["value"], float(val)))
    out.sort(key=lambda t: t[1], reverse=True)
    return out


def collect(week: WeekRange, retrieved_at: str, timeout: float = 25.0) -> dict:
    """Return ``{"top_list": [Fact], "top_list_title": str, "geography": [Fact]}``."""
    real = _real_country_codes(timeout)

    indicator, title, unit, prefix = THEMES[week.edition_no % len(THEMES)]
    ranked = _ranked(indicator, real, timeout)
    top_list = [
        Fact({"label": name, "value": prefix + _human(val, unit)}, _src(indicator), retrieved_at)
        for name, val in ranked[:10]
    ]

    # Geography facts derived from land area + population (cited to the series).
    geography: list[Fact] = []
    area = _ranked("AG.LND.TOTL.K2", real, timeout)
    pop = _ranked("SP.POP.TOTL", real, timeout)
    if area:
        geography.append(Fact(
            {"fact": f"The largest country by land area is {area[0][0]}, at {_human(area[0][1], 'km²')}."},
            _src("AG.LND.TOTL.K2"), retrieved_at))
        geography.append(Fact(
            {"fact": f"The smallest country by land area (World Bank data) is {area[-1][0]}, at {_human(area[-1][1], 'km²')}."},
            _src("AG.LND.TOTL.K2"), retrieved_at))
    if pop:
        geography.append(Fact(
            {"fact": f"The most populous country is {pop[0][0]}, with about {_human(pop[0][1])} people."},
            _src("SP.POP.TOTL"), retrieved_at))

    return {"top_list": top_list, "top_list_title": title, "geography": geography}
