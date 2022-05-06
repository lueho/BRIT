from django.urls import path

from . import views

urlpatterns = [
    path('', views.BibliographyDashboardView.as_view(), name='bibliography-dashboard'),
    path('authors/', views.AuthorListView.as_view(), name='author-list'),
    path('authors/create/', views.AuthorCreateView.as_view(), name='author-create'),
    path('authors/create/modal/', views.AuthorModalCreateView.as_view(), name='author-create-modal'),
    path('authors/<int:pk>/', views.AuthorDetailView.as_view(), name='author-detail'),
    path('authors/<int:pk>/modal/', views.AuthorModalDetailView.as_view(), name='author-detail-modal'),
    path('authors/<int:pk>/update/', views.AuthorUpdateView.as_view(), name='author-update'),
    path('authors/<int:pk>/update/modal/', views.AuthorModalUpdateView.as_view(), name='author-update-modal'),
    path('authors/<int:pk>/delete/modal/', views.AuthorModalDeleteView.as_view(), name='author-delete-modal'),
    path('licences/', views.LicenceListView.as_view(), name='licence-list'),
    path('licences/create/', views.LicenceCreateView.as_view(), name='licence-create'),
    path('licences/create/modal/', views.LicenceModalCreateView.as_view(), name='licence-create-modal'),
    path('licences/<int:pk>/', views.LicenceDetailView.as_view(), name='licence-detail'),
    path('licences/<int:pk>/modal/', views.LicenceModalDetailView.as_view(), name='licence-detail-modal'),
    path('licences/<int:pk>/update/', views.LicenceUpdateView.as_view(), name='licence-update'),
    path('licences/<int:pk>/update/modal/', views.LicenceModalUpdateView.as_view(), name='licence-update-modal'),
    path('licences/<int:pk>/delete/modal/', views.LicenceModalDeleteView.as_view(), name='licence-delete-modal'),
    path('sources/', views.SourceListView.as_view(), name='source-list'),
    path('sources/create/', views.SourceCreateView.as_view(), name='source-create'),
    path('sources/create/modal/', views.SourceModalCreateView.as_view(), name='source-create-modal'),
    path('sources/<int:pk>/', views.SourceDetailView.as_view(), name='source-detail'),
    path('sources/<int:pk>/modal/', views.SourceModalDetailView.as_view(), name='source-detail-modal'),
    path('sources/<int:pk>/update/', views.SourceUpdateView.as_view(), name='source-update'),
    path('sources/<int:pk>/update/modal/', views.SourceModalUpdateView.as_view(), name='source-update-modal'),
    path('sources/<int:pk>/delete/modal/', views.SourceModalDeleteView.as_view(), name='source-delete-modal'),
]
