from django.views.generic import TemplateView

from sources.registry import get_source_domain_explorer_cards
from utils.views import BreadcrumbContextMixin


class SourcesExplorerView(BreadcrumbContextMixin, TemplateView):
    template_name = "sources_explorer.html"
    breadcrumb_module_label = "Sources"
    breadcrumb_page_title = "Sources"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source_domain_explorer_cards"] = get_source_domain_explorer_cards()
        return context
