#!/usr/bin/env python3
"""
scripts/fetch_city_images.py
─────────────────────────────
Fetches one landscape photo per destination from Wikimedia Commons (CC-licensed,
no API key required), optimizes each to ≤1200px / JPEG-80, and saves to
streamlit_app/assets/cities/.  Writes attributions to ATTRIBUTIONS.md.

Run from the project root:
    python scripts/fetch_city_images.py

Idempotent — skips cities whose file already exists.
Set FORCE=1 to re-download everything.

If a city fails, the script prints clear instructions for manual sourcing and
continues with the rest; it does NOT abort the whole run.
"""

import os
import re
import sys
import time
import json
import textwrap
import html
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

ROOT   = Path(__file__).parent.parent
ASSETS = ROOT / "streamlit_app" / "assets" / "cities"
ASSETS.mkdir(parents=True, exist_ok=True)

FORCE = os.environ.get("FORCE", "0") == "1"

MAX_LONG_EDGE   = 1200
JPEG_QUALITY    = 80
TARGET_MAX_BYTES = 250 * 1024   # 250 KB

HEADERS = {
    "User-Agent": (
        "WeatherHolidayRecommender/1.0 "
        "(https://github.com/student-project; educational use) "
        "python-requests/2.x"
    )
}

# ── City queries ──────────────────────────────────────────────────────────────
# (slug, primary search query, alt query, alt_text)
CITIES: list[tuple[str, str, str, str]] = [
    ("tenerife",   "Tenerife beach Canary Islands",
                   "Tenerife coastline Spain",
                   "Tenerife beach and volcanic coastline, Canary Islands"),
    ("tarifa",     "Tarifa beach kitesurf Spain wind",
                   "Tarifa Strait of Gibraltar coast",
                   "Tarifa beach on the Strait of Gibraltar, Spain"),
    ("barcelona",  "Barcelona skyline aerial panorama",
                   "Barcelona cityscape Catalonia",
                   "Barcelona cityscape and skyline, Spain"),
    ("lisbon",     "Lisbon cityscape Alfama Tagus river",
                   "Lisbon panorama Portugal",
                   "Lisbon rooftops and the River Tagus, Portugal"),
    ("dubrovnik",  "Dubrovnik old town walls Adriatic",
                   "Dubrovnik Croatia coast",
                   "Dubrovnik old town and Adriatic sea, Croatia"),
    ("rhodes",     "Rhodes old town medieval Greece",
                   "Rhodes island coast Greece",
                   "Rhodes medieval old town and coastline, Greece"),
    ("nice",       "Nice Promenade des Anglais French Riviera",
                   "Nice France coastline azure",
                   "Nice and the Promenade des Anglais, French Riviera"),
    ("chamonix",   "Chamonix Mont Blanc Alps mountains",
                   "Chamonix alpine peaks France",
                   "Chamonix and the Mont Blanc massif, French Alps"),
    ("bergen",     "Bergen Norway Bryggen fjord",
                   "Bergen Norway cityscape",
                   "Bergen Bryggen wharf and surrounding fjords, Norway"),
    ("reykjavik",  "Reykjavik Iceland cityscape mountain",
                   "Reykjavik subarctic landscape",
                   "Reykjavik with Mount Esja in the distance, Iceland"),
    ("prague",     "Prague old town skyline Charles Bridge",
                   "Prague cityscape Czech Republic",
                   "Prague old town skyline and Charles Bridge, Czechia"),
    ("amsterdam",  "Amsterdam canal houses Netherlands",
                   "Amsterdam canals city Netherlands",
                   "Amsterdam canal houses and waterways, Netherlands"),
]

