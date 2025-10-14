from django.urls import path

from .views import ExportModalView, FilteredListFileExportProgressView

urlpatterns = [
    path('export-modal/', ExportModalView.as_view(), name='export-modal'),
    path('tasks/<str:task_id>/progress/', FilteredListFileExportProgressView.as_view(), name='file-export-progress'),
]
