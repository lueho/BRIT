from django.shortcuts import render
from django.views.generic import FormView, TemplateView

class FeedstockDefinitionView(TemplateView):
    template_name = 'feedstock_definition.html'
    
class CatchmentDefinitionView(TemplateView):
    template_name = 'catchment_definition.html'
        
    
