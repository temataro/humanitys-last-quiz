# Repository Guidelines

## Project Structure & Module Organization

Humanity’s Last Quiz generates a weekly pub-quiz almanac with Python 3.10+ and Jinja2.

- `src/hlq/`: CLI, week calculations, edition models, provenance, build, and rendering; `fetch/` contains source providers.
- `templates/`: shared layout, weekly edition, and archive templates.
- `data/weeks/`: committed editions named `YYYY-Www.json`; `data/raw/`: corresponding source logs.
- `site/`: committed generated HTML and status files; regenerate through the renderer.
- `mockups/`: design references; `data/banner.png`: README image.
- `.github/workflows/weekly.yml`: scheduled builds and GitHub Pages deployment.

## Build, Test, and Development Commands

- `make setup`: create `.venv` and install `requirements.txt`.
- `make week`: fetch and build the latest completed week; requires network access.
- `make week SUNDAY=2026-07-26`: build a specific week.
- `make render`: regenerate the site from archived JSON without fetching sources.
- `make all`: build a week, then render.
- `make serve`: preview at `http://localhost:8000`.

The Makefile sets `PYTHONPATH=src`; direct CLI usage is `PYTHONPATH=src .venv/bin/python -m hlq.cli {build,render}`.

## Coding Style & Naming Conventions

Use four-space Python indentation, `snake_case` functions/modules, and `UPPER_CASE` constants. Prefer simple functions, minimal abstractions, and type hints only where ambiguity warrants them. Before committing Python changes, run Black on changed files, then `black --check` on those files; no formatter version is currently pinned.

For new code files, add a language-appropriate header with filename, purpose, copyright year, Temesgen Ataro, repository Git email, and `SPDX-License-Identifier: Apache-2.0`. For existing headers, only add the email to the authors. Markdown is exempt.

## Testing Guidelines

No automated test suite, framework, or coverage threshold is currently configured. For rendering changes, run `make render` and inspect the latest edition and archive through `make serve`, including light/dark themes and placeholder labels. Review generated diffs for unintended archive changes. Verify week boundaries and JSON round trips when changing those modules.

## Commit & Pull Request Guidelines

History uses imperative subjects and automated `chore: weekly edition …` messages. Keep commits focused. Review each diff twice: first scope/design/simplicity, then correctness and boundary behavior. Describe AI assistance and its purpose without attributing authorship to an assistant vendor.

PRs should describe behavior, validation, relevant issues, and archive changes; include screenshots for visual changes.

## Data Integrity & Configuration

Preserve per-fact provenance and authoritative birth/death dates. Keep placeholder editions visibly marked. Store optional `GEMINI_API_KEY` in ignored `.env` or Actions secrets; `HLQ_AGGREGATOR=free` selects keyless sources.
