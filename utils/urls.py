from django.urls import path

from .views import (PropertyListView, PropertyCreateView, PropertyDetailView, PropertyUpdateView,
                    PropertyModalDeleteView, PropertyUnitOptionsView, UnitListView, UnitCreateView, UnitDetailView,
                    UnitUpdateView, UnitModalDeleteView, UtilsDashboardView)

urlpatterns = [
    path('dashboard/', UtilsDashboardView.as_view(), name='utils-dashboard'),
    path('units/', UnitListView.as_view(), name='unit-list'),
    path('units/create/', UnitCreateView.as_view(), name='unit-create'),
    path('units/<int:pk>/', UnitDetailView.as_view(), name='unit-detail'),
    path('units/<int:pk>/update/', UnitUpdateView.as_view(), name='unit-update'),
    path('units/<int:pk>/delete/modal/', UnitModalDeleteView.as_view(), name='unit-delete-modal'),
    path('properties/', PropertyListView.as_view(), name='property-list'),
    path('properties/create/', PropertyCreateView.as_view(), name='property-create'),
    path('properties/<int:pk>/', PropertyDetailView.as_view(), name='property-detail'),
    path('properties/<int:pk>/update/', PropertyUpdateView.as_view(), name='property-update'),
    path('properties/<int:pk>/delete/modal/', PropertyModalDeleteView.as_view(), name='property-delete-modal'),
    path('properties/<int:pk>/unit-options/', PropertyUnitOptionsView.as_view(), name='property-unit-options'),
]
