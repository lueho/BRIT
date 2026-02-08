import json

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from utils.forms import TomSelectFormsetHelper
from utils.object_management.permissions import get_object_policy
from utils.object_management.views import (
    PrivateObjectFilterView,
    PublishedObjectFilterView,
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

from .filters import AuthorFilterSet, LicenceListFilter, SourceFilter
from .forms import (
    AuthorModalModelForm,
    AuthorModelForm,
    LicenceModalModelForm,
    LicenceModelForm,
    SourceModalModelForm,
    SourceModelForm,
)
from .inlines import SourceAuthorInline
from .models import SOURCE_TYPES, Author, Licence, Source
from .serializers import HyperlinkedSourceSerializer
from .tasks import check_source_url, check_source_urls


class BibliographyDashboardView(TemplateView):
    template_name = "bibliography_dashboard.html"


# ----------- Author CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorPublishedListView(PublishedObjectFilterView):
    model = Author
    filterset_class = AuthorFilterSet
    dashboard_url = reverse_lazy("bibliography-dashboard")
    ordering = "last_names"


class AuthorPrivateListView(PrivateObjectFilterView):
    model = Author
    filterset_class = AuthorFilterSet
    dashboard_url = reverse_lazy("bibliography-dashboard")
    ordering = "last_names"


class AuthorCreateView(UserCreatedObjectCreateView):
    form_class = AuthorModelForm
    permission_required = "bibliography.add_author"


class AuthorModalCreateView(UserCreatedObjectModalCreateView):
    form_class = AuthorModalModelForm
    permission_required = "bibliography.add_author"


class AuthorDetailView(UserCreatedObjectDetailView):
    model = Author


class AuthorModalDetailView(UserCreatedObjectModalDetailView):
    template_name = "author_detail_modal.html"
    model = Author


class AuthorUpdateView(UserCreatedObjectUpdateView):
    model = Author
    form_class = AuthorModelForm


class AuthorModalUpdateView(UserCreatedObjectModalUpdateView):
    model = Author
    form_class = AuthorModalModelForm


class AuthorModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Author


# ----------- Author Utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Author
    search_lookups = [
        "last_names__icontains",
        "first_names__icontains",
    ]
    ordering = "last_names"
    page_size = 10
    value_fields = ["id", "last_names", "first_names"]
    virtual_fields = ["label"]

    def hook_prepare_results(self, results):
        for result in results:
            result["label"] = f"{result['last_names']}, {result['first_names']}"
        return results


# ----------- Licence CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LicencePublishedListView(PublishedObjectFilterView):
    model = Licence
    filterset_class = LicenceListFilter
    dashboard_url = reverse_lazy("bibliography-dashboard")


class LicencePrivateListView(PrivateObjectFilterView):
    model = Licence
    filterset_class = LicenceListFilter
    dashboard_url = reverse_lazy("bibliography-dashboard")


class LicenceCreateView(UserCreatedObjectCreateView):
    form_class = LicenceModelForm
    permission_required = "bibliography.add_licence"


class LicenceModalCreateView(UserCreatedObjectModalCreateView):
    form_class = LicenceModalModelForm
    permission_required = "bibliography.add_licence"


class LicenceDetailView(UserCreatedObjectDetailView):
    model = Licence


class LicenceModalDetailView(UserCreatedObjectModalDetailView):
    template_name = "licence_detail_modal.html"
    model = Licence


class LicenceUpdateView(UserCreatedObjectUpdateView):
    model = Licence
    form_class = LicenceModelForm


class LicenceModalUpdateView(UserCreatedObjectModalUpdateView):
    model = Licence
    form_class = LicenceModalModelForm


class LicenceModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Licence


class LicenceAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Licence


# ----------- Source CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SourcePublishedFilterView(PublishedObjectFilterView):
    model = Source
    queryset = Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by(
        "abbreviation"
    )
    filterset_class = SourceFilter
    dashboard_url = reverse_lazy("bibliography-dashboard")


class SourcePrivateFilterView(PrivateObjectFilterView):
    model = Source
    queryset = Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by(
        "abbreviation"
    )
    filterset_class = SourceFilter
    dashboard_url = reverse_lazy("bibliography-dashboard")


class SourceCreateView(UserCreatedObjectCreateWithInlinesView):
    model = Source
    form_class = SourceModelForm
    inlines = [SourceAuthorInline]
    permission_required = "bibliography.add_source"
    formset_helper_class = TomSelectFormsetHelper


class SourceModalCreateView(UserCreatedObjectModalCreateView):
    form_class = SourceModalModelForm
    permission_required = "bibliography.add_source"


class SourceDetailView(UserCreatedObjectDetailView):
    model = Source


class SourceModalDetailView(UserCreatedObjectModalDetailView):
    template_name = "source_detail_modal.html"
    model = Source

    def get_context_data(self, **kwargs):
        # TODO: Documentation
        context = super().get_context_data(**kwargs)
        serializer = HyperlinkedSourceSerializer(
            self.object, context={"request": self.request}
        )
        context.update(
            {"modal_title": "Source details", "object_data": serializer.data}
        )
        return context


class SourceUpdateView(UserCreatedObjectUpdateWithInlinesView):
    model = Source
    form_class = SourceModelForm
    inlines = [SourceAuthorInline]
    formset_helper_class = TomSelectFormsetHelper


class SourceModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Source


# ----------- Source utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SourceCheckUrlView(LoginRequiredMixin, View):
    object = None
    model = Source

    def get(self, request, *args, **kwargs):
        self.object = self.model.objects.get(pk=kwargs.get("pk"))
        policy = get_object_policy(request.user, self.object, request=request)
        if not (
            policy.get("is_owner")
            or policy.get("is_staff")
            or policy.get("is_moderator")
        ):
            raise PermissionDenied

        task = check_source_url.delay(self.object.pk)
        response_data = {"task_id": task.task_id}
        return HttpResponse(json.dumps(response_data), content_type="application/json")


class SourceCheckUrlProgressView(LoginRequiredMixin, View):
    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            "state": result.state,
            "details": result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type="application/json")


