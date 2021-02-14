from django.views.generic import ListView

from scenario_builder.models import GeoDataset


class BioresourceExplorerHomeView(ListView):
    queryset = GeoDataset.objects.all()
    template_name = 'bioresource_explorer_home.html'
