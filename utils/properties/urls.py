from django.urls import include, path

from .router import router
from .views import (PropertyCreateView, PropertyDetailView, PropertyListView, PropertyModalDeleteView,
                    PropertyUnitCreateView, PropertyUnitDetailView, PropertyUnitListView, PropertyUnitModalDeleteView,
                    PropertyUnitOptionsView, PropertyUnitUpdateView, PropertyUpdateView)

urlpatterns = [
    path('', PropertyListView.as_view(), name='property-list'),
    path('create/', PropertyCreateView.as_view(), name='property-create'),
    path('<int:pk>/', PropertyDetailView.as_view(), name='property-detail'),
    path('<int:pk>/update/', PropertyUpdateView.as_view(), name='property-update'),
    path('<int:pk>/delete/modal/', PropertyModalDeleteView.as_view(), name='property-delete-modal'),
    path('<int:pk>/propertyunit-options/', PropertyUnitOptionsView.as_view(), name='property-unit-options'),
    path('propertyunits/', PropertyUnitListView.as_view(), name='propertyunit-list'),
    path('propertyunits/create/', PropertyUnitCreateView.as_view(), name='propertyunit-create'),
    path('propertyunits/<int:pk>/', PropertyUnitDetailView.as_view(), name='propertyunit-detail'),
    path('propertyunits/<int:pk>/update/', PropertyUnitUpdateView.as_view(), name='propertyunit-update'),
    path('propertyunits/<int:pk>/delete/modal/', PropertyUnitModalDeleteView.as_view(),
         name='propertyunit-delete-modal'),
    path('api/', include(router.urls)),
]
