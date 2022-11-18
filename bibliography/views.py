from dal.autocomplete import Select2QuerySetView
import json

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from utils import views
from . import forms
from .filters import SourceFilter
from .models import Author, Licence, Source, SOURCE_TYPES
from .serializers import HyperlinkedSourceSerializer
from .tasks import check_source_url, check_source_urls


class BibliographyDashboardView(TemplateView):
    template_name = 'bibliography_dashboard.html'


# ----------- Author CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorListView(views.OwnedObjectListView):
    model = Author
    permission_required = set()


class AuthorCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.AuthorModelForm
    permission_required = 'bibliography.add_author'


class AuthorModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.AuthorModalModelForm
    permission_required = 'bibliography.add_author'


class AuthorDetailView(views.OwnedObjectDetailView):
    model = Author
    permission_required = set()


class AuthorModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'author_detail_modal.html'
    model = Author
    permission_required = set()


class AuthorUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = Author
    form_class = forms.AuthorModelForm
    permission_required = 'bibliography.change_author'


class AuthorModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = Author
    form_class = forms.AuthorModalModelForm
    permission_required = 'bibliography.change_author'


class AuthorModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Author
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('author-list')
    permission_required = 'bibliography.delete_author'


# ----------- Licence CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class LicenceListView(views.OwnedObjectListView):
    model = Licence
    permission_required = set()


class LicenceCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.LicenceModelForm
    permission_required = 'bibliography.add_licence'


class LicenceModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.LicenceModalModelForm
    permission_required = 'bibliography.add_licence'


class LicenceDetailView(views.OwnedObjectDetailView):
    model = Licence
    permission_required = set()


class LicenceModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'licence_detail_modal.html'
    model = Licence
    permission_required = set()


class LicenceUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = Licence
    form_class = forms.LicenceModelForm
    permission_required = 'bibliography.change_licence'


class LicenceModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = Licence
    form_class = forms.LicenceModalModelForm
    permission_required = 'bibliography.change_licence'


class LicenceModalDeleteView(views.OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Licence
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('licence-list')
    permission_required = 'bibliography.delete_licence'


# ----------- Source CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class SourceListView(views.OwnedObjectListView):
    model = Source
    queryset = Source.objects.filter(type__in=[t[0] for t in SOURCE_TYPES]).order_by('abbreviation')
    filterset_class = SourceFilter
    filterset = None
    permission_required = set()

    def get_queryset(self):
        queryset = super().get_queryset()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filterset
        return context


class SourceCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.SourceModelForm
    permission_required = 'bibliography.add_source'


class SourceModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.SourceModalModelForm
    permission_required = 'bibliography.add_source'


class SourceDetailView(views.OwnedObjectDetailView):
    model = Source
    permission_required = set()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        serializer = HyperlinkedSourceSerializer(self.object, context={'request': self.request})
        context.update({
            'object_data': serializer.data
        })
        return context


class SourceModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'source_detail_modal.html'
    model = Source
    permission_required = set()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        serializer = HyperlinkedSourceSerializer(self.object, context={'request': self.request})
        context.update({
            'modal_title': 'Source details',
            'object_data': serializer.data
        })
        return context


class SourceUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = Source
    form_class = forms.SourceModelForm
    permission_required = 'bibliography.change_source'


class SourceModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = Source
    form_class = forms.SourceModalModelForm
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
            qs = qs.filter(Q(title__icontains=self.q) | Q(authors__last_names__icontains=self.q) | Q(authors__first_names__icontains=self.q)).distinct()
        return qs
