from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path(
        "green_areas/map/",
        RedirectView.as_view(
            url="/maps/hamburg/green_areas/map/",
            permanent=True,
            query_string=True,
        ),
    ),
]

__all__ = ["urlpatterns"]
