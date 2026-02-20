import requests

_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20200101 Firefox/84.0",
    "Accept-Language": "en-GB,en;q=0.5",
    "Referer": "https://www.wikipedia.org",
    "DNT": "1",
}


def check_url(url):
    try:
        response = requests.head(url, headers=_REQUEST_HEADERS, allow_redirects=True)
    except requests.exceptions.RequestException:
        return False
    else:
        if response.status_code == 405:
            response = requests.get(url, headers=_REQUEST_HEADERS, allow_redirects=True)
        return response.status_code == 200


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
