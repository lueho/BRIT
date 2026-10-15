import json

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.forms import TomSelectFormsetHelper
from utils.object_management.policy import decide
from utils.object_management.services import (
    authorize_url_check_job,
    content_mutation,
    record_creation,
    register_url_check_job,
)
from utils.object_management.templatetags.moderation_tags import safe_back_url
from utils.object_management.views import (
    PolicyPermissionRequiredMixin,
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    ReviewObjectFilterView,
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
from utils.permissions import HasModelPermission
from utils.views import BreadcrumbContextMixin

from .filters import AuthorFilterSet, LicenceListFilter, SourceFilter
from .forms import (
    AuthorModalModelForm,
    AuthorModelForm,
    LicenceModalModelForm,
    LicenceModelForm,
    SourceBibtexArticleImportForm,
    SourceModalModelForm,
    SourceModelForm,
)
from .inlines import SourceAuthorInline
from .models import (
    SOURCE_TYPES,
    Author,
    Licence,
    Source,
)
from .serializers import HyperlinkedSourceSerializer, SourceCreateSerializer
from .services import (
    create_source_with_authors,
    resolve_author_for_source,
    source_is_referenced,
)
from .tasks import check_source_url, check_source_urls


class BibliographyExplorerView(BreadcrumbContextMixin, TemplateView):
    template_name = "bibliography_dashboard.html"
    breadcrumb_module_label = "Bibliography"
    breadcrumb_page_title = "Bibliography"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source_count"] = Source.objects.filter(
            type__in=[t[0] for t in SOURCE_TYPES],
            publication_status="published",
        ).count()
        context["author_count"] = Author.objects.filter(
            publication_status="published"
        ).count()
        context["licence_count"] = Licence.objects.filter(
            publication_status="published"
        ).count()
        return context


# ----------- Author CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorPublishedListView(PublishedObjectFilterView):
    model = Author
    filterset_class = AuthorFilterSet
    dashboard_url = reverse_lazy("bibliography-explorer")
    ordering = "last_names"


class AuthorPrivateListView(PrivateObjectFilterView):
    model = Author
    filterset_class = AuthorFilterSet
    dashboard_url = reverse_lazy("bibliography-explorer")
    ordering = "last_names"


class AuthorReviewListView(ReviewObjectFilterView):
    model = Author
    filterset_class = AuthorFilterSet
    dashboard_url = reverse_lazy("bibliography-explorer")
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
        "organization_name__icontains",
    ]
    ordering = "last_names"
    page_size = 10
    value_fields = [
        "id",
        "last_names",
        "first_names",
        "author_type",
        "organization_name",
    ]
    virtual_fields = ["label"]

    def hook_queryset(self, queryset):
        queryset = super().hook_queryset(queryset)
        # Exclude legacy rows that bypassed clean() and carry no letter in
        # their display name (e.g. imported "30.379" surnames).
        return queryset.filter(
            Q(author_type="organization", organization_name__regex=r"[[:alpha:]]")
            | Q(author_type="person", last_names__regex=r"[[:alpha:]]")
        )

    def hook_prepare_results(self, results):
        for result in results:
            result["label"] = (
                result["organization_name"]
                if result.get("author_type") == "organization"
                else f"{result['last_names']}, {result['first_names']}"
            )
            if result.get("author_type") != "organization":
                result.pop("author_type", None)
                result.pop("organization_name", None)
        return results


# ----------- Licence CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LicencePublishedListView(PublishedObjectFilterView):
    model = Licence
    filterset_class = LicenceListFilter
    dashboard_url = reverse_lazy("bibliography-explorer")


class LicencePrivateListView(PrivateObjectFilterView):
    model = Licence
    filterset_class = LicenceListFilter
    dashboard_url = reverse_lazy("bibliography-explorer")


class LicenceReviewListView(ReviewObjectFilterView):
    model = Licence
    filterset_class = LicenceListFilter
    dashboard_url = reverse_lazy("bibliography-explorer")


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
        "citation_key"
    )
    filterset_class = SourceFilter
    dashboard_url = reverse_lazy("bibliography-explorer")


class SourcePrivateFilterView(PrivateObjectFilterView):
    model = Source
    queryset = Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by(
        "citation_key"
    )
    filterset_class = SourceFilter
    dashboard_url = reverse_lazy("bibliography-explorer")


class SourceReviewFilterView(ReviewObjectFilterView):
    model = Source
    queryset = Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by(
        "citation_key"
    )
    filterset_class = SourceFilter
    dashboard_url = reverse_lazy("bibliography-explorer")


