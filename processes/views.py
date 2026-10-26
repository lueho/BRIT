"""Production views for the processes module.

Provides complete CRUD operations for all process-related models following
BRIT conventions and patterns from utils.object_management.views.
"""

from urllib.parse import urlsplit

from django.db.models import Prefetch, prefetch_related_objects
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView

from bibliography.models import Author, Source
from materials.models import Material
from utils.object_management.models import ReviewAction
from utils.object_management.permissions import (
    apply_scope_filter,
    filter_queryset_for_user,
    get_object_policy,
    user_is_moderator_for_model,
)
from utils.object_management.views import (
    OwnedObjectModelSelectOptionsView,
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    PublishedObjectListView,
    ReviewItemDetailView,
    ReviewObjectFilterView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
    WorkspaceSectionUpdateMixin,
)
from utils.views import BreadcrumbContextMixin, get_safe_next_url

from .filters import ProcessCategoryFilter, ProcessFilter
from .forms import (
    PROCESS_SECTIONS,
    ProcessCategoryModalModelForm,
    ProcessCategoryModelForm,
    ProcessMaintenanceForm,
    ProcessModalModelForm,
    ProcessQuickCreateForm,
    ProcessSectionFormSet,
)
from .models import (
    Process,
    ProcessAuthor,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
    ProcessSource,
)
from .navigation import (
    categories_url,
    category_process_list_url,
    discovery_context,
    process_scope_url,
)
from .querysets import with_process_count

# ==============================================================================
# Explorer
# ==============================================================================


class ProcessExplorerView(BreadcrumbContextMixin, TemplateView):
    """Explorer landing page for the processes module."""

    template_name = "processes/explorer.html"
    breadcrumb_module_label = "Processes"
    breadcrumb_page_title = "Processes"
    top_category_limit = 8
    recent_process_limit = 5

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        published_processes = Process.objects.filter(publication_status="published")
        published_categories = ProcessCategory.objects.filter(
            publication_status="published"
        )

        context["process_count"] = published_processes.count()
        context["category_count"] = published_categories.count()
        top_categories = (
            with_process_count(published_categories, publication_status="published")
            .filter(process_count__gt=0)
            .order_by("-process_count", "name")[: self.top_category_limit]
        )
        for category in top_categories:
            category.process_list_url = category_process_list_url(category, "published")
        context["top_categories"] = top_categories
        context["recent_processes"] = published_processes.order_by("-lastmodified_at")[
            : self.recent_process_limit
        ]
        context["categories_url"] = categories_url("published")

        if user.is_authenticated:
            context["my_process_count"] = apply_scope_filter(
                Process.objects.all(), "private", user=user
            ).count()
            context["my_processes_url"] = process_scope_url("private")
        if user_is_moderator_for_model(user, Process):
            context["review_count"] = apply_scope_filter(
                Process.objects.all(), "review", user=user
            ).count()
            context["review_processes_url"] = process_scope_url("review")
        context["can_add_process"] = user.has_perm("processes.add_process")
        context["can_add_processcategory"] = user.has_perm(
            "processes.add_processcategory"
        )
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


class ProcessCategoryListViewMixin:
    """Shared class attributes for the process category list scopes."""

    model = ProcessCategory
    template_name = "processes/processcategory_list.html"
    explorer_url = reverse_lazy("processes:explorer")
    context_object_name = "categories"
    filterset_class = ProcessCategoryFilter
    paginate_by = 20


class ProcessCategoryPublishedListView(
    ProcessCategoryListViewMixin, PublishedObjectListView
):
    """Public catalogue of published ProcessCategory objects.

    The ``category_q`` query parameter drives the category-name search; the
    process discovery scope carried in ``scope`` never restricts the category
    publication state.
    """

    template_name = "processes/processcategory_catalogue.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        query = (self.request.GET.get("category_q") or "").strip()
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_q"] = (self.request.GET.get("category_q") or "").strip()
        context["discovery_scope"] = discovery_context(self.request)["scope"]
        return context


class ProcessCategoryPrivateListView(
    ProcessCategoryListViewMixin, PrivateObjectFilterView
):
    """List user's private ProcessCategory objects."""


class ProcessCategoryReviewListView(
    ProcessCategoryListViewMixin, ReviewObjectFilterView
):
    """List ProcessCategory objects in review status for moderators."""


