# =============================================================================
# portraits.py — Cache attributed Wikimedia portrait thumbnails.
#
# Part of Humanity's Last Quiz; see ARCHITECTURE.md for the data flow.
#
# Copyright (c) 2026 Temesgen Ataro <ataro.temesgen@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# =============================================================================

"""Cache attributed Wikimedia portraits; never guess image URLs or faces."""

import hashlib
import json

import requests

from .wikipedia import query
from .. import paths
from ..utils import get_json, plain_text, USER_AGENT


def collect(people):
    directory = paths.DATA / "media"
    directory.mkdir(exist_ok=True)
    cache_file = directory / "portraits.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    portraits = {}
    people = {
        p["name"]: p["wikipedia_title"]
        for p in people
        if p.get("name") and p.get("wikipedia_title")
    }
    pending = [
        name
        for name, title in people.items()
        if title not in cache or not cache[title].get("large_url")
    ]
    for start in range(0, len(pending), 40):
        batch = pending[start : start + 40]
        try:
            result = query(
                prop="pageimages|pageprops",
                titles="|".join(people[n] for n in batch),
                redirects=1,
                piprop="name",
                pilicense="free",
            )
            query_data = result.get("query", {})
            redirects = {
                p["from"]: p["to"]
                for p in query_data.get("normalized", [])
                + query_data.get("redirects", [])
            }
            pages = {p["title"]: p for p in query_data.get("pages", [])}
            for name in batch:
                title = people[name]
                resolved = title
                for _ in range(5):
                    resolved = redirects.get(resolved, resolved)
                page = pages.get(resolved, {})
                filename = page.get("pageimage")
                if not filename or "disambiguation" in page.get("pageprops", {}):
                    continue
                try:
                    data = get_json(
                        "https://commons.wikimedia.org/w/api.php",
                        {
                            "action": "query",
                            "prop": "imageinfo",
                            "titles": "File:" + filename,
                            "iiprop": "url|extmetadata",
                            "iiurlwidth": 160,
                            "format": "json",
                            "formatversion": 2,
                        },
                    )
                    info = data["query"]["pages"][0].get("imageinfo", [{}])[0]
                    meta = info.get("extmetadata", {})
                    license_name = plain_text(
                        meta.get("LicenseShortName", {}).get("value", "")
                    )
                    if not license_name or not any(
                        v in license_name.lower()
                        for v in ("cc by", "cc0", "public domain")
                    ):
                        continue
                    url = info.get("thumburl") or info.get("url", "")
                    if not url.startswith("https://"):
                        continue
                    response = requests.get(
                        url, headers={"User-Agent": USER_AGENT}, timeout=25
                    )
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "").split(";")[
                        0
                    ]
                    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
                        continue
                    suffix = {
                        "image/jpeg": ".jpg",
                        "image/png": ".png",
                        "image/webp": ".webp",
                    }[content_type]
                    local_name = (
                        hashlib.sha256(filename.encode()).hexdigest()[:16] + suffix
                    )
                    (directory / local_name).write_bytes(response.content)
                    cache[title] = {
                        "url": "media/" + local_name,
                        "large_url": info.get("url", url),
                        "page_url": info.get("descriptionurl", ""),
                        "credit": plain_text(meta.get("Artist", {}).get("value", "")),
                        "license": license_name,
                        "license_url": meta.get("LicenseUrl", {}).get("value", ""),
                        "title": resolved,
                    }
                except (requests.RequestException, KeyError, IndexError) as exc:
                    print(f"  [portrait] {name}: {type(exc).__name__}")
        except requests.RequestException as exc:
            print(f"  [portrait] batch unavailable: {exc}")
    for name, title in people.items():
        portrait = cache.get(title)
        if portrait and (paths.DATA / portrait["url"]).exists():
            portraits[name] = portrait
    cache_file.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")
    return portraits
