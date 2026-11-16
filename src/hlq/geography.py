# =============================================================================
# geography.py — Build offline regional country-identification maps.
#
# Part of Humanity's Last Quiz; see ARCHITECTURE.md for the data flow.
#
# Copyright (c) 2026 Temesgen Ataro <ataro.temesgen@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# =============================================================================

"""An offline regional identification round from Natural Earth and World Bank data."""

import json
from html import escape

from . import paths

REGIONS = [
    ("South America", ["COL", "ECU", "PER", "BOL", "URY"], (-85, -58, -32, 15)),
    ("West Africa", ["SEN", "GMB", "GIN", "GHA", "BEN"], (-20, 0, 17, 25)),
    ("Southeast Asia", ["MMR", "THA", "KHM", "LAO", "VNM"], (88, -2, 112, 30)),
    ("Central Asia", ["KAZ", "UZB", "TKM", "KGZ", "TJK"], (45, 33, 88, 57)),
    ("Southeast Europe", ["ALB", "MNE", "MKD", "BGR", "ROU"], (13, 36, 32, 49)),
    ("Central America", ["GTM", "BLZ", "HND", "SLV", "NIC"], (-96, 5, -75, 23)),
]


def regional_round(edition_no):
    region, codes, bounds = REGIONS[(edition_no - 1) % len(REGIONS)]
    countries = json.loads((paths.DATA / "maps/countries.json").read_text())
    west, south, east, north = bounds
    # Equirectangular projection; cropped to one region, with surrounding countries.
    viewbox = f"{west} {-north} {east-west} {north-south}"
    shapes, labels, answers = [], [], []
    for country in countries:
        geometry = country["geometry"]
        polygons = (
            geometry["coordinates"]
            if geometry["type"] == "MultiPolygon"
            else [geometry["coordinates"]]
        )
        commands = []
        for polygon in polygons:
            for ring in polygon:
                commands.append(
                    "M" + "L".join(f"{x:.3f},{-y:.3f}" for x, y in ring) + "Z"
                )
        selected = country["code"] in codes
        shapes.append(
            f'<path class="{"selected" if selected else "context"}" d="{" ".join(commands)}"/>'
        )
        if selected:
            number = codes.index(country["code"]) + 1
            x, y = country["label"]
            labels.append(f'<text x="{x}" y="{-y}" aria-hidden="true">{number}</text>')
            answers.append(
                {
                    "number": number,
                    "name": country["name"],
                    "capital": country["capital"],
                    "source_url": f"https://api.worldbank.org/v2/country/{country['code']}?format=json",
                }
            )
    svg = (
        f'<svg class="regional-map" viewBox="{viewbox}" role="img" aria-labelledby="map-title map-description">'
        f'<title id="map-title">{escape(region)} identification round</title>'
        '<desc id="map-description">Five highlighted countries are numbered. Reveal each answer below for its name and capital.</desc>'
        + "".join(shapes + labels)
        + "</svg>"
    )
    return {
        "region": region,
        "svg": svg,
        "answers": sorted(answers, key=lambda a: a["number"]),
    }
