"""Client IP resolution behind Cloudflare and the Heroku router."""

import ipaddress
from functools import lru_cache

from django.conf import settings

# Cloudflare's published edge ranges (https://www.cloudflare.com/ips/).
# Override with the ``CLOUDFLARE_TRUSTED_PROXY_RANGES`` setting.
CLOUDFLARE_IP_RANGES = (
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
)


@lru_cache(maxsize=4)
def _networks(ranges):
    return tuple(ipaddress.ip_network(cidr) for cidr in ranges)


def _is_cloudflare_edge(ip):
    ranges = tuple(
        getattr(settings, "CLOUDFLARE_TRUSTED_PROXY_RANGES", CLOUDFLARE_IP_RANGES)
    )
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in network for network in _networks(ranges))


def get_client_ip(request):
    """Return the client address the proxy chain vouches for.

    Heroku's router appends the observed peer IP on the right of
    ``X-Forwarded-For``, so the LAST entry is the only one the client cannot
    control; earlier entries can be forged per request. When that peer is a
    Cloudflare edge, the request came through Cloudflare, which overwrites
    ``CF-Connecting-IP`` with the real client IP, so that header is trusted.
    From any other peer the Cloudflare headers are client-supplied and ignored.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    peer = (
        forwarded.split(",")[-1].strip()
        if forwarded
        else request.META.get("REMOTE_ADDR", "")
    )
    cf_ip = request.META.get("HTTP_CF_CONNECTING_IP", "").strip()
    if cf_ip and request.META.get("HTTP_CF_RAY") and _is_cloudflare_edge(peer):
        return cf_ip
    return peer