class ProcessCategoryDetailView(UserCreatedObjectDetailView):
    """Display ProcessCategory details."""

    model = ProcessCategory
    template_name = "processes/processcategory_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Apply the read policy in both directions: a published category only
        # lists processes the current user may read, and a non-published
        # category must not leak other users' private processes either.
        process_queryset = filter_queryset_for_user(
            self.object.processes.all(), self.request.user
        )
        nav = discovery_context(self.request)
        if nav["explicit"]:
            data = nav["filters"].copy()
            data["scope"] = nav["scope"]
            process_queryset = ProcessFilter(
                data=data, queryset=process_queryset, request=self.request
            ).qs
        category_queryset = filter_queryset_for_user(
            ProcessCategory.objects.filter(processes__in=process_queryset),
            self.request.user,
        )
        processes = process_queryset.select_related("owner")
        context["processes"] = processes
        context["related_categories"] = (
            category_queryset.exclude(pk=self.object.pk).distinct().order_by("name")
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


def _scoped_list_delete_success_url(view):
    """Redirect target after modal deletion of a user-created object.

    Honors a ``next`` parameter unless it points back at the deleted
    object's own detail page, which no longer exists after deletion.
    """
    next_url = get_safe_next_url(view.request)
    if next_url and not urlsplit(next_url).path.startswith(
        view.object.get_absolute_url()
    ):
        return next_url
    if view.object.publication_status == "published":
        return f"{view.model.public_list_url()}?scope=published"
    if view.object.publication_status == "review":
        return f"{view.model.review_list_url()}?scope=review"
    return f"{view.model.private_list_url()}?scope=private"


class ProcessCategoryModalDeleteView(UserCreatedObjectModalDeleteView):
    """Delete a ProcessCategory."""

    model = ProcessCategory

    def get_success_url(self):
        return _scoped_list_delete_success_url(self)


class ProcessCategoryAutocompleteView(UserCreatedObjectAutocompleteView):
    """Autocomplete view for ProcessCategory selection."""

    model = ProcessCategory
    search_lookups = ["name__icontains"]


class ProcessCategoryOptions(OwnedObjectModelSelectOptionsView):
    """Provide ProcessCategory options for select fields."""

    model = ProcessCategory
    permission_required = set()

    def get_queryset(self):
        # Same policy as the category autocomplete: readable by the user and
        # not archived (archived categories cannot be newly selected).
        return filter_queryset_for_user(
            super().get_queryset(), self.request.user
        ).exclude(publication_status=ProcessCategory.STATUS_ARCHIVED)


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
            "cancel_url": reverse("processes:process-list"),
        }

    def get_success_url(self):
        return f"{self.object.get_absolute_url()}?mode=edit"


class ProcessModalCreateView(UserCreatedObjectModalCreateView):
    """Create a new Process in a modal dialog."""

    model = Process
    form_class = ProcessModalModelForm
    permission_required = "processes.add_process"


def _process_list_queryset(queryset, user):
    """Shared queryset for process list views.

    Related user-created objects are filtered by the read policy so that
    private category names do not leak into list rows.
    """
    return queryset.select_related("owner").prefetch_related(
        Prefetch(
            "categories",
            queryset=filter_queryset_for_user(ProcessCategory.objects.all(), user),
        ),
    )


class ProcessFilterViewMixin:
    """Shared class attributes for the process list scopes."""

    model = Process
    template_name = "processes/process_list.html"
    explorer_url = reverse_lazy("processes:explorer")
    context_object_name = "processes"
    filterset_class = ProcessFilter
    paginate_by = 20

    def get_queryset(self):
        return _process_list_queryset(super().get_queryset(), self.request.user)


class ProcessPublishedFilterView(ProcessFilterViewMixin, PublishedObjectFilterView):
    """List published Process objects with filtering."""


class ProcessPrivateFilterView(ProcessFilterViewMixin, PrivateObjectFilterView):
    """List user's private Process objects with filtering."""


class ProcessReviewFilterView(ProcessFilterViewMixin, ReviewObjectFilterView):
    """List Process objects in review status for moderators."""


