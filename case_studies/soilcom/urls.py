from django.urls import path

from . import views

urlpatterns = [
    path('collectors/', views.CollectorListView.as_view(), name='collector_list'),
    path('collectors/create/', views.CollectorCreateView.as_view(), name='collector_create'),
]
