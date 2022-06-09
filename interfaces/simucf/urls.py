from django.urls import path

from .views import SimuCFFormView

urlpatterns = [
    path('form/', SimuCFFormView.as_view(), name='simucf-form'),
]
