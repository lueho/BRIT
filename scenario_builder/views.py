from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, CreateView, DeleteView
from rest_framework.views import APIView

from .forms import CatchmentForm
from .models import Catchment
from .serializers import CatchmentSerializer


class FeedstockDefinitionView(TemplateView):
    template_name = 'feedstock_definition.html'


class CatchmentDefinitionView(CreateView):
    template_name = 'catchment_definition.html'
    form_class = CatchmentForm
    success_url = reverse_lazy('catchment_view')


class CatchmentDeleteView(DeleteView):
    model = Catchment
    success_url = reverse_lazy('catchment_view')


# class CatchmentView(TemplateView):
# template_name = 'catchment_view.html'
# form_class = CatchmentForm
# success_url = reverse_lazy('catchment_view')

def catchmentView(request):
    catchment_names = Catchment.objects.all().values('name')

    return render(request, 'catchment_view.html', {'names': catchment_names})


def catchmentDelete(request):
    return redirect(catchmentView)


class CatchmentAPIView(APIView):

    def get(self, request):
        name = request.GET.get('name')
        qs = Catchment.objects.filter(name=name)

        serializer = CatchmentSerializer(qs, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)
