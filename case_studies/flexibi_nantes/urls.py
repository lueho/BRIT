from django.urls import include, path
from django.views.generic import RedirectView

from .rounter import router
from .views import (CultureCreateView, CultureModalDeleteView, CultureDetailView, CultureListView, CultureUpdateView,
                    GreenhouseCreateView, GreenhouseModalDeleteView, GreenhouseDetailView,
                    GreenhouseGrowthCycleCreateView,
                    GreenhouseListView, GreenhouseUpdateView, GreenhousesMapView, GrowthCycleCreateView,
                    GrowthCycleModalDeleteView, GrowthCycleDetailView, GrowthCycleUpdateView,
                    GrowthTimeStepSetModalUpdateView,
                    NantesGreenhousesCatchmentAutocompleteView, NantesGreenhousesListFileExportProgressView,
                    NantesGreenhousesListFileExportView, UpdateGreenhouseGrowthCycleValuesView)

urlpatterns = [
    path('cultures/', CultureListView.as_view(), name='culture-list'),
    path('cultures/create/', CultureCreateView.as_view(), name='culture-create'),
    path('cultures/<int:pk>/', CultureDetailView.as_view(), name='culture-detail'),
    path('cultures/<int:pk>/update/', CultureUpdateView.as_view(), name='culture-update'),
    path('cultures/<int:pk>/delete/modal/', CultureModalDeleteView.as_view(), name='culture-delete-modal'),
    path('greenhouses/map/', GreenhousesMapView.as_view(), name='NantesGreenhouses'),
    path('roadside_trees/export/', NantesGreenhousesListFileExportView.as_view(), name='nantesgreenhouses-export'),
    path('roadside_trees/export/<str:task_id>/progress/', NantesGreenhousesListFileExportProgressView.as_view(),
         name='nantesgreenhouses-export-progress'),
    path('greenhouses/catchment_autocomplete/', NantesGreenhousesCatchmentAutocompleteView.as_view(),
         name='nantesgreenhouses-catchment-autocomplete'),
    path('greenhouses/', GreenhouseListView.as_view(), name='greenhouse-list'),
    path('greenhouses/create/', GreenhouseCreateView.as_view(), name='greenhouse-create'),
    path('greenhouses/<int:pk>/', GreenhouseDetailView.as_view(), name='greenhouse-detail'),
    path('greenhouses/<int:pk>/update/', GreenhouseUpdateView.as_view(), name='greenhouse-update'),
    path('greenhouses/<int:pk>/delete/modal/', GreenhouseModalDeleteView.as_view(), name='greenhouse-delete-modal'),
    path('greenhouses/<int:pk>/growth_cycles/add', GrowthCycleCreateView.as_view(), name='growthcycle-create-modal'),
    path('greenhouses/<int:pk>/growth_cycles/<int:cycle_pk>/update/',
         UpdateGreenhouseGrowthCycleValuesView.as_view(), name='greenhouse_growth_cycle_update_values'),
    path('growthcycles/create_inline/', GreenhouseGrowthCycleCreateView.as_view(), name='growth_cycle_create_inline'),
    path('growthcycles/<int:pk>/', GrowthCycleDetailView.as_view(), name='greenhousegrowthcycle-detail'),
    path('growthcycles/<int:pk>/update/', GrowthCycleUpdateView.as_view(), name='greenhousegrowthcycle-update'),
    path('growthcycles/<int:pk>/delete/', GrowthCycleModalDeleteView.as_view(), name='greenhousegrowthcycle-delete-modal'),
    path('growthcycles/timesteps/<int:pk>/update/modal/', GrowthTimeStepSetModalUpdateView.as_view(), name='greenhousegrowthcycle-timestep-update-modal'),
    path('api/', include(router.urls)),
]
