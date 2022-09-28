from bootstrap_modal_forms.generic import BSModalReadView

from .models import Timestep


class TimestepModalDetailView(BSModalReadView):
    model = Timestep
    template_name = 'timestep_detail_modal.html'
