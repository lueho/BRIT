from django.urls import path

from .views import PropertyUnitOptionsView

urlpatterns = [
    path('properties/<int:pk>/unit-options/', PropertyUnitOptionsView.as_view(), name='property-unit-options'),
]
