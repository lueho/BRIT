"""Validation of atlas query parameters shared by the pages and the data API.

Anonymous visitors control these values, so nothing is trusted: years are
clamped to the years the atlas offers and region codes must look like region
codes before they reach a template, a cache key or a follow-up request URL.
"""

import re

from .map_selection import MAP_SELECTION_YEARS

MIN_ATLAS_YEAR = min(int(year) for year in MAP_SELECTION_YEARS)
MAX_ATLAS_YEAR = max(int(year) for year in MAP_SELECTION_YEARS)
# Years the database can meaningfully hold; anything else is a malformed request.
MIN_PLAUSIBLE_YEAR = 1900
MAX_PLAUSIBLE_YEAR = 2100
MAX_NUTS_LEVEL = 3

_COUNTRY = re.compile(r"[A-Za-z]{2}")
_NUTS_PREFIXES = re.compile(r"[A-Za-z0-9]{1,8}(,[A-Za-z0-9]{1,8}){0,15}")


def parse_year(raw, default):
    """Return ``raw`` as a plausible year, else ``default``."""
    try:
        year = int(raw)
    except (TypeError, ValueError):
        return default
    if MIN_PLAUSIBLE_YEAR <= year <= MAX_PLAUSIBLE_YEAR:
        return year
    return default


def parse_atlas_year(raw, default):
    """Return ``raw`` clamped to the atlas years; ``default`` if not an integer.

    Change overlays feed the years into cache keys, so they stay within the
    range the atlas offers instead of walking unbounded cache misses.
    """
    try:
        year = int(raw)
    except (TypeError, ValueError):
        return default
    return min(max(year, MIN_ATLAS_YEAR), MAX_ATLAS_YEAR)


def parse_nuts_level(raw, default=""):
    """Return a NUTS level (0-3) as a string, else ``default``."""
    try:
        level = int(raw)
    except (TypeError, ValueError):
        return default
    return str(level) if 0 <= level <= MAX_NUTS_LEVEL else default


def parse_country(raw, default):
    return raw if raw is not None and _COUNTRY.fullmatch(raw) else default


def parse_nuts_prefix(raw, default=""):
    return raw if raw is not None and _NUTS_PREFIXES.fullmatch(raw) else default
