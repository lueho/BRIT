from django.urls import include, path

from .views import UtilsExplorerView

urlpatterns = [
    path("explorer/", UtilsExplorerView.as_view(), name="utils-explorer"),
    path("file_export/", include("utils.file_export.urls")),
    path("properties/", include("utils.properties.urls")),
    path("object_management/", include("utils.object_management.urls")),
]
