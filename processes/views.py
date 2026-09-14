"""Production views for the processes module.

Provides complete CRUD operations for all process-related models following
BRIT conventions and patterns from utils.object_management.views.
"""

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, TemplateView

from utils.object_management.models import ReviewAction
from utils.object_management.permissions import get_object_policy
from utils.object_management.views import (
    OwnedObjectModelSelectOptionsView,
    PrivateObjectFilterView,
    PrivateObjectListView,
    PublishedObjectFilterView,
    PublishedObjectListView,
    ReviewItemDetailView,
    ReviewObjectFilterView,
    ReviewObjectListMixin,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
)
from utils.views import BreadcrumbContextMixin

from .filters import ProcessFilter
from .forms import (
    PROCESS_SECTIONS,
    ProcessCategoryModalModelForm,
    ProcessCategoryModelForm,
    ProcessMaintenanceForm,
    ProcessModalModelForm,
    ProcessQuickCreateForm,
    process_section_formsets,
)
from .models import (
    Process,
    ProcessAuthor,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
    ProcessSource,
)
from .querysets import with_process_count, with_published_process_count

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


class ProcessDashboardView(BreadcrumbContextMixin, TemplateView):
    """Main dashboard for the processes module."""

    template_name = "processes/dashboard.html"
    breadcrumb_module_label = "Processes"
    breadcrumb_page_title = "Processes"

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
        context["categories_with_counts"] = with_published_process_count(
            ProcessCategory.objects.filter(publication_status="published")
        ).order_by("-process_count")[:10]

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
        return with_published_process_count(super().get_queryset())


class ProcessCategoryPrivateListView(PrivateObjectListView):
    """List user's private ProcessCategory objects."""

    model = ProcessCategory
    template_name = "processes/processcategory_list.html"
    dashboard_url = reverse_lazy("processes:dashboard")
    context_object_name = "categories"
    paginate_by = 20

    def get_queryset(self):
        return with_process_count(super().get_queryset())


class ProcessCategoryReviewListView(ReviewObjectListView):
    """List ProcessCategory objects in review status for moderators."""

    model = ProcessCategory
    template_name = "processes/processcategory_list.html"
    dashboard_url = reverse_lazy("processes:dashboard")
    context_object_name = "categories"
    paginate_by = 20

    def get_queryset(self):
        return with_process_count(super().get_queryset())


class ProcessCategoryDetailView(UserCreatedObjectDetailView):
    """Display ProcessCategory details."""

    model = ProcessCategory
    template_name = "processes/processcategory_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        process_queryset = self.object.processes.all()
        category_queryset = ProcessCategory.objects.filter(
            processes__in=process_queryset
        )
        process_count_status = None
        if self.object.publication_status == "published":
            process_queryset = process_queryset.filter(publication_status="published")
            category_queryset = category_queryset.filter(publication_status="published")
            process_count_status = "published"
        processes = process_queryset.select_related("owner").prefetch_related(
            "authors", "categories"
        )
        context["processes"] = processes
        context["related_categories"] = with_process_count(
            category_queryset.exclude(pk=self.object.pk).distinct(),
            publication_status=process_count_status,
        ).order_by("name")
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


class ProcessCreateView(UserCreatedObjectCreateView):
    """Create a new Process with related objects."""

    model = Process
    form_class = ProcessQuickCreateForm
    template_name = "processes/process_form.html"
    permission_required = "processes.add_process"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "request": self.request}

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "form_title": "New process",
            "submit_button_text": "Save private draft",
        }

    def get_success_url(self):
        return f"{self.object.get_absolute_url()}?mode=edit"


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
            .prefetch_related("authors", "categories", "process_materials__material")
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
                Prefetch(
                    "process_authors",
                    queryset=ProcessAuthor.objects.select_related("author"),
                ),
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
                    "process_sources",
                    queryset=ProcessSource.objects.select_related("source"),
                ),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        policy = get_object_policy(self.request.user, self.object, request=self.request)
        context["edit_mode_enabled"] = (
            self.request.GET.get("mode") == "edit" and policy["can_edit"]
        )
        if context["edit_mode_enabled"]:
            context["process_policy"] = policy
            context["maintenance_sections"] = [
                {
                    "key": key,
                    "label": section["label"],
                    "url": f"{self.object.update_url}?section={key}",
                    "material_links": self.object._material_links_for_role(
                        section["role"]
                    )
                    if "role" in section
                    else [],
                }
                for key, section in PROCESS_SECTIONS.items()
            ]
            return context

        # Organize materials by role
        context["input_materials"] = self.object._material_links_for_role(
            ProcessMaterial.Role.INPUT
        )
        context["output_materials"] = self.object._material_links_for_role(
            ProcessMaterial.Role.OUTPUT
        )

        # Group parameters by type
        params_by_type = {}
        for param in self.object.operating_parameters.all():
            param_type = param.get_parameter_display()
            if param_type not in params_by_type:
                params_by_type[param_type] = []
            params_by_type[param_type].append(param)
        context["parameters_by_type"] = params_by_type
        context["operating_parameters"] = [
            param
            for param in self.object.operating_parameters.all()
            if param.parameter != ProcessOperatingParameter.Parameter.YIELD
        ]
        context["process_links"] = list(self.object.links.all())
        context["process_info_resources"] = list(self.object.info_resources.all())
        context["process_variants"] = list(self.object.variants.all())
        context["process_authors"] = self.object.ordered_authors()
        context["bibliography_sources"] = sorted(
            self.object.sources_ordered(),
            key=lambda source: (source.abbreviation or source.title or "").casefold(),
        )
        context["process_policy"] = policy
        context["review_timeline"] = self._build_review_timeline()
        context["section_anchors"] = self._build_section_anchors(context)
        context["has_related_processes"] = bool(
            context["process_variants"] or self.object.parent_id
        )

        return context

    def _build_review_timeline(self):
        try:
            actions = (
                ReviewAction.for_object(self.object)
                .select_related("user")
                .order_by("created_at", "id")
            )
        except Exception:
            return []
        timeline = []
        for action in actions:
            timeline.append(
                {
                    "action": action.action,
                    "label": action.get_action_display()
                    if hasattr(action, "get_action_display")
                    else action.action,
                    "user": getattr(action.user, "username", None),
                    "created_at": action.created_at,
                    "comment": getattr(action, "comment", "") or "",
                }
            )
        return timeline

    def _build_section_anchors(self, context):
        """Return label/id pairs for the sections rendered on the page."""
        anchors = []
        if (
            self.object.mechanism
            or context["operating_parameters"]
            or context["input_materials"]
            or context["output_materials"]
            or context["parameters_by_type"].get(
                ProcessOperatingParameter.Parameter.YIELD.label
            )
        ):
            anchors.append({"id": "facts", "name": "At a glance"})
        if self.object.description:
            anchors.append({"id": "description", "name": "Description"})
        if self.object.process_technology:
            anchors.append({"id": "technology", "name": "Process technology"})
        if context["process_links"]:
            anchors.append({"id": "links", "name": "Links"})
        if context["process_info_resources"]:
            anchors.append({"id": "resources", "name": "Information resources"})
        if context["bibliography_sources"]:
            anchors.append({"id": "bibliography", "name": "Bibliography"})
        return anchors


