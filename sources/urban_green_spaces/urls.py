from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path(
        "green_areas/map/",
        RedirectView.as_view(url="/maps/", permanent=True),
        name="HamburgGreenAreas",
    ),
]
