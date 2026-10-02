"""URL convention tests.

POST-accepting routes without a trailing slash are silently broken for
clients that use the canonical slashed form: Django's APPEND_SLASH
middleware answers with a redirect and the POST body is dropped. All
routes therefore end with '/', except file-like paths (sitemap.xml,
robots.txt, *.geojson) and catch-all redirect patterns.
"""

from django.test import SimpleTestCase
from django.urls import get_resolver
from django.urls.resolvers import RoutePattern


def _iter_routes(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if hasattr(pattern, "url_patterns"):
            yield from _iter_routes(pattern.url_patterns, route)
        elif isinstance(pattern.pattern, RoutePattern):
            # Only path() routes; re_path()/DRF router routes carry their own
            # regex anchors and slash handling.
            yield route


class TrailingSlashConventionTests(SimpleTestCase):
    def test_all_non_file_routes_end_with_trailing_slash(self):
        bad = []
        for route in _iter_routes(get_resolver().url_patterns):
            if not route or route.endswith("/"):
                continue
            last_segment = route.rsplit("/", 1)[-1]
            if (
                "." in last_segment
                or last_segment.startswith("<path:")
                or last_segment.startswith("<drf_format_suffix")
            ):
                continue
            bad.append(route)

        self.assertEqual(
            bad,
            [],
            "These routes lack a trailing slash; POSTs to the slashed form "
            "lose their body on the APPEND_SLASH redirect.",
        )