FREE_LICENSES = {
    "cc0", "cc-zero", "public domain", "pd",
    "cc-by", "cc-by-sa", "cc-by-2.0", "cc-by-3.0", "cc-by-4.0",
    "cc-by-sa-2.0", "cc-by-sa-3.0", "cc-by-sa-4.0",
    "cc by", "cc by-sa",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_html(s: str) -> str:
    """Remove HTML tags and decode entities."""
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def _is_free(license_str: str) -> bool:
    return any(tok in license_str.lower() for tok in FREE_LICENSES)


def _search_wikimedia(query: str, n: int = 12) -> list[dict]:
    """Search Wikimedia Commons for images matching query; return metadata list."""
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action":       "query",
        "generator":    "search",
        "gsrnamespace": 6,          # File namespace
        "gsrlimit":     n,
        "gsrsearch":    query,
        "prop":         "imageinfo",
        "iiprop":       "url|extmetadata|size",
        "iiurlwidth":   1200,
        "format":       "json",
        "formatversion": 2,
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        print(f"    [WARN] Wikimedia search failed for '{query}': {exc}")
        return []

    pages = data.get("query", {}).get("pages", [])
    results = []
    for page in pages:
        ii_list = page.get("imageinfo", [])
        if not ii_list:
            continue
        ii = ii_list[0]

        # Must be JPEG or PNG
        src = ii.get("thumburl") or ii.get("url", "")
        if not src.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png")):
            continue

        meta = ii.get("extmetadata", {})
        license_raw = (
            meta.get("LicenseShortName", {}).get("value", "")
            or meta.get("License", {}).get("value", "")
        )
        if not _is_free(license_raw):
            continue

        width  = ii.get("thumbwidth")  or ii.get("width",  0)
        height = ii.get("thumbheight") or ii.get("height", 0)
        if not width or not height:
            continue

        author = _strip_html(
            meta.get("Artist", {}).get("value", "")
            or meta.get("Credit", {}).get("value", "Unknown")
        )[:200]
        desc_url = (
            meta.get("DescriptionUrl", {}).get("value", "")
            or f"https://commons.wikimedia.org/wiki/{page.get('title','')}"
        )
        results.append({
            "url":      src,
            "author":   author or "Unknown",
            "license":  _strip_html(license_raw),
            "desc_url": desc_url,
            "width":    width,
            "height":   height,
        })

    # Prefer landscape (wide), large images
    results.sort(
        key=lambda x: (
            1 if x["width"] > x["height"] * 1.1 else 0,   # landscape first
            x["width"] * x["height"],                       # then largest
        ),
        reverse=True,
    )
    return results


def _download_and_optimize(url: str, dest: Path) -> bool:
    """Download image URL, optimize, and save as JPEG to dest. Returns True on success."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        r.raise_for_status()
        raw = BytesIO(r.content)
    except Exception as exc:
        print(f"    [WARN] Download failed: {exc}")
        return False

    try:
        img = Image.open(raw).convert("RGB")
    except Exception as exc:
        print(f"    [WARN] Pillow could not open image: {exc}")
        return False

    # Resize so long edge ≤ MAX_LONG_EDGE
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > MAX_LONG_EDGE:
        scale = MAX_LONG_EDGE / long_edge
        img = img.resize(
            (int(w * scale), int(h * scale)),
            Image.LANCZOS,
        )

    # Save with progressively lower quality until under TARGET_MAX_BYTES
    quality = JPEG_QUALITY
    while quality >= 50:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size = buf.tell()
        if size <= TARGET_MAX_BYTES:
            break
        quality -= 5

    dest.write_bytes(buf.getvalue())
    kb = buf.tell() // 1024
    print(f"    Saved {dest.name}  ({img.width}×{img.height}  {kb} KB  q={quality})")
    return True


def _write_attributions(records: list[dict]) -> None:
    lines = [
        "# Image Attributions",
        "",
        "All images are sourced from Wikimedia Commons under free licenses.",
        "Files are stored in `streamlit_app/assets/cities/`.",
        "",
        "| File | City | Source URL | Author | License |",
        "|------|------|-----------|--------|---------|",
    ]
    for rec in sorted(records, key=lambda r: r["slug"]):
        lines.append(
            f"| {rec['slug']}.jpg "
            f"| {rec['city']} "
            f"| [{rec['desc_url']}]({rec['desc_url']}) "
            f"| {rec['author']} "
            f"| {rec['license']} |"
        )
    lines += [
        "",
        "## Note on license compliance",
        "",
        "CC-BY and CC-BY-SA licenses require attribution when images are shown publicly.",
        "This file serves as the attribution record.",
        "CC0 / Public Domain images require no attribution.",
        "",
        "Before deploying publicly, verify each license at the source URL above.",
    ]
    attr_path = ASSETS / "ATTRIBUTIONS.md"
    attr_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nAttributions written → {attr_path.relative_to(ROOT)}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Fetching images → {ASSETS.relative_to(ROOT)}")
    print(f"FORCE={FORCE}\n{'─'*55}")

    records: list[dict] = []
    failed: list[str]   = []

    # Load existing attributions so we can merge rather than overwrite
    attr_path = ASSETS / "ATTRIBUTIONS.md"

    for slug, primary_query, alt_query, alt_text in CITIES:
        dest = ASSETS / f"{slug}.jpg"
        city_display = slug.capitalize()

        if dest.exists() and not FORCE:
            print(f"  ✓ {slug}.jpg already exists — skipping")
            # Preserve attribution entry
            records.append({
                "slug": slug, "city": city_display,
                "desc_url": "(already present)", "author": "(see existing ATTRIBUTIONS.md)",
                "license": "(see existing ATTRIBUTIONS.md)",
            })
            continue

        print(f"  → {slug}: searching…")
        candidates = _search_wikimedia(primary_query)
        if not candidates:
            print(f"    No results for primary query, trying alt…")
            candidates = _search_wikimedia(alt_query)

        if not candidates:
            print(f"    [FAIL] No usable CC-licensed images found for {slug}.")
            failed.append(slug)
            continue

        best = candidates[0]
        print(f"    Best candidate: {best['url'][:80]}… ({best['width']}×{best['height']})")
        ok = _download_and_optimize(best["url"], dest)
        if ok:
            records.append({
                "slug":     slug,
                "city":     city_display,
                "desc_url": best["desc_url"],
                "author":   best["author"],
                "license":  best["license"],
            })
        else:
            print(f"    [FAIL] Could not save {slug}.")
            failed.append(slug)

        time.sleep(0.5)   # be polite to Wikimedia

    _write_attributions(records)

    print(f"\n{'─'*55}")
    if failed:
        print(f"FAILED ({len(failed)}): {', '.join(failed)}")
        print("\nFor each failed city, manually drop a JPEG into:")
        print(f"  {ASSETS.relative_to(ROOT)}/")
        print("Using any CC0/CC-BY image from:")
        print("  https://unsplash.com  or  https://www.pexels.com  or  https://commons.wikimedia.org")
        print("Name the file exactly:  <slug>.jpg  (see CITIES list in this script)")
    else:
        print("All images fetched successfully.")

    # Size report
    jpegs = sorted(ASSETS.glob("*.jpg"))
    total_kb = sum(f.stat().st_size for f in jpegs) // 1024
    print(f"\nAsset total: {len(jpegs)} images, {total_kb} KB")
    for f in jpegs:
        kb = f.stat().st_size // 1024
        flag = "  ⚠️  > 250 KB" if kb > 250 else ""
        print(f"  {f.name:20s}  {kb:4d} KB{flag}")


if __name__ == "__main__":
    main()
