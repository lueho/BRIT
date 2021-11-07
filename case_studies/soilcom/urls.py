from django.urls import path

from . import views

urlpatterns = [
    path('collectors/', views.CollectorListView.as_view(), name='collector_list'),
    path('collectors/create/', views.CollectorCreateView.as_view(), name='collector_create'),
    path('collectors/create/modal/', views.CollectorModalCreateView.as_view(), name='collector_create_modal'),
    path('collectors/<int:pk>/', views.CollectorDetailView.as_view(), name='collector_detail'),
    path('collectors/<int:pk>/modal/', views.CollectorModalDetailView.as_view(), name='collector_detail_modal'),
    path('collectors/<int:pk>/update/', views.CollectorUpdateView.as_view(), name='collector_update'),
    path('collectors/<int:pk>/update/modal/', views.CollectorModalUpdateView.as_view(), name='collector_update_modal'),
    path('collectors/<int:pk>/delete/modal/', views.CollectorModalDeleteView.as_view(), name='collector_delete_modal'),
]
