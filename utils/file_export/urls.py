from django.urls import path

from .views import FilteredListFileExportProgressView

urlpatterns = [
    path('tasks/<str:task_id>/progress/', FilteredListFileExportProgressView.as_view(), name='file-export-progress'),
]
