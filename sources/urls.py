from django.urls import path
from django.views.generic import RedirectView

from .views import SourcesListView

urlpatterns = [
    path(
        "explorer/",
        RedirectView.as_view(pattern_name="sources-list", permanent=False),
        name="sources-explorer",
    ),
    path("list/", SourcesListView.as_view(), name="sources-list"),
]
