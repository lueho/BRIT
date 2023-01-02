from django.views.generic import TemplateView


class SourcesListView(TemplateView):
    template_name = 'sources_list.html'
