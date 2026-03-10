from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path(
        "roadside_trees/map/",
        RedirectView.as_view(
            url="/sources/roadside_trees/map/",
            permanent=True,
            query_string=True,
        ),
    ),
    path(
        "roadside_trees/map/iframe/",
        RedirectView.as_view(
            url="/sources/roadside_trees/map/iframe/",
            permanent=True,
            query_string=True,
        ),
    ),
    path(
        "roadside_trees/export/",
        RedirectView.as_view(
            url="/sources/roadside_trees/export/",
            permanent=True,
            query_string=True,
        ),
    ),
    path(
        "roadside_trees/catchment_autocomplete/",
        RedirectView.as_view(
            url="/sources/roadside_trees/catchment_autocomplete/",
            permanent=True,
            query_string=True,
        ),
    ),
    path(
        "green_areas/map/",
        RedirectView.as_view(
            url="/sources/green_areas/map/",
            permanent=True,
            query_string=True,
        ),
    ),
    path(
        "api/",
        RedirectView.as_view(
            url="/sources/api/",
            permanent=True,
            query_string=True,
        ),
    ),
    path(
        "api/<path:path>",
        RedirectView.as_view(
            url="/sources/api/%(path)s",
            permanent=True,
            query_string=True,
        ),
    ),
]

__all__ = ["urlpatterns"]
