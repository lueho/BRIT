from django.urls import path

from .views import TimestepModalDetailView

urlpatterns = [
    path(
        "timesteps/<int:pk>/modal/",
        TimestepModalDetailView.as_view(),
        name="timestep-detail-modal",
    ),
]
