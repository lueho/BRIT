"""Throttling classes for the maps GeoJSON endpoints.

The public GeoJSON endpoints serve large, expensive payloads (some region
geometries are several megabytes). Aggressive crawlers hammer these endpoints
from a whole network block rather than a single address, so a plain per-IP
``AnonRateThrottle`` is ineffective: every request lands in a different bucket.

``GeoJSONAnonThrottle`` instead buckets anonymous clients by their network
prefix (``/24`` for IPv4, ``/64`` for IPv6 by default) so a distributed crawler
sharing a subnet is rate limited as a single client. Authenticated users are not
affected (``AnonRateThrottle`` only applies to anonymous requests).

The prefix lengths can be tuned per deployment via the
``GEOJSON_THROTTLE_IPV4_PREFIX`` / ``GEOJSON_THROTTLE_IPV6_PREFIX`` settings (for
example, loosened on a network where many real users share a CGNAT block).
"""

import ipaddress

from django.conf import settings
from rest_framework.throttling import AnonRateThrottle

DEFAULT_IPV4_PREFIX = 24
DEFAULT_IPV6_PREFIX = 64

# Single shared bucket for clients we cannot identify, so a spoofed or malformed
# ``X-Forwarded-For`` header cannot be used to mint unlimited throttle buckets
# (which would both bypass the limit and bloat the cache).
UNKNOWN_IDENT = "unknown"


def get_subnet_ident(ip: str | None) -> str:
    """Return the network prefix for ``ip`` used as the throttle bucket.

    IPv4 addresses are grouped into ``/24`` networks and IPv6 addresses into
    ``/64`` networks (configurable via settings). ``ip`` may be a comma-joined
    ``X-Forwarded-For`` chain, in which case the first (client) entry is used.
    Returns a single shared sentinel for values that cannot be parsed as an IP
    address so unparseable input does not create per-request buckets.
    """
    if not ip:
        return UNKNOWN_IDENT

    # DRF's get_ident may return a comma-joined X-Forwarded-For chain; the
    # left-most entry is the originating client.
    candidate = ip.split(",")[0].strip()
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return UNKNOWN_IDENT

    if address.version == 4:
        prefix = getattr(settings, "GEOJSON_THROTTLE_IPV4_PREFIX", DEFAULT_IPV4_PREFIX)
    else:
        prefix = getattr(settings, "GEOJSON_THROTTLE_IPV6_PREFIX", DEFAULT_IPV6_PREFIX)

    network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
    return str(network)


class GeoJSONAnonThrottle(AnonRateThrottle):
    """Subnet-aware anonymous rate limit for GeoJSON endpoints."""

    scope = "geojson_anon"

    def get_cache_key(self, request, view):
        # Only throttle anonymous requests; authenticated users are unaffected.
        if request.user and request.user.is_authenticated:
            return None

        ident = get_subnet_ident(self.get_ident(request))
        return self.cache_format % {"scope": self.scope, "ident": ident}
