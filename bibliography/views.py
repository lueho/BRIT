from dal import autocomplete
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from brit import views

from . import forms
from .filters import SourceFilter
from .models import Author, Licence, Source, SOURCE_TYPES


class BibliographyDashboardView(TemplateView):
    template_name = 'bibliography_dashboard.html'


# ----------- Author CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = Author
    permission_required = set()


class AuthorCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.AuthorModelForm
    success_url = reverse_lazy('author-list')
    permission_required = 'bibliography.add_author'


class AuthorModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.AuthorModalModelForm
    success_url = reverse_lazy('author-list')
    permission_required = 'bibliography.add_author'


class AuthorDetailView(views.OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = Author
    permission_required = set()


class AuthorModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
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


class AuthorModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = Author
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('author-list')
    permission_required = 'bibliography.delete_author'


# ----------- Licence CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class LicenceListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = Licence
    permission_required = set()


class LicenceCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.LicenceModelForm
    success_url = reverse_lazy('licence-list')
    permission_required = 'bibliography.add_licence'


class LicenceModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.LicenceModalModelForm
    success_url = reverse_lazy('licence-list')
    permission_required = 'bibliography.add_licence'


class LicenceDetailView(views.OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = Licence
    permission_required = set()


class LicenceModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
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


class LicenceModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = Licence
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('licence-list')
    permission_required = 'bibliography.delete_licence'


# ----------- Source CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class SourceListView(views.OwnedObjectListView):
    template_name = 'source_list_card.html'
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
    success_url = reverse_lazy('source-list')
    permission_required = 'bibliography.add_source'


class SourceModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.SourceModalModelForm
    success_url = reverse_lazy('source-list')
    permission_required = 'bibliography.add_source'


class SourceDetailView(views.OwnedObjectDetailView):
    template_name = 'source_detail.html'
    model = Source
    permission_required = set()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'source_dict': self.object.as_dict()
        })
        return context


class SourceModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_source_detail.html'
    model = Source
    permission_required = set()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'{self.object._meta.verbose_name} Details',
            'source_dict': self.object.as_dict()
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


class SourceModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = Source
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('source-list')
    permission_required = 'bibliography.delete_source'
