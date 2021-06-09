from django.views.generic import ListView

from scenario_builder.models import GeoDataset
from .tables import DatasetTable


class BioresourceExplorerHomeView(ListView):
    queryset = GeoDataset.objects.all()
    template_name = 'bioresource_explorer_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = DatasetTable(data=self.queryset)
        context.update({'dataset_table': table})
        return context
