from django.urls import include, path

from .router import router
from .views import (PropertyCreateView, PropertyDetailView, PropertyListView, PropertyModalDeleteView,
                    PropertyUnitOptionsView, PropertyUpdateView, UnitCreateView, UnitDetailView, UnitListView,
                    UnitModalDeleteView, UnitUpdateView)

urlpatterns = [
    path('', PropertyListView.as_view(), name='property-list'),
    path('create/', PropertyCreateView.as_view(), name='property-create'),
    path('<int:pk>/', PropertyDetailView.as_view(), name='property-detail'),
    path('<int:pk>/update/', PropertyUpdateView.as_view(), name='property-update'),
    path('<int:pk>/delete/modal/', PropertyModalDeleteView.as_view(), name='property-delete-modal'),
    path('<int:pk>/unit-options/', PropertyUnitOptionsView.as_view(), name='property-unit-options'),
    path('units/', UnitListView.as_view(), name='unit-list'),
    path('units/create/', UnitCreateView.as_view(), name='unit-create'),
    path('units/<int:pk>/', UnitDetailView.as_view(), name='unit-detail'),
    path('units/<int:pk>/update/', UnitUpdateView.as_view(), name='unit-update'),
    path('units/<int:pk>/delete/modal/', UnitModalDeleteView.as_view(), name='unit-delete-modal'),
    path('api/', include(router.urls)),
]
