from django.urls import path

from .views import SourcesListView

urlpatterns = [
    path('list/', SourcesListView.as_view(), name='sources-list'),
]
