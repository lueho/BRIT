from django.urls import path

from . import views

urlpatterns = [
    path('sources/', views.SourceListView.as_view(), name='source-list'),
    path('sources/create/', views.SourceCreateView.as_view(), name='source-create'),
    path('sources/create/modal/', views.SourceModalCreateView.as_view(), name='source-create-modal'),
    path('sources/<int:pk>/', views.SourceDetailView.as_view(), name='source-detail'),
    path('sources/<int:pk>/modal/', views.SourceModalDetailView.as_view(), name='source-detail-modal'),
    path('sources/<int:pk>/update/', views.SourceUpdateView.as_view(), name='source-update'),
    path('sources/<int:pk>/update/modal/', views.SourceModalUpdateView.as_view(), name='source-update-modal'),
    path('sources/<int:pk>/delete/modal/', views.SourceModalDeleteView.as_view(), name='source-delete-modal'),
]