def _process_detail_prefetches(user):
    """Prefetch lookups for the process detail views.

    Related user-created objects are prefetch-filtered by the read policy so
    private/in-review objects owned by others never reach the template.
    """
    return (
        Prefetch(
            "categories",
            queryset=filter_queryset_for_user(ProcessCategory.objects.all(), user),
        ),
        Prefetch(
            "process_authors",
            queryset=ProcessAuthor.objects.select_related("author").filter(
                author__in=filter_queryset_for_user(Author.objects.all(), user)
            ),
        ),
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


PROCESS_SECTION_NEXT_STEPS = {
    "inputs": "add a material that goes into the process.",
    "outputs": "add a material the process produces.",
    "overview": "add a short description or a category.",
    "technology": "describe how the process works.",
    "parameters": "add typical operating conditions.",
    "references": "credit the sources and people behind this process.",
    "resources": "link documents or websites with more detail.",
    "image": "add a picture of the process.",
}


def process_section_progress(process):
    """Count sections with saved content and suggest the next one to fill."""
    has_content = {
        "overview": bool(process.short_description) or process.categories.exists(),
        "image": bool(process.image),
        "technology": bool(
            process.mechanism or process.description or process.process_technology
        ),
        "inputs": process.process_materials.filter(
            role=ProcessMaterial.Role.INPUT
        ).exists(),
        "outputs": process.process_materials.filter(
            role=ProcessMaterial.Role.OUTPUT
        ).exists(),
        "parameters": process.operating_parameters.exists(),
        "references": process.process_authors.exists()
        or process.process_sources.exists(),
        "resources": bool(process.supplementary_document)
        or process.links.exists()
        or process.info_resources.exists(),
    }
    next_key = next(
        (key for key in PROCESS_SECTION_NEXT_STEPS if not has_content[key]), None
    )
    return {
        "filled": sum(has_content[key] for key in PROCESS_SECTIONS),
        "total": len(PROCESS_SECTIONS),
        "next": {
            "key": next_key,
            "label": PROCESS_SECTIONS[next_key]["label"],
            "hint": PROCESS_SECTION_NEXT_STEPS[next_key],
        }
        if next_key
        else None,
    }


class ProcessDetailView(UserCreatedObjectDetailView):
    """Display Process details with all related information."""

    model = Process
    template_name = "processes/process_detail.html"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("owner")
            .prefetch_related(*_process_detail_prefetches(self.request.user))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        policy = get_object_policy(self.request.user, self.object, request=self.request)
        context["edit_mode_enabled"] = (
            self.request.GET.get("mode") == "edit" and policy["can_edit"]
        )
        if context["edit_mode_enabled"]:
            context["process_policy"] = policy
            section_links = {
                key: self.object._material_links_for_role(section["role"])
                for key, section in PROCESS_SECTIONS.items()
                if "role" in section
            }
            visible_material_ids = self._visible_material_ids(
                {link.material_id for links in section_links.values() for link in links}
            )
            context["maintenance_sections"] = [
                {
                    "key": key,
                    "label": section["label"],
                    "url": f"{self.object.update_url}?section={key}",
                    "summary_template": "processes/includes/process_section_summary.html",
                    "material_links": [
                        link
                        for link in section_links.get(key, [])
                        if link.material_id in visible_material_ids
                    ],
                }
                for key, section in PROCESS_SECTIONS.items()
            ]
            context["section_progress"] = process_section_progress(self.object)
            return context

        # Organize materials by role, dropping links to materials the current
        # user cannot read so private material names do not leak.
        input_links = self.object._material_links_for_role(ProcessMaterial.Role.INPUT)
        output_links = self.object._material_links_for_role(ProcessMaterial.Role.OUTPUT)
        visible_material_ids = self._visible_material_ids(
            {link.material_id for link in input_links}
            | {link.material_id for link in output_links}
        )
        context["input_materials"] = [
            link for link in input_links if link.material_id in visible_material_ids
        ]
        context["output_materials"] = [
            link for link in output_links if link.material_id in visible_material_ids
        ]

        # Group parameters by type, keyed by the stable parameter value so
        # the template lookup does not depend on the display language.
        params_by_type = {}
        for param in self.object.operating_parameters.all():
            params_by_type.setdefault(param.parameter, []).append(param)
        context["parameters_by_type"] = params_by_type
        context["operating_parameters"] = [
            param
            for param in self.object.operating_parameters.all()
            if param.parameter != ProcessOperatingParameter.Parameter.YIELD
        ]
        context["process_links"] = list(self.object.links.all())
        context["process_info_resources"] = list(self.object.info_resources.all())
        # Drop authors the current user cannot read so private contributor
        # names and contact emails do not leak on published processes.
        process_authors = self.object.ordered_authors()
        author_ids = {link.author_id for link in process_authors}
        visible_author_ids = set(
            filter_queryset_for_user(
                Author.objects.filter(pk__in=author_ids), self.request.user
            ).values_list("pk", flat=True)
        )
        context["process_authors"] = [
            link for link in process_authors if link.author_id in visible_author_ids
        ]
        sources = self.object.sources_ordered()
        visible_source_ids = set(
            filter_queryset_for_user(
                Source.objects.filter(pk__in=[s.pk for s in sources]),
                self.request.user,
            ).values_list("pk", flat=True)
        )
        # Keep the explicit order maintained in the workspace formset;
        # re-sorting alphabetically would hide the editor's ordering.
        context["bibliography_sources"] = [
            s for s in sources if s.pk in visible_source_ids
        ]
        context["process_policy"] = policy
        # The timeline only feeds the review banner, which renders solely for
        # 'review' and 'declined' objects; skip the query otherwise.
        context["review_timeline"] = (
            self._build_review_timeline()
            if self.object.publication_status in ("review", "declined")
            else []
        )
        context["section_anchors"] = self._build_section_anchors(context)
        section_url = context.get("breadcrumb_section_url")
        if callable(section_url):
            section_url = section_url()
        if section_url is not None and section_url == context.get(
            "breadcrumb_module_url"
        ):
            context.pop("breadcrumb_section_label", None)
            context.pop("breadcrumb_section_url", None)

        return context

    def _visible_material_ids(self, material_ids):
        """Pks of linked materials the current user may read."""
        return set(
            filter_queryset_for_user(
                Material.objects.filter(pk__in=material_ids), self.request.user
            ).values_list("pk", flat=True)
        )

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
                ProcessOperatingParameter.Parameter.YIELD
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

    def get_object(self, queryset=None):
        # The registry path resolves the object without a queryset; apply the
        # detail view's policy-filtered prefetches so related objects respect
        # the requesting reviewer's read policy.
        obj = super().get_object(queryset)
        prefetch_related_objects([obj], *_process_detail_prefetches(self.request.user))
        return obj

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


class ProcessCategoryReviewItemDetailView(ReviewItemDetailView):
    """Render process category moderation with the full category detail context."""

    model = ProcessCategory
    detail_view_class = ProcessCategoryDetailView


ProcessCategoryReviewItemDetailView.register_for_model(ProcessCategory)


class ProcessModalDetailView(UserCreatedObjectModalDetailView):
    """Display Process details in a modal."""

    model = Process


class ProcessUpdateView(WorkspaceSectionUpdateMixin, UserCreatedObjectUpdateView):
    """Update a Process with related objects."""

    model = Process
    form_class = ProcessMaintenanceForm
    template_name = "processes/process_form.html"
    section_registry = PROCESS_SECTIONS
    section_formset_class = ProcessSectionFormSet
    object_label = "process"
    section_form_template = "processes/includes/process_section_form.html"
    section_summary_template = "processes/includes/process_section_summary.html"

    def get_section_summary_context(self):
        context = super().get_section_summary_context()
        if "role" in self.section:
            links = self.object._material_links_for_role(self.section["role"])
            visible_material_ids = set(
                filter_queryset_for_user(
                    Material.objects.filter(
                        pk__in={link.material_id for link in links}
                    ),
                    self.request.user,
                ).values_list("pk", flat=True)
            )
            context["material_links"] = [
                link for link in links if link.material_id in visible_material_ids
            ]
        return context

    def get_section_saved_payload(self, message):
        payload = super().get_section_saved_payload(message)
        payload["progress_html"] = render_to_string(
            "processes/includes/process_section_progress.html",
            {"section_progress": process_section_progress(self.object)},
            request=self.request,
        )
        return payload


class ProcessModalDeleteView(UserCreatedObjectModalDeleteView):
    """Delete a Process."""

    model = Process

    def get_success_url(self):
        return _scoped_list_delete_success_url(self)


class ProcessAutocompleteView(UserCreatedObjectAutocompleteView):
    """Autocomplete view for Process selection."""

    model = Process
    search_lookups = ["name__icontains", "mechanism__icontains"]
