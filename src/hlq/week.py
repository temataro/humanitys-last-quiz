"""Week arithmetic.

An edition is published on a Sunday and covers the seven days ending on that
Sunday — "the week just gone" (Mon..Sun). Because a Sunday is day 7 of its ISO
week, the ISO week of the publish-Sunday *is* the week the edition covers, which
gives every edition a clean, sortable id like ``2026-W30``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# First edition. Edition numbers count Sundays from here, so they stay stable
# and deterministic no matter when the pipeline runs.
EPOCH_SUNDAY = date(2026, 1, 4)  # first Sunday of 2026


def most_recent_sunday(today: date) -> date:
    """The most recent Sunday on or before ``today`` (Python weekday: Sun == 6)."""
    return today - timedelta(days=(today.weekday() + 1) % 7)


@dataclass(frozen=True)
class WeekRange:
    sunday: date  # publication day; also the last covered day

    @property
    def start(self) -> date:
        return self.sunday - timedelta(days=6)

    @property
    def end(self) -> date:
        return self.sunday

    @property
    def week_id(self) -> str:
        iso = self.sunday.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    @property
    def edition_no(self) -> int:
        return (self.sunday - EPOCH_SUNDAY).days // 7 + 1

    def dates(self) -> list[date]:
        """Every covered day, Monday-first."""
        return [self.start + timedelta(days=i) for i in range(7)]

    def label(self) -> str:
        """Human coverage span, e.g. '20 – 26 July 2026' (collapses same-month)."""
        s, e = self.start, self.end
        if (s.year, s.month) == (e.year, e.month):
            return f"{s.day} – {e.day} {e:%B %Y}"
        if s.year == e.year:
            return f"{s.day} {s:%B} – {e.day} {e:%B %Y}"
        return f"{s.day} {s:%B %Y} – {e.day} {e:%B %Y}"

    @classmethod
    def for_sunday(cls, sunday: date) -> "WeekRange":
        """Snap any date to a Sunday (itself if already Sunday), so ids stay consistent."""
        return cls(sunday=most_recent_sunday(sunday))

    @classmethod
    def most_recent(cls, today: date) -> "WeekRange":
        return cls(sunday=most_recent_sunday(today))


def parse_sunday(s: str) -> date:
    """Parse a 'YYYY-MM-DD' CLI argument into a date."""
    y, m, d = (int(p) for p in s.split("-"))
    return date(y, m, d)
