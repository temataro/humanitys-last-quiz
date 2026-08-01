"""Provenance primitives.

Every fact that reaches the page carries where it came from. A `Fact` pairs a
rendered value with its `Source`, so the broadsheet footer can be *generated*
from the sources actually used rather than hardcoded — and so a wrong answer can
always be traced back to a citation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class Source:
    """Where a fact came from. `url` is the specific citation when known."""

    name: str              # e.g. "Wikipedia", "Billboard", "Google Search (Gemini)"
    url: str = ""          # specific page cited, when available
    license: str = ""      # e.g. "CC BY-SA 4.0", "" if unknown/proprietary

    def key(self) -> tuple[str, str]:
        """Identity used to de-duplicate sources for the footer credits."""
        return (self.name, self.license)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Source":
        return cls(name=d["name"], url=d.get("url", ""), license=d.get("license", ""))


@dataclass
class Fact:
    """A single quiz-relevant datum plus its provenance.

    `value` is a small dict whose shape depends on the section (a birth has
    year/who/what; a chart row has pos/title/artist). Keeping it open lets one
    Fact type serve every section while the template decides how to render it.
    """

    value: dict[str, Any]
    source: Source
    retrieved_at: str = ""   # ISO-8601 UTC timestamp of when it was fetched

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source.to_dict(),
            "retrieved_at": self.retrieved_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Fact":
        return cls(
            value=d["value"],
            source=Source.from_dict(d["source"]),
            retrieved_at=d.get("retrieved_at", ""),
        )


def dedupe_sources(facts: list[Fact]) -> list[Source]:
    """Collapse the sources across a set of facts into footer-ready credits.

    De-dupes by (name, license); keeps the first non-empty url seen so a credit
    line can link somewhere sensible. Order is stable (first appearance).
    """
    seen: dict[tuple[str, str], Source] = {}
    for f in facts:
        k = f.source.key()
        if k not in seen:
            seen[k] = f.source
        elif not seen[k].url and f.source.url:
            seen[k] = f.source
    return list(seen.values())
