from django.urls import path

from .views import (
    GreenhouseCreateView,
    GreenhouseDeleteView,
    GreenhouseDetailView,
    GreenhouseListView,
    GreenhouseUpdateView,
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
]
