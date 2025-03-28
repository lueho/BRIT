from django.urls import include, path

from .views import (UtilsDashboardView)

urlpatterns = [
    path('dashboard/', UtilsDashboardView.as_view(), name='utils-dashboard'),
    path('file_export/', include('utils.file_export.urls')),
    path('properties/', include('utils.properties.urls')),
]
