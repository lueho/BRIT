from django.views.generic import TemplateView

from case_studies.flexibi_nantes.models import Greenhouse
from case_studies.soilcom.models import Collection


class SourcesExplorerView(TemplateView):
    template_name = "sources_explorer.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["collection_count"] = Collection.objects.filter(
            publication_status="published"
        ).count()
        context["greenhouse_count"] = Greenhouse.objects.filter(
            publication_status="published"
        ).count()
        return context


class SourcesListView(TemplateView):
    template_name = "sources_list.html"
