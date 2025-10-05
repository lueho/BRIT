"""Production views for the processes module.

Provides complete CRUD operations for all process-related models following
BRIT conventions and patterns from utils.object_management.views.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, TemplateView
from extra_views import CreateWithInlinesView

from utils.object_management.views import (
    OwnedObjectModelSelectOptionsView,
    PrivateObjectFilterView,
    PrivateObjectListView,
    PublishedObjectFilterView,
    PublishedObjectListView,
    ReviewObjectFilterView,
    ReviewObjectListMixin,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectCreateWithInlinesView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
    UserCreatedObjectUpdateWithInlinesView,
)
from utils.views import NextOrSuccessUrlMixin

from .filters import ProcessFilter
from .forms import (
    ProcessAddMaterialForm,
    ProcessAddParameterForm,
    ProcessCategoryModalModelForm,
    ProcessCategoryModelForm,
    ProcessInfoResourceInline,
    ProcessLinkInline,
    ProcessMaterialInline,
    ProcessModalModelForm,
    ProcessModelForm,
    ProcessOperatingParameterInline,
    ProcessReferenceInline,
)
from .models import (
    Process,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
    ProcessReference,
)

# Temporary mock data for backward compatibility with closecycle module
# TODO: Remove when closecycle is updated to use real Process model
MOCK_PROCESS_TYPES = [
    {"id": 1, "name": "Anaerobic Digestion", "category": "Biochemical"},
    {"id": 2, "name": "Gasification", "category": "Thermochemical"},
    {"id": 3, "name": "Pyrolysis", "category": "Thermochemical"},
    {"id": 4, "name": "Composting", "category": "Biochemical"},
    {"id": 5, "name": "Hydrothermal Processing", "category": "Thermochemical"},
    {"id": 12, "name": "Pulping", "category": "Physicochemical"},
]

# ==============================================================================
# Helper Views
# ==============================================================================


class ReviewObjectListView(ReviewObjectListMixin, ListView):
    """
    List view for objects in review (for moderators).
    Combines ReviewObjectListMixin with ListView functionality.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "list_type": self.list_type,
                "scope": "review",
            }
        )
        return context

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append("simple_list_card.html")
        return template_names


# ==============================================================================
# Dashboard
# ==============================================================================


class ProcessDashboardView(TemplateView):
    """Main dashboard for the processes module."""

    template_name = "processes/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistics
        context["total_processes"] = Process.objects.filter(
            publication_status="published"
        ).count()
        context["total_categories"] = ProcessCategory.objects.filter(
            publication_status="published"
        ).count()

        # Recent processes
        context["recent_processes"] = (
            Process.objects.filter(publication_status="published")
            .select_related("owner")
            .prefetch_related("categories")[:5]
        )

        # Categories with process counts
        context["categories_with_counts"] = (
            ProcessCategory.objects.filter(publication_status="published")
            .annotate(process_count=Count("processes"))
            .order_by("-process_count")[:10]
        )

        # User's private processes if authenticated
        if self.request.user.is_authenticated:
            context["my_processes"] = Process.objects.filter(
                owner=self.request.user
            ).order_by("-lastmodified_at")[:5]

        return context


# ==============================================================================
# ProcessCategory CRUD
# ==============================================================================


class ProcessCategoryCreateView(UserCreatedObjectCreateView):
    """Create a new ProcessCategory."""

    model = ProcessCategory
    form_class = ProcessCategoryModelForm
    template_name = "processes/processcategory_form.html"
    permission_required = "processes.add_processcategory"

    def get_success_url(self):
        return reverse(
            "processes:processcategory-detail", kwargs={"pk": self.object.pk}
        )


class ProcessCategoryModalCreateView(UserCreatedObjectModalCreateView):
    """Create a new ProcessCategory in a modal dialog."""

    model = ProcessCategory
    form_class = ProcessCategoryModalModelForm
    permission_required = "processes.add_processcategory"


