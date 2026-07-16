from django.urls import path

from .views import (
    ExportModalView,
    FilteredListFileExportProgressView,
    UserExportDownloadView,
    UserExportListView,
)

urlpatterns = [
    path("export-modal/", ExportModalView.as_view(), name="export-modal"),
    path("exports/", UserExportListView.as_view(), name="user-export-list"),
    path(
        "exports/<int:pk>/download/",
        UserExportDownloadView.as_view(),
        name="user-export-download",
    ),
    path(
        "tasks/<str:task_id>/progress/",
        FilteredListFileExportProgressView.as_view(),
        name="file-export-progress",
    ),
]
