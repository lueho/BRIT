from django.shortcuts import render
from django.views.generic import TemplateView


class SourcesListView(TemplateView):
    template_name = 'sources-list.html'
