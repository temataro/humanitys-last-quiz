"""Repo-root-relative paths, resolved from this file so cwd doesn't matter."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # src/hlq/paths.py -> repo root
TEMPLATES = ROOT / "templates"
DATA = ROOT / "data"
WEEKS = DATA / "weeks"       # committed archive: one <week_id>.json per edition
RAW = DATA / "raw"           # archived LLM prompt+response per edition
SITE = ROOT / "site"         # generated static output
