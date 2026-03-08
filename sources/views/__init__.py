from django.views.generic import TemplateView
from sources.greenhouses.selectors import published_greenhouse_count
from sources.waste_collection.selectors import published_collection_count


class SourcesExplorerView(TemplateView):
    template_name = "sources_explorer.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["collection_count"] = published_collection_count()
        context["greenhouse_count"] = published_greenhouse_count()
        return context


class SourcesListView(TemplateView):
    template_name = "sources_list.html"