class ProcessCategoryPublishedListView(PublishedObjectListView):
    """List published ProcessCategory objects."""

    model = ProcessCategory
    template_name = "processes/processcategory_list.html"
    dashboard_url = reverse_lazy("processes:dashboard")
    context_object_name = "categories"
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().annotate(process_count=Count("processes"))


class ProcessCategoryPrivateListView(PrivateObjectListView):
    """List user's private ProcessCategory objects."""

    model = ProcessCategory
    template_name = "processes/processcategory_list.html"
    dashboard_url = reverse_lazy("processes:dashboard")
    context_object_name = "categories"
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().annotate(process_count=Count("processes"))


class ProcessCategoryReviewListView(ReviewObjectListView):
    """List ProcessCategory objects in review status for moderators."""

    model = ProcessCategory
    template_name = "processes/processcategory_list.html"
    dashboard_url = reverse_lazy("processes:dashboard")
    context_object_name = "categories"
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().annotate(process_count=Count("processes"))


class ProcessCategoryDetailView(UserCreatedObjectDetailView):
    """Display ProcessCategory details."""

    model = ProcessCategory
    template_name = "processes/processcategory_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get processes in this category
        context["processes"] = (
            self.object.processes.filter(publication_status="published")
            .select_related("owner")
            .prefetch_related("categories")
        )
        return context


class ProcessCategoryModalDetailView(UserCreatedObjectModalDetailView):
    """Display ProcessCategory details in a modal."""

    model = ProcessCategory


class ProcessCategoryUpdateView(UserCreatedObjectUpdateView):
    """Update a ProcessCategory."""

    model = ProcessCategory
    form_class = ProcessCategoryModelForm
    template_name = "processes/processcategory_form.html"

    def get_success_url(self):
        return reverse(
            "processes:processcategory-detail", kwargs={"pk": self.object.pk}
        )


class ProcessCategoryModalUpdateView(UserCreatedObjectModalUpdateView):
    """Update a ProcessCategory in a modal dialog."""

    model = ProcessCategory
    form_class = ProcessCategoryModalModelForm


class ProcessCategoryModalDeleteView(UserCreatedObjectModalDeleteView):
    """Delete a ProcessCategory."""

    model = ProcessCategory


class ProcessCategoryAutocompleteView(UserCreatedObjectAutocompleteView):
    """Autocomplete view for ProcessCategory selection."""

    model = ProcessCategory
    search_lookups = ["name__icontains"]


class ProcessCategoryOptions(OwnedObjectModelSelectOptionsView):
    """Provide ProcessCategory options for select fields."""

    model = ProcessCategory


# ==============================================================================
# Process CRUD
# ==============================================================================


class ProcessCreateView(UserCreatedObjectCreateWithInlinesView):
    """Create a new Process with related objects."""

    model = Process
    form_class = ProcessModelForm
    template_name = "processes/process_form.html"
    permission_required = "processes.add_process"
    inlines = [
        ProcessMaterialInline,
        ProcessOperatingParameterInline,
        ProcessLinkInline,
        ProcessInfoResourceInline,
        ProcessReferenceInline,
    ]

    def get_success_url(self):
        return reverse("processes:process-detail", kwargs={"pk": self.object.pk})


class ProcessModalCreateView(UserCreatedObjectModalCreateView):
    """Create a new Process in a modal dialog."""

    model = Process
    form_class = ProcessModalModelForm
    permission_required = "processes.add_process"


class ProcessPublishedFilterView(PublishedObjectFilterView):
    """List published Process objects with filtering."""

    model = Process
    template_name = "processes/process_list.html"
    dashboard_url = reverse_lazy("processes:dashboard")
    context_object_name = "processes"
    filterset_class = ProcessFilter
    paginate_by = 20

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("owner", "parent")
            .prefetch_related("categories", "process_materials__material")
        )


class ProcessPrivateFilterView(PrivateObjectFilterView):
    """List user's private Process objects with filtering."""

    model = Process
    template_name = "processes/process_list.html"
    dashboard_url = reverse_lazy("processes:dashboard")
    context_object_name = "processes"
    filterset_class = ProcessFilter
    paginate_by = 20

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("owner", "parent")
            .prefetch_related("categories", "process_materials__material")
        )


