from utils.object_management.views import UserCreatedObjectModalDetailView

from .models import Timestep


class TimestepModalDetailView(UserCreatedObjectModalDetailView):
    model = Timestep
    template_name = "timestep_detail_modal.html"
