import ipaddress
import socket
import string
from urllib.parse import urljoin, urlsplit

import requests

_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20200101 Firefox/84.0",
    "Accept-Language": "en-GB,en;q=0.5",
    "Referer": "https://www.wikipedia.org",
    "DNT": "1",
}
_REQUEST_TIMEOUT = 10


_MAX_REDIRECTS = 10
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_ALLOWED_SCHEMES = frozenset({"http", "https"})
# An environment proxy would resolve hostnames itself, bypassing the
# destination check, so URL checks always connect directly.
_NO_PROXIES = {"http": None, "https": None, "all": None}


def _is_success_status(status_code):
    return 200 <= status_code < 300


def _is_public_http_url(url):
    """Return True if *url* is http(s) and its host resolves only to public IPs.

    Guards server-side URL checks against requests to loopback, private,
    link-local (cloud metadata) and other non-global addresses.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme.lower() not in _ALLOWED_SCHEMES or not parts.hostname:
        return False
    try:
        infos = socket.getaddrinfo(
            parts.hostname,
            port or (443 if parts.scheme.lower() == "https" else 80),
            proto=socket.IPPROTO_TCP,
        )
    except (OSError, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0].split("%", 1)[0])
        except ValueError:
            return False
        if not address.is_global or address.is_multicast:
            return False
    return True


def _request_public(method, url, **kwargs):
    """Send *method* to *url*, following redirects only to public http(s) hosts.

    Returns the final response, or None if any hop targets a non-public
    destination or the redirect limit is exceeded.
    """
    for _ in range(_MAX_REDIRECTS + 1):
        if not _is_public_http_url(url):
            return None
        response = method(
            url,
            headers=_REQUEST_HEADERS,
            allow_redirects=False,
            timeout=_REQUEST_TIMEOUT,
            proxies=_NO_PROXIES,
            **kwargs,
        )
        location = response.headers.get("Location")
        if response.status_code not in _REDIRECT_STATUSES or not location:
            return response
        response.close()
        try:
            url = urljoin(url, location)
        except ValueError:
            return None
    return None


def check_url(url):
    clean_url = str(url or "").strip()
    if not clean_url:
        return False

    try:
        response = _request_public(requests.head, clean_url)
    except requests.exceptions.RequestException:
        response = None
    else:
        if response is not None and _is_success_status(response.status_code):
            return True

    get_response = None
    try:
        get_response = _request_public(requests.get, clean_url, stream=True)
        return get_response is not None and _is_success_status(get_response.status_code)
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
