# Architecture

Humanity’s Last Quiz is a Python/Jinja2 static site published through GitHub Pages.
The edition’s chart/trivia coverage remains Monday–Sunday. Its people and cultural
calendar cover publication Sunday minus five through plus five days.

```text
Wikipedia birthday feeds (all eleven days) ─┐
Wikipedia dated recent-death lists ────────┤→ pageview ranking → people/calendar research
                                         │                       ↓
Gemini grounded weekly research ──────────┘                 sourced Edition
  ↳ free sources on failure                                      ↓
Wikimedia free photographs → attribution + local cache → data/weeks/YYYY-Www.json
                                                             data/raw/ audit files
                                                                    ↓
Natural Earth boundaries + World Bank capitals → render.py + templates/ → site/
```

## Collection and publication

- `fetch/wikipedia.py` keeps dates deterministic. Birthday candidates are ranked
  across all eras, with two candidates from each day. Popularity queries follow
  continuation pages. Recent-death lists are parsed by actual year/month/day;
  future dates and red-link biographies are excluded.
- `fetch/people.py` makes one grounded call to curate those candidates and research
  cultural dates. The model can select existing people, not invent replacements.
- `fetch/aggregate.py` makes one grounded call for charts, box office, lists,
  trivia and geography. Current charts cannot silently backfill old editions.
  Summaries derive from accepted chart rows. Chart-history generation is removed.
- Dated chart/box-office rows and calendar events require evidence excerpts found
  on their cited pages. Missing citations never inherit unrelated grounding URLs.
  Blocked or inaccessible pages may cause otherwise true items to be omitted.
  Evidence matching confirms text presence, not full semantic entailment; static
  trivia and rankings still rely on grounded research and editorial review.
- `fetch/gemini.py` uses the Interactions API and archives search steps, citation
  annotations, timing and token usage. Structured JSON may omit inline annotations;
  successful search-result steps still establish that research used Search.
  Date-checked free charts fill chart gaps when source pages are inaccessible. Normal builds use
  at most two LLM calls, without automatic paid retries. API/model pricing depends
  on the configured provider; no exact cost is assumed.
- `fetch/portraits.py` batches identity lookups, downloads free Wikimedia images,
  and caches small thumbnails plus author/licence metadata in `data/media/`.
  Full-size originals load on demand when clicked. Missing, ambiguous or
  non-free images are omitted. PageImages can return group/full-body photographs;
  automatic selection does not guarantee a tight facial portrait.
- `build.py` persists the edition plus raw responses and `.audit.json` metadata.
  Rendering is offline. Older JSON facts remain unchanged and gain the current
  layout; legacy death anniversaries are explicitly labelled as archived.

## Rendering

`geography.py` rotates six regional rounds, each with five numbered countries and
revealable capitals. Country geometry and metadata are checked in under
`data/maps/`; the map needs neither an LLM nor a browser map service.

`render.py` generates edition, archive and cultural-calendar pages. Its emphasis
filter escapes source text, bolds known proper nouns, and inserts portrait buttons.
A native dialog provides enlargement, keyboard dismissal and focus restoration.
Photo attributions remain visible in each edition’s credits.

## Automation and verification

The weekly workflow runs regression tests, builds with the Actions Gemini secret,
regenerates the site, commits the archive/media, and deploys Pages. Source pushes
also rebuild the latest edition. CI requires verified cultural dates and a chart
before replacing the edition; rejected research remains in the audit files.
The Sunday 07:00 UTC run is a snapshot: deaths
occurring later and final weekend figures may need a subsequent manual rebuild.

Run `make setup`, `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`,
`make render`, and `make serve`. Install Black separately before Python commits;
run it and `black --check` on every changed Python file. Browser tooling is for
local verification and is not a runtime dependency.