class SourceCreateView(UserCreatedObjectCreateWithInlinesView):
    model = Source
    form_class = SourceModelForm
    inlines = [SourceAuthorInline]
    permission_required = "bibliography.add_source"
    formset_helper_class = TomSelectFormsetHelper
    template_name = "bibliography/source_create_form.html"


class SourceModalCreateView(UserCreatedObjectModalCreateView):
    form_class = SourceModalModelForm
    permission_required = "bibliography.add_source"


class SourceBibtexArticleImportView(PolicyPermissionRequiredMixin, FormView):
    form_class = SourceBibtexArticleImportForm
    policy_model = Source
    permission_required = "bibliography.add_source"
    template_name = "bibliography/source_bibtex_article_import_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form_title": "Create New Reference from BibTeX @article",
                "submit_button_text": "Import",
            }
        )
        return context

    def form_valid(self, form):
        try:
            sources = form.create_sources(owner=self.request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)

        if len(sources) == 1:
            messages.success(self.request, "Reference created successfully.")
            return HttpResponseRedirect(sources[0].get_absolute_url())

        messages.success(
            self.request,
            f"{len(sources)} references created successfully.",
        )
        return HttpResponseRedirect(reverse_lazy("source-list-owned"))


class SourceDetailView(UserCreatedObjectDetailView):
    model = Source

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["back_url"] = safe_back_url({"request": self.request})
        return context


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
            {
                "modal_title": "Reference details",
                "object_data": serializer.data,
            }
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


def _parse_json_object(request):
    """Parse the request body as a JSON object; ``None`` marks invalid input."""
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


