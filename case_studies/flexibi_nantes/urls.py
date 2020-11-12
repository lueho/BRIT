from django.urls import path

from .views import (
    NantesGreenhousesView,
    NantesGreenhousesAPIView,
)

urlpatterns = [
    path('greenhouses/data', NantesGreenhousesAPIView.as_view(), name='data.nantes_greenhouses'),
    path('greenhouses/', NantesGreenhousesView.as_view(), name='NantesGreenhouses'),
]
