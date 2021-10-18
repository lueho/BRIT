from django.views.generic import ListView

from scenario_builder.models import GeoDataset


class MapsListView(ListView):
    queryset = GeoDataset.objects.all()
    template_name = 'maps_list.html'