class ProcessReviewFilterView(ReviewObjectFilterView):
    """List Process objects in review status for moderators."""

    model = Process
    template_name = "processes/process_list.html"
    dashboard_url = reverse_lazy("processes:dashboard")
    context_object_name = "processes"
    filterset_class = ProcessFilter
    paginate_by = 20

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("owner", "parent")
            .prefetch_related("categories", "process_materials__material")
        )


class ProcessDetailView(UserCreatedObjectDetailView):
    """Display Process details with all related information."""

    model = Process
    template_name = "processes/process_detail.html"

    def get_queryset(self):
        # Optimize queries with prefetch
        return (
            super()
            .get_queryset()
            .select_related("owner", "parent")
            .prefetch_related(
                "categories",
                "variants",
                Prefetch(
                    "process_materials",
                    queryset=ProcessMaterial.objects.select_related(
                        "material", "quantity_unit"
                    ),
                ),
                Prefetch(
                    "operating_parameters",
                    queryset=ProcessOperatingParameter.objects.select_related("unit"),
                ),
                "links",
                "info_resources",
                Prefetch(
                    "references",
                    queryset=ProcessReference.objects.select_related("source"),
                ),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Organize materials by role
        context["input_materials"] = self.object.input_materials
        context["output_materials"] = self.object.output_materials

        # Group parameters by type
        params_by_type = {}
        for param in self.object.operating_parameters.all():
            param_type = param.get_parameter_display()
            if param_type not in params_by_type:
                params_by_type[param_type] = []
            params_by_type[param_type].append(param)
        context["parameters_by_type"] = params_by_type

        return context


class ProcessModalDetailView(UserCreatedObjectModalDetailView):
    """Display Process details in a modal."""

    model = Process


class ProcessUpdateView(UserCreatedObjectUpdateWithInlinesView):
    """Update a Process with related objects."""

    model = Process
    form_class = ProcessModelForm
    template_name = "processes/process_form.html"
    inlines = [
        ProcessMaterialInline,
        ProcessOperatingParameterInline,
        ProcessLinkInline,
        ProcessInfoResourceInline,
        ProcessReferenceInline,
    ]

    def get_success_url(self):
        return reverse("processes:process-detail", kwargs={"pk": self.object.pk})


class ProcessModalDeleteView(UserCreatedObjectModalDeleteView):
    """Delete a Process."""

    model = Process


class ProcessAutocompleteView(UserCreatedObjectAutocompleteView):
    """Autocomplete view for Process selection."""

    model = Process
    search_lookups = ["name__icontains", "mechanism__icontains"]


# ==============================================================================
# Utility Views
# ==============================================================================


class ProcessAddMaterialView(
    LoginRequiredMixin, NextOrSuccessUrlMixin, CreateWithInlinesView
):
    """Add a material to an existing process."""

    model = ProcessMaterial
    form_class = ProcessAddMaterialForm
    template_name = "processes/process_add_material.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["process"] = get_object_or_404(Process, pk=self.kwargs["pk"])
        return context

    def form_valid(self, form):
        form.instance.process = get_object_or_404(Process, pk=self.kwargs["pk"])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("processes:process-detail", kwargs={"pk": self.kwargs["pk"]})


class ProcessAddParameterView(
    LoginRequiredMixin, NextOrSuccessUrlMixin, CreateWithInlinesView
):
    """Add an operating parameter to an existing process."""

    model = ProcessOperatingParameter
    form_class = ProcessAddParameterForm
    template_name = "processes/process_add_parameter.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["process"] = get_object_or_404(Process, pk=self.kwargs["pk"])
        return context

    def form_valid(self, form):
        form.instance.process = get_object_or_404(Process, pk=self.kwargs["pk"])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("processes:process-detail", kwargs={"pk": self.kwargs["pk"]})
