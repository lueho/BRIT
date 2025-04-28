from django.urls import path
from django.http import HttpResponse
from .views import GenericDatasetMapView
from . import urls as base_urls

def dummy_home(request):
    return HttpResponse('')

def dummy_sample_list_featured(request):
    return HttpResponse('')

urlpatterns = [
    path('', dummy_home, name='home'),
    path('sample-list-featured/', dummy_sample_list_featured, name='sample-list-featured'),
    *base_urls.urlpatterns[:30],
    path('geodatasets/<int:pk>/map/', GenericDatasetMapView.as_view(), name='geodataset-map'),
    *base_urls.urlpatterns[31:]
]
