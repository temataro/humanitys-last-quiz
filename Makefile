# Humanity's Last Quiz — weekly broadsheet almanac
#
# Typical use:
#   make setup      # one-time: venv + deps
#   make week       # fetch the week just gone -> data/weeks/<ISO-week>.json
#   make render     # (re)generate site/ from every week in data/weeks/
#   make all        # week + render
#   make serve      # preview site/ at http://localhost:8000
#
# Override the target week (defaults to the most recent completed week):
#   make week SUNDAY=2026-07-26

PY := PYTHONPATH=src .venv/bin/python
PIP := .venv/bin/pip
SUNDAY ?=

.PHONY: setup week render all serve clean

setup:
	python3 -m venv .venv
	$(PIP) install -q -r requirements.txt
	@echo "Ready. Set GEMINI_API_KEY in your environment (or .env) to enable live aggregation."

week:
	$(PY) -m hlq.cli build $(if $(SUNDAY),--sunday $(SUNDAY),)

render:
	$(PY) -m hlq.cli render

all: week render

serve:
	@echo "Serving site/ at http://localhost:8000  (Ctrl-C to stop)"
	$(PY) -m http.server 8000 --directory site

clean:
	rm -rf site