class AuthorQuickCreateView(LoginRequiredMixin, View):
    """Create a minimal Author object for inline source creation workflows."""

    def post(self, request, *args, **kwargs):
        """Create or return an Author from a JSON payload."""
        payload = _parse_json_object(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON object."}, status=400)

        allow_create = decide(request.user, "create", Author).allowed
        try:
            with transaction.atomic():
                author, created = resolve_author_for_source(
                    request.user, payload, allow_create=allow_create
                )
                if created:
                    record_creation(request.user, author)
        except PermissionDenied as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except ValidationError as exc:
            return JsonResponse(
                {"error": exc.messages[0] if exc.messages else str(exc)},
                status=400,
            )
        if author.author_type == "organization":
            label = author.organization_name
            data = {
                "id": author.pk,
                "author_type": "organization",
                "organization_name": author.organization_name,
            }
        else:
            label = f"{author.last_names}, {author.first_names}".strip(", ")
            data = {
                "id": author.pk,
                "first_names": author.first_names,
                "last_names": author.last_names,
            }
        data.update({"label": label, "text": label})
        return JsonResponse(data, status=201 if created else 200)


class SourceQuickCreateView(LoginRequiredMixin, View):
    """Create a minimal Source object for inline source selectors.

    This endpoint is used by SourceListWidget to create a new bibliography source
    directly from form contexts (for example waste collection creation) without
    navigating away to the bibliography module.
    """

    def post(self, request, *args, **kwargs):
        """Create a Source from a JSON payload and return option data as JSON."""
        payload = _parse_json_object(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON object."}, status=400)

        raw_year = payload.get("year")
        year = None
        if raw_year not in (None, ""):
            try:
                year = int(raw_year)
            except (TypeError, ValueError):
                return JsonResponse(
                    {"error": "Year must be a valid integer."},
                    status=400,
                )

        source_data = {
            "title": payload.get("title", ""),
            "type": "misc",
            "year": year,
        }
        authors_data = payload.get("authors", [])
        if not isinstance(authors_data, list):
            return JsonResponse(
                {"error": "The 'authors' field must be a list."},
                status=400,
            )

        try:
            source = create_source_with_authors(request.user, source_data, authors_data)
        except PermissionDenied as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except ValidationError as exc:
            return JsonResponse(
                {"error": exc.messages[0] if exc.messages else str(exc)},
                status=400,
            )

        authors = source.authors_ordered
        author_part = "; ".join(author.abbreviated_full_name for author in authors)
        formatted_label = (
            f"{author_part}. {source.title}" if author_part else source.title
        )

        return JsonResponse(
            {
                "id": source.pk,
                "title": source.title,
                "text": formatted_label,
                "label": formatted_label,
            },
            status=201,
        )

    def delete(self, request, *args, **kwargs):
        """Delete a quick-created Source if the delete policy allows it.

        Only sources the policy lets the requesting user delete (i.e. owned
        private records) and that are not referenced by other objects may be
        removed via this endpoint.  This prevents orphaned records when the
        user removes a just-created source from the widget before saving the
        parent form.
        """
        payload = _parse_json_object(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON object."}, status=400)

        source_id = payload.get("id")
        if not source_id:
            return JsonResponse({"error": "Source id is required."}, status=400)

        try:
            source = Source.objects.get(pk=int(source_id))
        except (Source.DoesNotExist, TypeError, ValueError):
            return JsonResponse({"error": "Source not found."}, status=404)

        if not decide(request.user, "delete", source).allowed:
            return JsonResponse(
                {"error": "You don't have permission to delete this source."},
                status=403,
            )

        if source_is_referenced(source):
            return JsonResponse(
                {"error": "This source is referenced by other objects."},
                status=400,
            )

        with content_mutation(request.user, source, action="delete"):
            source.delete()
        return JsonResponse({"deleted": True}, status=200)


class SourceCreateAPIView(APIView):
    queryset = Source.objects.all()
    permission_classes = [HasModelPermission]
    action = "create"
    permission_required = {"create": "bibliography.add_source"}

    def post(self, request, *args, **kwargs):
        serializer = SourceCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        source = serializer.save()
        return Response(
            SourceCreateSerializer(source, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class SourceCheckUrlView(LoginRequiredMixin, View):
    object = None
    model = Source

    def get(self, request, *args, **kwargs):
        self.object = get_object_or_404(self.model, pk=kwargs.get("pk"))
        decision = decide(request.user, "check_url", self.object)
        if not decision.allowed:
            raise PermissionDenied(decision.reason)

        task = check_source_url.delay(self.object.pk, request.user.pk)
        register_url_check_job(task.task_id, request.user, target=self.object)
        response_data = {"task_id": task.task_id}
        return HttpResponse(json.dumps(response_data), content_type="application/json")


class SourceCheckUrlProgressView(LoginRequiredMixin, View):
    @staticmethod
    def get(request, task_id):
        authorize_url_check_job(request.user, task_id)
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
        task = self.check_task.delay(params, request.user.pk)
        register_url_check_job(task.task_id, request.user)
        response_data = {"task_id": task.task_id}
        return HttpResponse(json.dumps(response_data), content_type="application/json")


class SourceAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Source
    search_lookups = [
        "citation_key__icontains",
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
        "citation_key",
        "url",
    ]

    def get_queryset(self):
        """Order sources to prioritize actual bibliographic sources over URLs."""
        qs = super().get_queryset()
        from django.db.models import Case, Exists, IntegerField, OuterRef, When

        from bibliography.models import SourceAuthor

        has_authors_subquery = SourceAuthor.objects.filter(source=OuterRef("pk"))

        qs = qs.annotate(
            has_authors=Exists(has_authors_subquery),
            type_priority=Case(
                When(type="waste_flyer", then=1),
                default=0,
                output_field=IntegerField(),
            ),
        ).order_by("type_priority", "-has_authors", "title")

        return qs.distinct()

    def hook_prepare_results(self, results):
        from bibliography.models import SourceAuthor

        if self.request.GET.get("label") == "abbreviation":
            for result in results:
                label = result.get("citation_key") or f"Source #{result['id']}"
                result.update(
                    text=label, selected_text=label, abbreviation=label, label=label
                )
            return results

        source_ids = [r["id"] for r in results]
        authors_by_source = {}
        author_qs = (
            SourceAuthor.objects.filter(source_id__in=source_ids)
            .order_by("source_id", "position")
            .select_related("author")
        )
        for sa in author_qs:
            authors_by_source.setdefault(sa.source_id, []).append(sa.author)

        for result in results:
            source_type = result.get("type", "misc")

            if source_type == "waste_flyer":
                url = result.get("url", "")
                formatted_name = url if url else f"WasteFlyer #{result['id']}"
            else:
                title = result.get("title", "").strip()
                authors = authors_by_source.get(result["id"], [])

                if authors:
                    author_part = "; ".join(a.abbreviated_full_name for a in authors)
                    formatted_name = f"{author_part}. {title}" if title else author_part
                else:
                    formatted_name = (
                        title
                        if title
                        else result.get("citation_key", f"Source #{result['id']}")
                    )

            result["text"] = formatted_name
            result["selected_text"] = formatted_name
            result["citation_key"] = formatted_name
            result["abbreviation"] = formatted_name
            result["label"] = formatted_name
        return results
