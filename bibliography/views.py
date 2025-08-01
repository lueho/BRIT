import json

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from utils.forms import TomSelectFormsetHelper
from utils.object_management.views import (
    PrivateObjectFilterView,
    PrivateObjectListView,
    PublishedObjectFilterView,
    PublishedObjectListView,
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

from .filters import AuthorFilterSet, SourceFilter
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


class LicencePublishedListView(PublishedObjectListView):
    model = Licence
    dashboard_url = reverse_lazy("bibliography-dashboard")


class LicencePrivateListView(PrivateObjectListView):
    model = Licence
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


class SourceCheckUrlView(PermissionRequiredMixin, View):
    object = None
    model = Source
    permission_required = "bibliography.change_source"

    def get(self, request, *args, **kwargs):
        self.object = self.model.objects.get(pk=kwargs.get("pk"))
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
        "title__icontains",
        "authors__last_names__icontains",
        "authors__first_names__icontains",
    ]
    ordering = "title"
    page_size = 10
    value_fields = ["id", "title", "authors__last_names", "authors__first_names"]

    def hook_prepare_results(self, results):
        for result in results:
            formatted_name = f"{result['authors__last_names']}, {result['authors__first_names']}. {result['title']}"
            result["text"] = formatted_name
            result["selected_text"] = formatted_name
        return results
