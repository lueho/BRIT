from django.urls import path
from django.views.generic import RedirectView

from .views import SourcesExplorerView

urlpatterns = [
    path("explorer/", SourcesExplorerView.as_view(), name="sources-explorer"),
    path(
        "list/",
        RedirectView.as_view(pattern_name="sources-explorer", permanent=True),
        name="sources-list",
    ),
]
