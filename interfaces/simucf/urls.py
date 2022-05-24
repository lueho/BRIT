from django.urls import path

from .views import download_input_file

urlpatterns = [
    path('download_inputfile/', download_input_file, name='simucf-inputfile'),
]
