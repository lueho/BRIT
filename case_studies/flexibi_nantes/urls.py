from django.urls import path

from .views import (
    CultureListView,
    CultureCreateView,
    CultureDetailView,
    CultureUpdateView,
    CultureDeleteView,
    GreenhouseCreateView,
    GreenhouseGrowthCycleCreateView,
    GreenhouseDeleteView,
    GreenhouseDetailView,
    GreenhouseListView,
    GreenhouseUpdateView,
    UpdateGreenhouseGrowthCycleValuesView,
    GreenhousesMapView,
    NantesGreenhousesAPIView,
    GrowthCycleDetailView,
    GrowthCycleCreateView,
    GrowthCycleDeleteView,
    GrowthTimeStepSetModalUpdateView,
)

urlpatterns = [
    path('cultures/', CultureListView.as_view(), name='culture-list'),
    path('cultures/create/', CultureCreateView.as_view(), name='culture-create'),
    path('cultures/<int:pk>/', CultureDetailView.as_view(), name='culture-detail'),
    path('cultures/<int:pk>/update/', CultureUpdateView.as_view(), name='culture-update'),
    path('cultures/<int:pk>/delete/', CultureDeleteView.as_view(), name='culture-delete'),
    path('greenhouses/data/', NantesGreenhousesAPIView.as_view(), name='data.nantes_greenhouses'),
    path('greenhouses/map/', GreenhousesMapView.as_view(), name='NantesGreenhouses'),
    path('greenhouses/', GreenhouseListView.as_view(), name='greenhouse-list'),
    path('greenhouses/create/', GreenhouseCreateView.as_view(), name='greenhouse-create'),
    path('greenhouses/<int:pk>/', GreenhouseDetailView.as_view(), name='greenhouse-detail'),
    path('greenhouses/<int:pk>/update/', GreenhouseUpdateView.as_view(), name='greenhouse-update'),
    path('greenhouses/<int:pk>/delete', GreenhouseDeleteView.as_view(), name='greenhouse-delete'),
    path('greenhouses/<int:pk>/growth_cycles/add', GrowthCycleCreateView.as_view(), name='growthcycle-create'),
    path('greenhouses/<int:pk>/growth_cycles/<int:cycle_pk>/update/',
         UpdateGreenhouseGrowthCycleValuesView.as_view(), name='greenhouse_growth_cycle_update_values'),
    path('growthcycles/create_inline/', GreenhouseGrowthCycleCreateView.as_view(), name='growth_cycle_create_inline'),
    path('growthcycles/<int:pk>/', GrowthCycleDetailView.as_view(), name='growthcycle-detail'),
    path('growthcycles/<int:pk>/delete/', GrowthCycleDeleteView.as_view(), name='growthcycle-delete'),
    path('growthcycles/timesteps/<int:pk>/update', GrowthTimeStepSetModalUpdateView.as_view(), name='growth_cycle_timestep_update')
]
