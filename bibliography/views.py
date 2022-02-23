from django.urls import reverse_lazy

from brit import views
from . import forms
from .models import Source


# ----------- Source CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class SourceListView(views.OwnedObjectListView):
    template_name = 'source_list_card.html'
    model = Source
    permission_required = 'bibliography.view_source'
    create_new_object_url = reverse_lazy('source-create')


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
