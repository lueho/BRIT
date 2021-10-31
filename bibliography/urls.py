from django.urls import path

from .views import (
    LiteratureSourceListView,
    LiteratureSourceCreateView,
    LiteratureSourceDetailView,
    LiteratureSourceUpdateView,
    LiteratureSourceDeleteView
)

urlpatterns = [
    path('sources/', LiteratureSourceListView.as_view(), name='bib_source_list'),
    path('sources/create/', LiteratureSourceCreateView.as_view(), name='bib_source_create'),
    path('sources/<int:pk>/', LiteratureSourceDetailView.as_view(), name='bib_source_detail'),
    path('sources/<int:pk>/update/', LiteratureSourceUpdateView.as_view(), name='bib_source_update'),
    path('sources/<int:pk>/delete/', LiteratureSourceDeleteView.as_view(), name='bib_source_delete'),
]