class SourceListCheckUrlsView(PermissionRequiredMixin, View):
    model = Source
    filterset_class = SourceFilter
    success_url = None
    permission_required = "bibliography.change_source"
    check_task = check_source_urls

    def get(self, request, *args, **kwargs):
        params = request.GET.copy()
        params.pop("page", None)
        task = self.check_task.delay(params)
        response_data = {"task_id": task.task_id}
        return HttpResponse(json.dumps(response_data), content_type="application/json")


class SourceAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Source
    search_lookups = [
        "abbreviation__icontains",
        "title__icontains",
        "authors__last_names__icontains",
        "authors__first_names__icontains",
        "url__icontains",
    ]
    page_size = 10
    value_fields = [
        "id",
        "type",
        "title",
        "abbreviation",
        "url",
        "authors__last_names",
        "authors__first_names",
    ]

    def get_queryset(self):
        """Order sources to prioritize actual bibliographic sources over URLs."""
        qs = super().get_queryset()
        # Annotate with has_authors to prioritize sources with authors
        # Then order by type (waste_flyer comes last alphabetically)
        # Then by title
        from django.db.models import Case, Exists, IntegerField, OuterRef, When

        from bibliography.models import SourceAuthor

        # Check if source has any authors using Exists instead of Count to avoid GROUP BY issues
        has_authors_subquery = SourceAuthor.objects.filter(source=OuterRef("pk"))

        qs = qs.annotate(
            has_authors=Exists(has_authors_subquery),
            # Prioritize non-waste_flyer types
            type_priority=Case(
                When(type="waste_flyer", then=1),
                default=0,
                output_field=IntegerField(),
            ),
        ).order_by("type_priority", "-has_authors", "title")

        return qs

    def hook_prepare_results(self, results):
        for result in results:
            source_type = result.get("type", "custom")

            if source_type == "waste_flyer":
                # WasteFlyers are identified by URL
                url = result.get("url", "")
                formatted_name = url if url else f"WasteFlyer #{result['id']}"
            else:
                # Traditional sources use author/title format
                last_names = result.get("authors__last_names", "").strip()
                first_names = result.get("authors__first_names", "").strip()
                title = result.get("title", "").strip()

                if last_names or first_names:
                    author_part = f"{last_names}, {first_names}".strip(", ")
                    formatted_name = f"{author_part}. {title}" if title else author_part
                else:
                    formatted_name = (
                        title
                        if title
                        else result.get("abbreviation", f"Source #{result['id']}")
                    )

            # Set all possible label fields that forms might use
            result["text"] = formatted_name
            result["selected_text"] = formatted_name
            result["abbreviation"] = (
                formatted_name  # For forms using label_field="abbreviation"
            )
            result["label"] = formatted_name  # For forms using label_field="label"
        return results
