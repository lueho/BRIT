"""URL configuration for the processes module.

Provides comprehensive URL routing for all CRUD operations following BRIT patterns.
"""

from django.urls import include, path

from . import views
from .router import router

app_name = "processes"

urlpatterns = [
    # Dashboard
    path("dashboard/", views.ProcessDashboardView.as_view(), name="dashboard"),

    # ProcessCategory URLs
    path(
        "categories/",
        views.ProcessCategoryPublishedListView.as_view(),
        name="processcategory-list",
    ),
    path(
        "categories/user/",
        views.ProcessCategoryPrivateListView.as_view(),
        name="processcategory-list-owned",
    ),
    path(
        "categories/create/",
        views.ProcessCategoryCreateView.as_view(),
        name="processcategory-create",
    ),
    path(
        "categories/create/modal/",
        views.ProcessCategoryModalCreateView.as_view(),
        name="processcategory-create-modal",
    ),
    path(
        "categories/<int:pk>/",
        views.ProcessCategoryDetailView.as_view(),
        name="processcategory-detail",
    ),
    path(
        "categories/<int:pk>/modal/",
        views.ProcessCategoryModalDetailView.as_view(),
        name="processcategory-detail-modal",
    ),
    path(
        "categories/<int:pk>/update/",
        views.ProcessCategoryUpdateView.as_view(),
        name="processcategory-update",
    ),
    path(
        "categories/<int:pk>/update/modal/",
        views.ProcessCategoryModalUpdateView.as_view(),
        name="processcategory-update-modal",
    ),
    path(
        "categories/<int:pk>/delete/modal/",
        views.ProcessCategoryModalDeleteView.as_view(),
        name="processcategory-delete-modal",
    ),
    path(
        "categories/autocomplete/",
        views.ProcessCategoryAutocompleteView.as_view(),
        name="processcategory-autocomplete",
    ),
    path(
        "categories/options/",
        views.ProcessCategoryOptions.as_view(),
        name="processcategory-options",
    ),

    # Process URLs
    path(
        "list/",
        views.ProcessPublishedFilterView.as_view(),
        name="process-list",
    ),
    path(
        "list/user/",
        views.ProcessPrivateFilterView.as_view(),
        name="process-list-owned",
    ),
    path(
        "create/",
        views.ProcessCreateView.as_view(),
        name="process-create",
    ),
    path(
        "create/modal/",
        views.ProcessModalCreateView.as_view(),
        name="process-create-modal",
    ),
    path(
        "<int:pk>/",
        views.ProcessDetailView.as_view(),
        name="process-detail",
    ),
    path(
        "<int:pk>/modal/",
        views.ProcessModalDetailView.as_view(),
        name="process-detail-modal",
    ),
    path(
        "<int:pk>/update/",
        views.ProcessUpdateView.as_view(),
        name="process-update",
    ),
    path(
        "<int:pk>/delete/modal/",
        views.ProcessModalDeleteView.as_view(),
        name="process-delete-modal",
    ),
    path(
        "<int:pk>/add-material/",
        views.ProcessAddMaterialView.as_view(),
        name="process-add-material",
    ),
    path(
        "<int:pk>/add-parameter/",
        views.ProcessAddParameterView.as_view(),
        name="process-add-parameter",
    ),
    path(
        "autocomplete/",
        views.ProcessAutocompleteView.as_view(),
        name="process-autocomplete",
    ),

    # API endpoints
    path("api/", include(router.urls)),
]
