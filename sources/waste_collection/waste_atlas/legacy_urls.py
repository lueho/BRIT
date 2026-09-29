"""Permanent redirects from the former ``/waste_collection/api/waste-atlas/`` mount.

Published links and third-party embeds point at the old paths. Pages moved to
``/waste_collection/waste-atlas/map/...`` and the data endpoints to
``/waste_collection/waste-atlas/api/...``.
"""

from django.urls import path
from django.views.generic import RedirectView

NEW_PREFIX = "/waste_collection/waste-atlas/"


def _redirect(url):
    return RedirectView.as_view(url=url, permanent=True, query_string=True)


urlpatterns = [
    path("map/", _redirect(f"{NEW_PREFIX}map/")),
    path("map/<path:path>", _redirect(f"{NEW_PREFIX}map/%(path)s")),
    path("", _redirect(f"{NEW_PREFIX}api/")),
    path("<path:path>", _redirect(f"{NEW_PREFIX}api/%(path)s")),
]

__all__ = ["urlpatterns"]
