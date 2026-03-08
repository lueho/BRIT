from django.urls import include, path
from django.views.generic import RedirectView

from .views import SourcesExplorerView

urlpatterns = [
    path("", include("sources.roadside_trees.urls")),
    path("explorer/", SourcesExplorerView.as_view(), name="sources-explorer"),
    path(
        "list/",
        RedirectView.as_view(pattern_name="sources-explorer", permanent=True),
        name="sources-list",
    ),
]
