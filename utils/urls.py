from django.urls import include, path

from .views import (UtilsDashboardView)

urlpatterns = [
    path('dashboard/', UtilsDashboardView.as_view(), name='utils-dashboard'),
    path('properties/', include('utils.properties.urls')),
]
