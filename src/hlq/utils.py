# =============================================================================
# utils.py — Shared source requests and evidence verification.
#
# Part of Humanity's Last Quiz; see ARCHITECTURE.md for the data flow.
#
# Copyright (c) 2026 Temesgen Ataro <ataro.temesgen@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# =============================================================================

"""Small shared functions for source requests and text."""

from functools import lru_cache

import requests
from bs4 import BeautifulSoup

USER_AGENT = "HumanitysLastQuiz/0.2 (https://github.com/temataro/humanitys-last-quiz; ataro.temesgen@gmail.com)"


def get_json(url, params=None, timeout=25):
    response = requests.get(
        url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout
    )
    response.raise_for_status()
    return response.json()


def plain_text(value):
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


@lru_cache(maxsize=64)
def source_text(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup(["script", "style", "nav"]):
        node.decompose()
    return soup.get_text(" ", strip=True)


def verify_excerpt(url, excerpt):
    """Require a supplied evidence excerpt to actually occur on its cited page."""
    import re

    normalize = lambda text: re.sub(r"\W+", " ", plain_text(text).casefold()).strip()
    if len(normalize(excerpt).split()) < 5:
        return False
    try:
        return normalize(excerpt) in normalize(source_text(url))
    except requests.RequestException:
        return False
