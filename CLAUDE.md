# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What the product is

"Humanity's Last Quiz" is a **weekly broadsheet almanac** that pre-loads a pub-quiz team with the facts their quiz reliably asks about. A new edition is generated **every Sunday** covering the week just gone (Mon–Sun), and the site keeps an **archive** of all past editions. The content model (see `PLAN.md`): fixed staples (births/deaths on/around the date; top charts single/album/artist; top box-office film) plus rotating extras (a themed Top-10, trivia, geography).

## Commands

```bash
make setup                      # one-time: create .venv + install requirements.txt
make week                       # build the last completed week -> data/weeks/<id>.json
make week SUNDAY=2026-07-26     # build a specific week (any date snaps to its Sunday)
make render                     # regenerate site/ from every week in data/weeks/
make all                        # week + render
make serve                      # preview site/ at http://localhost:8000
```

The package runs via `PYTHONPATH=src` (it is not pip-installed); the Makefile handles this. Direct form: `PYTHONPATH=src .venv/bin/python -m hlq.cli {build,render}`. **No API key is required to build** — main uses Gemini if a key is present, otherwise the free keyless sources; set `GEMINI_API_KEY` (billing-enabled project) for grounded LLM coverage. `HLQ_AGGREGATOR=free` skips the LLM entirely.

## Branches

- **`main`** — Gemini primary, free sources as fallback, placeholder last (this doc).
- **`no-llm-provenance`** — the pure keyless, no-LLM pipeline preserved unmixed (free sources only). Port cross-cutting fixes (templates, week math, render, heartbeat) to both.

## Architecture

The core design is a **provenance-first pipeline**, split by hallucination risk, with a three-tier aggregation fallback:

- **Deterministic backbone** (`src/hlq/fetch/wikipedia.py`) — births/deaths from Wikimedia's "On this day" REST feed, one call per covered day. Exact dates are quiz-critical, so they always get an authoritative source (never the LLM).
- **Aggregator** (`src/hlq/fetch/aggregate.py`) fills charts/box office/Top-10/trivia/geography via, in order: (1) an **LLM provider** with web search — default **Gemini** (`gemini.py`; `HLQ_AGGREGATOR`), one grounded prompt/week from `prompts/aggregate.md`, JSON with a `source_url` per fact; (2) **free keyless sources** if the LLM is absent/errors — Open Trivia DB (`opentdb.py`), Billboard Hot 100 (`billboard.py`, + derived "banker"), World Bank rotating Top-10 + geography (`worldbank.py`); (3) **placeholder** only if all of that fails. Free-source sections also fail independently (a dead source → empty section).
- **Intentional stubs** (empty, not faked, when the free path is used and no clean source exists): UK charts, Billboard 200 albums, box office, chart history. The template hides empty sections.

> Why the fallback exists: free-tier LLM web search is unreliable/blocked (Gemini grounding needs billing; Groq Compound hits 413/TPM). `gemini.py`/`groq.py` are thin providers behind `LLM_PROVIDERS`. See the project memo in memory.

**Provenance is the load-bearing idea, not decoration.** Every datum is a `Fact` (`src/hlq/provenance.py`) pairing a `value` dict with a `Source` (name/url/license) and a retrieval timestamp. The broadsheet footer's source credits are **generated** from `Edition.sources()` (deduped), never hardcoded — so a wrong answer is always traceable to a citation. The TMDB disclaimer only renders when a TMDB source is actually present (`uses_tmdb` in `render.py`).

Data flow (build and render are separate so the site can be regenerated from the archive without re-fetching):

```
build.py  → fetch (wikipedia + aggregator: LLM→free→placeholder) → Edition → data/weeks/<id>.json  (committed archive)
                                                                            + data/raw/<id>.md       (prompt/response or source log)
render.py → read all data/weeks/*.json → templates/ → site/  (flat: <id>.html, index.html=latest, archive.html)
```

Key modules: `week.py` (ISO-week math — a Sunday is day 7 of its ISO week, giving sortable ids like `2026-W30` and a deterministic `edition_no` counted from `EPOCH_SUNDAY`); `model.py` (`Edition` ⇄ JSON; `FACT_SECTIONS` is the single list that keeps serialisation/`all_facts` in sync — add new sections there); `paths.py` (repo-root paths, cwd-independent).

The generated site is **committed** (`data/weeks/`, `data/raw/`, `site/` are not gitignored) — it *is* the archive.

**Dev heartbeat.** A deliberately quiet footer widget (in `base.html.j2`) reads two JSON files client-side and only turns amber/red when unhealthy: `site/status.json` (written by `render` — last *successful* build: time, live/placeholder mode, counts) and `site/heartbeat.json` (written by the workflow on *every* run via `if: always()`, even a failed one — run outcome, trigger, sha, logs URL). Because freshness is judged in the browser, a stale page still reveals a missed or failed Sunday cron. `heartbeat.json` is CI-only; the widget degrades gracefully without it. Fetch needs the site *served* (`make serve`), not opened as `file://`.

## Scheduling

`.github/workflows/weekly.yml` runs the build every Sunday 07:00 UTC (also `workflow_dispatch` with an optional `sunday`), commits the new archive + regenerated site, and deploys `site/` to GitHub Pages. Optional `GEMINI_API_KEY` Actions secret enables grounded LLM coverage (absent → free-source fallback, still a real edition); enable Pages. The repo exists locally (`main` + `no-llm-provenance`); add a GitHub remote + push before the workflow can run.

## Design system (from mockup A, the chosen direction)

Templates in `templates/` (`base` + `edition` + `archive`, Jinja2) are adapted from `mockups/a-broadsheet-almanac.html`. Keep the shared conventions; the other two mockups (`b-`, `c-`) remain as reference only.

- **Newspaper/almanac aesthetic** — serif body, sans-serif labels, mono for tabular figures (`font-variant-numeric: tabular-nums`).
- **Three theme states** — colors are `:root` CSS vars; every layout defines `@media (prefers-color-scheme: dark)` *plus* explicit `:root[data-theme="light"|"dark"]` for the manual toggle (persisted in `localStorage`). Define all three.
- **Placeholder editions must stay visibly flagged** — `Edition.placeholder` drives a banner and an archive "Sample" tag; never let sample data read as real.

## Known tunables / next steps

- Wikipedia births/deaths are capped per day (`PER_DAY`/`SECTION_CAP` in `wikipedia.py`) and taken in feed order — there's no notability ranking, so obscure names can surface. A pageview- or bluelink-based rank is the natural upgrade.
- **Stubbed sections** (`aggregate.py`): UK Official Charts, Billboard 200 albums, box office, and chart history have no clean free source yet. Adding them means finding a comparable free dataset (or scraping officialcharts.com / Box Office Mojo). Billboard Hot 100 comes from the `mhollingshead/billboard-hot-100` GitHub dataset.
- The World Bank Top-10 theme rotates on `edition_no % len(THEMES)` (land area / population / GDP) — add themes to `THEMES` in `worldbank.py`.

## Conventions

- When committing, do not credit Claude/Anthropic by name. Note that an AI was used and in what capacity, attributed to `tal@kamar.com`.
- Any data visualization must follow the Better Graphs design system (user's global instructions) — state chart type and why before plotting.