class ProcessReviewItemDetailView(ReviewItemDetailView):
    """Render process moderation with the complete process detail context."""

    model = Process

    def _resolve_base_template(self):
        return "processes/process_detail.html"

    def get_review_specific_context(self, context):
        detail_view = ProcessDetailView()
        detail_view.request = self.request
        detail_view.args = self.args
        detail_view.kwargs = self.kwargs
        detail_view.object = self.object
        process_context = detail_view.get_context_data(object=self.object)
        for review_key in ("review_logs", "review_mode", "show_review_panel"):
            process_context.pop(review_key, None)
        return process_context


ProcessReviewItemDetailView.register_for_model(Process)


class ProcessModalDetailView(UserCreatedObjectModalDetailView):
    """Display Process details in a modal."""

    model = Process


class ProcessUpdateView(UserCreatedObjectUpdateView):
    """Update a Process with related objects."""

    model = Process
    form_class = ProcessMaintenanceForm
    template_name = "processes/process_form.html"

    def dispatch(self, request, *args, **kwargs):
        key = request.GET.get("section", "overview")
        if key not in PROCESS_SECTIONS:
            raise Http404("Unknown process section.")
        self.section = {**PROCESS_SECTIONS[key], "key": key}
        self.inlines = None
        with transaction.atomic():
            return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        return (
            queryset.select_for_update() if self.request.method == "POST" else queryset
        )

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "request": self.request,
            "fields": self.section.get("fields", ()),
        }

    def get_inlines(self):
        if self.inlines is None:
            self.inlines = process_section_formsets(
                self.object, self.section, self.request
            )
        return self.inlines

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "section": self.section,
                "section_url": f"{self.object.update_url}?section={self.section['key']}",
                "workspace_url": self.get_success_url(),
                "form_title": self.section["label"],
                "submit_button_text": "Save section",
                "inlines": self.get_inlines(),
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "section": self.section["key"],
                    "saved": False,
                    "html": render_to_string(
                        "processes/includes/process_section_form.html",
                        context,
                        request=self.request,
                    ),
                },
                status=422 if self.request.method == "POST" else 200,
            )
        return super().render_to_response(context, **response_kwargs)

    def form_valid(self, form):
        validity = [inline.is_valid() for inline in self.get_inlines()]
        if not all(validity):
            return self.form_invalid(form)
        self.object = form.save()
        for inline in self.get_inlines():
            inline.save()
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            context = {"object": self.object, "section": self.section}
            if "role" in self.section:
                context["material_links"] = self.object._material_links_for_role(
                    self.section["role"]
                )
            return JsonResponse(
                {
                    "section": self.section["key"],
                    "saved": True,
                    "title": self.object.name,
                    "message": "Saved privately."
                    if self.object.is_private
                    else "Changes saved.",
                    "html": render_to_string(
                        "processes/includes/process_section_summary.html",
                        context,
                        request=self.request,
                    ),
                }
            )
        messages.success(
            self.request,
            "Saved privately." if self.object.is_private else "Changes saved.",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return f"{self.object.get_absolute_url()}?mode=edit"


class ProcessModalDeleteView(UserCreatedObjectModalDeleteView):
    """Delete a Process."""

    model = Process

    def get_success_url(self):
        if self.object.publication_status == "published":
            return f"{self.model.public_list_url()}?scope=published"
        if self.object.publication_status == "review":
            return f"{self.model.review_list_url()}?scope=review"
        return f"{self.model.private_list_url()}?scope=private"


class ProcessAutocompleteView(UserCreatedObjectAutocompleteView):
    """Autocomplete view for Process selection."""

    model = Process
    search_lookups = ["name__icontains", "mechanism__icontains"]
