from django.views.generic import TemplateView

from sources.registry import get_explorer_context


class SourcesExplorerView(TemplateView):
    template_name = "sources_explorer.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_explorer_context())
        return context


class SourcesListView(TemplateView):
    template_name = "sources_list.html"
