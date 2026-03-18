from django.urls import include, path
from django.views.generic import RedirectView

from .registry import get_hub_source_domain_plugins
from .views import SourcesExplorerView

urlpatterns = [
    *[
        path(plugin.mount_path, include(plugin.urlconf))
        for plugin in get_hub_source_domain_plugins()
    ],
    path("explorer/", SourcesExplorerView.as_view(), name="sources-explorer"),
    path(
        "list/",
        RedirectView.as_view(pattern_name="sources-explorer", permanent=True),
        name="sources-list",
    ),
]
