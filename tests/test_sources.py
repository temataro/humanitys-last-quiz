# =============================================================================
# test_sources.py — Regression checks for dates, sources, archives, and rendering.
#
# Part of Humanity's Last Quiz; see ARCHITECTURE.md for the data flow.
#
# Copyright (c) 2026 Temesgen Ataro <ataro.temesgen@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# =============================================================================

"""Regression checks for date windows, citations, archives, maps and safe rendering."""

import json
import unittest
import tempfile
from pathlib import Path
from datetime import date
from unittest.mock import patch, Mock

from hlq.fetch import aggregate, wikipedia, billboard, gemini
from hlq.geography import regional_round
from hlq.model import Edition
from hlq.provenance import Fact, Source
from hlq.render import emphasize
from hlq.utils import verify_excerpt


def edition():
    return Edition(
        "2026-W46",
        46,
        "2026-11-15",
        "2026-11-09",
        "2026-11-15",
        "9–15 November",
        "2026-11-16T10:00:00Z",
    )


class SourceTests(unittest.TestCase):
    def test_window_crosses_year_without_changing_dates(self):
        from hlq.week import WeekRange

        days = wikipedia.window(WeekRange(date(2027, 1, 3)))
        self.assertEqual(
            (days[0], days[-1], len(days)), (date(2026, 12, 29), date(2027, 1, 8), 11)
        )

    def test_recent_death_parser_ignores_contextual_links_and_historical_months(self):
        html = """<h2>October</h2><h3>12</h3><ul><li><a href="/wiki/Old">Old</a>, actor.</li></ul>
        <h2>November</h2><h3>12</h3><ul>
        <li><a class="new" href="/w/index.php?title=Missing">Missing person</a>, survivor of <a href="/wiki/Event">Event</a>.</li>
        <li><a href="/wiki/Actual_actor" title="Actual actor">Actual actor</a>, 80, actor.</li></ul>"""
        facts = wikipedia.parse_deaths(
            html, date(2026, 11, 1), {date(2026, 11, 12)}, "2026-11-16"
        )
        self.assertEqual([f.value["who"] for f in facts], ["Actual actor"])
        self.assertEqual(facts[0].value["on"], "2026-11-12")

    @patch("hlq.fetch.wikipedia.get_json")
    def test_deaths_exclude_future_dates(self, get):
        from hlq.week import WeekRange

        get.return_value = {
            "parse": {
                "text": '<h3>20</h3><ul><li><a href="/wiki/Future">Future</a>, actor.</li></ul>'
            }
        }
        self.assertEqual(
            wikipedia.deaths(WeekRange(date(2026, 11, 15)), "2026-11-16T00:00:00Z"), []
        )

    @patch("hlq.fetch.wikipedia.query")
    def test_popularity_ranking_follows_continuation(self, query):
        query.side_effect = [
            {
                "query": {"pages": [{"title": "Young", "pageviews": {"day": 10}}]},
                "continue": {"pvipcontinue": "Older", "continue": "||"},
            },
            {"query": {"pages": [{"title": "Older", "pageviews": {"day": 1000}}]}},
        ]
        facts = [
            Fact({"who": name}, Source("Wikipedia")) for name in ("Young", "Older")
        ]
        self.assertEqual(wikipedia.ranked(facts)[0].value["who"], "Older")
        self.assertEqual(query.call_args.kwargs["pvipcontinue"], "Older")

    def test_missing_citation_never_inherits_unrelated_grounding_url(self):
        source = aggregate._source("")
        self.assertEqual(source.url, "")
        self.assertEqual(
            aggregate._to_facts({"trivia": [{"q": "Q", "a": "A"}]}, "now").trivia,
            [],
        )

    def test_unsafe_citation_is_rejected(self):
        self.assertEqual(aggregate._source("javascript:alert(1)").url, "")

    def test_chart_outside_edition_is_rejected(self):
        from hlq.week import WeekRange

        row = {
            "chart_date": "2026-11-21",
            "position": 1,
            "evidence": "some evidence from a reliable source",
            "source_url": "https://example.org/chart",
        }
        self.assertEqual(
            aggregate._to_facts(
                {"charts": [row]}, "now", WeekRange(date(2026, 11, 15))
            ).charts,
            [],
        )

    @patch("hlq.fetch.billboard.requests.get")
    def test_free_chart_cannot_silently_backfill_an_old_edition(self, get):
        from hlq.week import WeekRange

        get.return_value.json.return_value = {
            "date": "2026-11-14",
            "data": [{"rank": 1, "song": "Song", "artist": "Artist"}],
        }
        with self.assertRaises(ValueError):
            billboard.collect("now", week=WeekRange(date(2026, 7, 26)))

    @patch("hlq.utils.requests.get")
    def test_evidence_must_occur_in_source_body(self, get):
        get.return_value.text = "<html><p>The festival takes place on 14 November 2026.</p><script>Invented evidence is written in scripts</script></html>"
        self.assertTrue(
            verify_excerpt(
                "https://example.org", "The festival takes place on 14 November 2026"
            )
        )
        self.assertFalse(
            verify_excerpt(
                "https://example.org", "Invented evidence is written in scripts"
            )
        )

    def test_archived_edition_round_trip(self):
        from hlq import paths

        for path in paths.WEEKS.glob("*.json"):
            data = json.loads(path.read_text())
            restored = Edition.from_dict(data).to_dict()
            for key, value in data.items():
                self.assertEqual(restored[key], value, (path.name, key))

    def test_each_region_has_five_numbered_answers_and_capitals(self):
        for n in range(1, 7):
            result = regional_round(n)
            self.assertEqual([c["number"] for c in result["answers"]], [1, 2, 3, 4, 5])
            self.assertTrue(all(c["capital"] for c in result["answers"]))
            self.assertEqual(result["svg"].count('class="selected"'), 5)

    def test_emphasis_escapes_html_and_respects_word_boundaries(self):
        ed = edition()
        ed.proper_nouns = ["Us", "Anne Hathaway"]
        html = str(
            emphasize("Music with Anne Hathaway and Us <script>alert(1)</script>", ed)
        )
        self.assertIn("<strong>Anne Hathaway</strong>", html)
        self.assertIn("<strong>Us</strong>", html)
        self.assertNotIn("M<strong>us</strong>", html)
        self.assertNotIn("<script>", html)

    @patch.dict("os.environ", {"HLQ_REQUIRE_RESEARCH": "1"})
    def test_failed_calendar_verification_preserves_existing_edition(self):
        from hlq import build

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "2026-W46.json"
            old.write_text("previous edition")
            with (
                patch.object(build.paths, "WEEKS", root),
                patch.object(build.paths, "RAW", root),
                patch.object(build.paths, "ROOT", root),
            ):
                with self.assertRaises(AssertionError):
                    build._persist(edition(), aggregate.Aggregation())
            self.assertEqual(old.read_text(), "previous edition")
            self.assertTrue((root / "2026-W46.audit.json").exists())

    def test_interactions_search_annotations_are_archived(self):
        interaction = Mock()
        interaction.model_dump.return_value = {
            "steps": [
                {
                    "type": "google_search_call",
                    "arguments": {"queries": ["current chart"]},
                },
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://example.org/dated-chart",
                                }
                            ],
                        }
                    ],
                },
            ],
            "usage": {"total_tokens": 123},
        }
        evidence = gemini._evidence(interaction)
        self.assertEqual(evidence["urls"], ["https://example.org/dated-chart"])
        self.assertEqual(evidence["usage"]["total_tokens"], 123)

    def test_collaborating_artists_each_keep_their_portrait(self):
        ed = edition()
        ed.charts = [
            Fact(
                {"artist": "Artist One & Artist Two", "title": "Duet"}, Source("Chart")
            )
        ]
        ed.portraits = {
            name: {
                "url": "media/photo.jpg",
                "page_url": "https://example.org",
                "credit": "Photo",
            }
            for name in ("Artist One", "Artist Two")
        }
        html = str(emphasize("Artist One & Artist Two", ed))
        self.assertEqual(html.count('<button class="portrait"'), 2)

    def test_portrait_is_a_button_with_enlargement_metadata(self):
        ed = edition()
        ed.portraits = {
            "Anne Hathaway": {
                "url": "media/portrait.jpg",
                "page_url": "https://commons.wikimedia.org/wiki/File:Portrait.jpg",
                "credit": 'Photographer "Name"',
            }
        }
        html = str(emphasize("Anne Hathaway", ed))
        self.assertIn('data-image="media/portrait.jpg"', html)
        self.assertIn("<strong>Anne Hathaway</strong>", html)
        self.assertIn('aria-label="Enlarge portrait of Anne Hathaway"', html)


if __name__ == "__main__":
    unittest.main()
