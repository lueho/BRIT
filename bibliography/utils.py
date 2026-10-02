import string

import requests

_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20200101 Firefox/84.0",
    "Accept-Language": "en-GB,en;q=0.5",
    "Referer": "https://www.wikipedia.org",
    "DNT": "1",
}
_REQUEST_TIMEOUT = 10


def _is_success_status(status_code):
    return 200 <= status_code < 300


def check_url(url):
    clean_url = str(url or "").strip()
    if not clean_url:
        return False

    try:
        response = requests.head(
            clean_url,
            headers=_REQUEST_HEADERS,
            allow_redirects=True,
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        response = None
    else:
        if _is_success_status(response.status_code):
            return True

    get_response = None
    try:
        get_response = requests.get(
            clean_url,
            headers=_REQUEST_HEADERS,
            allow_redirects=True,
            timeout=_REQUEST_TIMEOUT,
            stream=True,
        )
        return _is_success_status(get_response.status_code)
    except requests.exceptions.RequestException:
        return False
    finally:
        if get_response is not None:
            get_response.close()


def find_wayback_snapshot_for_year(url, year):
    """Return the latest Wayback snapshot URL for *url* in *year*.

    If no snapshot exists in that exact year or the Wayback query fails,
    this returns ``None``.
    """

    cdx_endpoint = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": url,
        "from": f"{year}0101",
        "to": f"{year}1231",
        "output": "json",
        "fl": "timestamp,original,statuscode",
        "filter": "statuscode:200",
    }

    try:
        response = requests.get(
            cdx_endpoint,
            params=params,
            headers=_REQUEST_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json()
    except (requests.exceptions.RequestException, ValueError):
        return None

    if not rows:
        return None

    if isinstance(rows[0], list) and rows[0] and rows[0][0] == "timestamp":
        rows = rows[1:]

    if not rows:
        return None

    latest_timestamp = max(
        (
            row[0]
            for row in rows
            if isinstance(row, list)
            and len(row) >= 1
            and isinstance(row[0], str)
            and row[0]
        ),
        default=None,
    )
    if latest_timestamp is None:
        return None

    return f"https://web.archive.org/web/{latest_timestamp}/{url}"


def check_source_urls(params):
    pass


def generate_citation_key(source):
    """Return a disambiguated citation key for the given source.

    Persisted sources use the full author/year generator; unsaved sources
    fall back to a title/year base because their m2m authors are not
    populated yet. Colliding keys get an a/b/c/... suffix.
    """
    if source.pk:
        base = source.generate_abbreviation()
    else:
        base = source._base_abbreviation_without_authors()
    if not base:
        return base

    # Query the concrete model's manager: proxy managers like
    # WasteFlyer.objects filter by type, but citation keys share one column.
    existing = set(
        source._meta.concrete_model.objects.filter(citation_key__startswith=base)
        .exclude(pk=source.pk)
        .values_list("citation_key", flat=True)
    )
    if base not in existing:
        return base

    for letter in string.ascii_lowercase:
        candidate = f"{base}{letter}"
        if candidate not in existing:
            return candidate

    return base
