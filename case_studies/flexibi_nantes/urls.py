from django.urls import path

from .views import (
    GreenhouseCreateView,
    GreenhouseDeleteView,
    GreenhouseDetailView,
    GreenhouseListView,
    GreenhouseUpdateView,
    GreenhouseAddGrowthCycleView,
    GreenhouseRemoveGrowthCycleView,
    UpdateGreenhouseGrowthCycleValuesView,
    NantesGreenhousesView,
    NantesGreenhousesAPIView,
)

urlpatterns = [
    path('greenhouses/data/', NantesGreenhousesAPIView.as_view(), name='data.nantes_greenhouses'),
    path('greenhouse_map/', NantesGreenhousesView.as_view(), name='NantesGreenhouses'),
    path('greenhouses/', GreenhouseListView.as_view(), name='greenhouse_list'),
    path('greenhouses/create/', GreenhouseCreateView.as_view(), name='greenhouse_create'),
    path('greenhouses/<int:pk>/', GreenhouseDetailView.as_view(), name='greenhouse_detail'),
    path('greenhouses/<int:pk>/update', GreenhouseUpdateView.as_view(), name='greenhouse_update'),
    path('greenhouses/<int:pk>/delete', GreenhouseDeleteView.as_view(), name='greenhouse_delete'),
    path('greenhouses/<int:pk>/growth_cycles/add', GreenhouseAddGrowthCycleView.as_view(),
         name='greenhouse_add_growth_cycle'),
    path('greenhouses/<int:greenhouse_pk>/growth_cycles/<int:cycle_number>/remove',
         GreenhouseRemoveGrowthCycleView.as_view(),
         name='greenhouse_remove_growth_cycle'),
    path('greenhouses/<int:pk>/growth_cycles/<int:material_pk>/<int:component_pk>/update/',
         UpdateGreenhouseGrowthCycleValuesView.as_view(), name='greenhouse_growth_cycle_update_values'),
]
