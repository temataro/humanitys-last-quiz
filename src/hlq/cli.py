"""Command-line entry point: `hlq build [--sunday YYYY-MM-DD]` and `hlq render`."""

from __future__ import annotations

import argparse
import os
import sys

from . import build, paths, render
from .week import parse_sunday


def _load_dotenv() -> None:
    """Load ROOT/.env into the environment (dependency-free; existing vars win).

    Lets you keep GEMINI_API_KEY in a gitignored .env instead of exporting it.
    """
    env = paths.ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(prog="hlq", description="Humanity's Last Quiz weekly almanac")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="fetch + assemble one week -> data/weeks/<id>.json")
    b.add_argument("--sunday", metavar="YYYY-MM-DD",
                   help="publish Sunday (any date snaps to its week); defaults to the last completed week")

    sub.add_parser("render", help="regenerate site/ from every week in data/weeks/")

    args = parser.parse_args(argv)
    if args.command == "build":
        build.run(parse_sunday(args.sunday) if args.sunday else None)
        return 0
    if args.command == "render":
        render.render()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
