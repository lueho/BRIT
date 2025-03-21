import json

from celery.result import AsyncResult
from dal.autocomplete import Select2QuerySetView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from utils import views
from utils.views import (OwnedObjectCreateWithInlinesView, PublishedObjectFilterView, PublishedObjectListView,
                         UserCreatedObjectDetailView, UserCreatedObjectUpdateView,
                         UserCreatedObjectUpdateWithInlinesView)
from .filters import SourceFilter
from .forms import (AuthorModalModelForm, AuthorModelForm, LicenceModalModelForm, LicenceModelForm, SourceAuthorInline,
                    SourceModalModelForm, SourceModelForm)
from .models import Author, Licence, SOURCE_TYPES, Source
from .serializers import HyperlinkedSourceSerializer
from .tasks import check_source_url, check_source_urls


class BibliographyDashboardView(TemplateView):
    template_name = 'bibliography_dashboard.html'


# ----------- Author CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorListView(PublishedObjectListView):
    model = Author


class AuthorCreateView(views.OwnedObjectCreateView):
    form_class = AuthorModelForm
    permission_required = 'bibliography.add_author'


class AuthorModalCreateView(views.OwnedObjectModalCreateView):
    form_class = AuthorModalModelForm
    permission_required = 'bibliography.add_author'


class AuthorDetailView(UserCreatedObjectDetailView):
    model = Author


class AuthorModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'author_detail_modal.html'
    model = Author
    permission_required = set()


class AuthorUpdateView(UserCreatedObjectUpdateView):
    model = Author
    form_class = AuthorModelForm


class AuthorModalUpdateView(views.OwnedObjectModalUpdateView):
    model = Author
    form_class = AuthorModalModelForm
    permission_required = 'bibliography.change_author'


class AuthorModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Author
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('author-list')
    permission_required = 'bibliography.delete_author'


# ----------- Author Utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class AuthorAutoCompleteView(Select2QuerySetView):
    def get_queryset(self):
        qs = Author.objects.all().order_by('last_names')
        if self.q:
            qs = qs.filter(
                Q(last_names__icontains=self.q) |
                Q(first_names__icontains=self.q)
            ).distinct()
        return qs


# ----------- Licence CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class LicenceListView(PublishedObjectListView):
    model = Licence


class LicenceCreateView(views.OwnedObjectCreateView):
    form_class = LicenceModelForm
    permission_required = 'bibliography.add_licence'


class LicenceModalCreateView(views.OwnedObjectModalCreateView):
    form_class = LicenceModalModelForm
    permission_required = 'bibliography.add_licence'


class LicenceDetailView(UserCreatedObjectDetailView):
    model = Licence


class LicenceModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'licence_detail_modal.html'
    model = Licence
    permission_required = set()


class LicenceUpdateView(UserCreatedObjectUpdateView):
    model = Licence
    form_class = LicenceModelForm


class LicenceModalUpdateView(views.OwnedObjectModalUpdateView):
    model = Licence
    form_class = LicenceModalModelForm
    permission_required = 'bibliography.change_licence'


class LicenceModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Licence
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('licence-list')
    permission_required = 'bibliography.delete_licence'


# ----------- Source CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class PublishedSourcesFilterView(PublishedObjectFilterView):
    model = Source
    queryset = Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by('abbreviation')
    filterset_class = SourceFilter


class SourceCreateView(OwnedObjectCreateWithInlinesView):
    model = Source
    form_class = SourceModelForm
    inlines = [SourceAuthorInline]
    permission_required = 'bibliography.add_source'


class SourceModalCreateView(views.OwnedObjectModalCreateView):
    form_class = SourceModalModelForm
    permission_required = 'bibliography.add_source'


class SourceDetailView(UserCreatedObjectDetailView):
    model = Source


class SourceModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'source_detail_modal.html'
    model = Source
    permission_required = set()

    def get_context_data(self, **kwargs):
        # TODO: Documentation
        context = super().get_context_data(**kwargs)
        serializer = HyperlinkedSourceSerializer(self.object, context={'request': self.request})
        context.update({
            'modal_title': 'Source details',
            'object_data': serializer.data
        })
        return context


class SourceUpdateView(UserCreatedObjectUpdateWithInlinesView):
    model = Source
    form_class = SourceModelForm
    inlines = [SourceAuthorInline]


class SourceModalUpdateView(views.OwnedObjectModalUpdateView):
    model = Source
    form_class = SourceModalModelForm
    permission_required = 'bibliography.change_source'


class SourceModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Source
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('source-list')
    permission_required = 'bibliography.delete_source'


# ----------- Source utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SourceCheckUrlView(PermissionRequiredMixin, View):
    object = None
    model = Source
    permission_required = 'bibliography.change_source'

    def get(self, request, *args, **kwargs):
        self.object = self.model.objects.get(pk=kwargs.get('pk'))
        task = check_source_url.delay(self.object.pk)
        response_data = {
            'task_id': task.task_id
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class SourceCheckUrlProgressView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            'state': result.state,
            'details': result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class SourceListCheckUrlsView(PermissionRequiredMixin, View):
    model = Source
    filterset_class = SourceFilter
    success_url = None
    permission_required = 'bibliography.change_source'
    check_task = check_source_urls

    def get(self, request, *args, **kwargs):
        params = request.GET.copy()
        params.pop('page', None)
        task = self.check_task.delay(params)
        response_data = {
            'task_id': task.task_id
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class SourceAutocompleteView(Select2QuerySetView):
    def get_queryset(self):
        qs = Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by('abbreviation')
        if self.q:
            qs = qs.filter(
                Q(title__icontains=self.q) |
                Q(authors__last_names__icontains=self.q) |
                Q(authors__first_names__icontains=self.q)
            ).distinct()
        return qs
