"""
Resolve a CSS font-family name to a local TTF file path.

For local fonts, the TTF is already in backend/assets/fonts/.
For Google Fonts, the TTF is downloaded on first use and cached there.
"""

import re
import logging
from functools import lru_cache
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Fonts whose TTF files are already present in FONTS_DIR
_LOCAL_MAP: dict[str, str] = {
    "Montserrat": "Montserrat-Regular.ttf",
    "Liberation Sans": "LiberationSans-Regular.ttf",
    "Orbitron": "Orbitron-Regular.ttf",
}

_LOCAL_BOLD_MAP: dict[str, str] = {
    "Liberation Sans": "LiberationSans-Bold.ttf",
    "Orbitron": "Orbitron-Bold.ttf",
}

# Old Safari UA — causes Google Fonts CSS API to return TTF src URLs
_GFONTS_UA = (
    "Mozilla/5.0 (Windows NT 6.1) "
    "AppleWebKit/534.54.16 (KHTML, like Gecko) "
    "Version/5.1.4 Safari/534.54.16"
)


@lru_cache(maxsize=128)
def resolve_font_path(font_family: str, bold: bool = False) -> str:
    """
    Return an absolute path string to a TTF file for the given CSS font-family name.
    Downloads and caches the file from Google Fonts on first use.
    Falls back to Montserrat if resolution fails.
    """
    weight = 700 if bold else 400

    # Check local bold map first (for fonts with a bundled bold file)
    if bold and font_family in _LOCAL_BOLD_MAP:
        candidate = FONTS_DIR / _LOCAL_BOLD_MAP[font_family]
        if candidate.exists():
            return str(candidate)

    # Check local regular map
    if not bold and font_family in _LOCAL_MAP:
        candidate = FONTS_DIR / _LOCAL_MAP[font_family]
        if candidate.exists():
            return str(candidate)

    # Check for a previously downloaded Google Font at the requested weight
    cached = FONTS_DIR / f"{font_family.replace(' ', '')}-{weight}.ttf"
    if cached.exists():
        return str(cached)

    # Download from Google Fonts
    try:
        path = _download_google_font(font_family, weight=weight)
        return str(path)
    except Exception as exc:
        logger.warning("Could not resolve font '%s' weight %s (%s) — using Montserrat fallback", font_family, weight, exc)

    fallback = FONTS_DIR / "Montserrat-Regular.ttf"
    return str(fallback)


def _download_google_font(family: str, weight: int = 400) -> Path:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)

    css_url = (
        "https://fonts.googleapis.com/css2"
        f"?family={family.replace(' ', '+')}:wght@{weight}"
    )
    resp = requests.get(css_url, headers={"User-Agent": _GFONTS_UA}, timeout=10)
    resp.raise_for_status()

    ttf_urls = re.findall(r"url\((https://[^)]+\.ttf)\)", resp.text)
    if not ttf_urls:
        raise ValueError(f"No TTF URL in Google Fonts CSS for '{family}:{weight}'")

    font_bytes = requests.get(ttf_urls[0], timeout=30)
    font_bytes.raise_for_status()

    dest = FONTS_DIR / f"{family.replace(' ', '')}-{weight}.ttf"
    dest.write_bytes(font_bytes.content)
    logger.info("Cached Google Font: %s", dest.name)
    return dest
