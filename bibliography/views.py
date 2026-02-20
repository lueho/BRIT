import json

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, JsonResponse
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


class BibliographyExplorerView(TemplateView):
    template_name = "bibliography_dashboard.html"

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
    dashboard_url = reverse_lazy("bibliography-explorer")


class LicencePrivateListView(PrivateObjectFilterView):
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
        "abbreviation"
    )
    filterset_class = SourceFilter
    dashboard_url = reverse_lazy("bibliography-explorer")


class SourcePrivateFilterView(PrivateObjectFilterView):
    model = Source
    queryset = Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by(
        "abbreviation"
    )
    filterset_class = SourceFilter
    dashboard_url = reverse_lazy("bibliography-explorer")


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


class AuthorQuickCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Create a minimal Author object for inline source creation workflows."""

    permission_required = "bibliography.add_author"

    def post(self, request, *args, **kwargs):
        """Create or return an Author from a JSON payload."""
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        first_names = " ".join(str(payload.get("first_names", "")).split())
        last_names = " ".join(str(payload.get("last_names", "")).split())

        if not last_names:
            return JsonResponse(
                {"error": "A non-empty last name is required to create an author."},
                status=400,
            )

        author = Author.objects.filter(
            first_names__iexact=first_names,
            last_names__iexact=last_names,
        ).first()

        created = False
        if author is None:
            author = Author.objects.create(
                owner=request.user,
                first_names=first_names,
                last_names=last_names,
            )
            created = True

        label = f"{author.last_names}, {author.first_names}".strip(", ")
        return JsonResponse(
            {
                "id": author.pk,
                "first_names": author.first_names,
                "last_names": author.last_names,
                "label": label,
                "text": label,
            },
            status=201 if created else 200,
        )


class SourceQuickCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Create a minimal Source object for inline source selectors.

    This endpoint is used by SourceListWidget to create a new bibliography source
    directly from form contexts (for example waste collection creation) without
    navigating away to the bibliography module.
    """

    permission_required = "bibliography.add_source"

    @staticmethod
    def _normalize_name_part(value):
        """Normalize whitespace for name parts in request payloads."""
        return " ".join(str(value or "").split())

    def _resolve_authors(self, request, payload):
        """Resolve payload authors to Author objects preserving payload order."""
        raw_authors = payload.get("authors", [])
        if not isinstance(raw_authors, list):
            return [], None

        resolved_authors = []
        resolved_ids = set()

        for raw_author in raw_authors:
            if not isinstance(raw_author, dict):
                continue

            author = None
            raw_author_id = raw_author.get("id")
            if raw_author_id not in (None, ""):
                try:
                    author = Author.objects.get(pk=int(raw_author_id))
                except (Author.DoesNotExist, TypeError, ValueError):
                    author = None
            else:
                first_names = self._normalize_name_part(raw_author.get("first_names"))
                last_names = self._normalize_name_part(raw_author.get("last_names"))
                if not last_names:
                    continue

                author = Author.objects.filter(
                    first_names__iexact=first_names,
                    last_names__iexact=last_names,
                ).first()

                if author is None:
                    if not request.user.has_perm("bibliography.add_author"):
                        return [], JsonResponse(
                            {
                                "error": (
                                    "You need permission to create authors "
                                    "for inline source creation."
                                )
                            },
                            status=403,
                        )

                    author = Author.objects.create(
                        owner=request.user,
                        first_names=first_names,
                        last_names=last_names,
                    )

            if author and author.pk not in resolved_ids:
                resolved_authors.append(author)
                resolved_ids.add(author.pk)

        return resolved_authors, None

    def post(self, request, *args, **kwargs):
        """Create a Source from a JSON payload and return option data as JSON."""
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        title = str(payload.get("title", "")).strip()
        if not title:
            return JsonResponse(
                {"error": "A non-empty title is required to create a source."},
                status=400,
            )

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

        authors, author_error = self._resolve_authors(request, payload)
        if author_error is not None:
            return author_error

        with transaction.atomic():
            source = Source.objects.create(
                owner=request.user,
                title=title,
                type="custom",
                year=year,
            )
            for position, author in enumerate(authors, start=1):
                source.sourceauthors.create(author=author, position=position)

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
        """Delete a quick-created Source owned by the requesting user.

        Only sources that were created by the requesting user and have not yet
        been published (i.e. still in draft/private state) may be deleted via
        this endpoint.  This prevents orphaned records when the user removes a
        just-created source from the widget before saving the parent form.
        """
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        source_id = payload.get("id")
        if not source_id:
            return JsonResponse({"error": "Source id is required."}, status=400)

        try:
            source = Source.objects.get(pk=int(source_id), owner=request.user)
        except (Source.DoesNotExist, TypeError, ValueError):
            return JsonResponse({"error": "Source not found."}, status=404)

        if source.publication_status == "published":
            return JsonResponse(
                {"error": "Published sources cannot be deleted via this endpoint."},
                status=403,
            )

        source.delete()
        return JsonResponse({"deleted": True}, status=200)


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
            source_type = result.get("type", "custom")

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
                        else result.get("abbreviation", f"Source #{result['id']}")
                    )

            result["text"] = formatted_name
            result["selected_text"] = formatted_name
            result["abbreviation"] = formatted_name
            result["label"] = formatted_name
        return results
