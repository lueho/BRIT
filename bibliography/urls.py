from django.urls import path

from . import views

urlpatterns = [
    path('sources/', views.SourceListView.as_view(), name='bib_source_list'),
    path('sources/create/', views.SourceCreateView.as_view(), name='bib_source_create'),
    path('sources/create/modal/', views.SourceModalCreateView.as_view(), name='bib_source_create_modal'),
    path('sources/<int:pk>/', views.SourceDetailView.as_view(), name='bib_source_detail'),
    path('sources/<int:pk>/modal/', views.SourceModalDetailView.as_view(), name='bib_source_detail_modal'),
    path('sources/<int:pk>/update/', views.SourceUpdateView.as_view(), name='bib_source_update'),
    path('sources/<int:pk>/update/modal/', views.SourceModalUpdateView.as_view(), name='bib_source_update_modal'),
    path('sources/<int:pk>/delete/modal/', views.SourceModalDeleteView.as_view(), name='bib_source_delete_modal'),
]
