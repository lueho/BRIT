from django.urls import reverse_lazy

from brit import views
from . import forms
from . import models


# ----------- Collector CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectorListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.Collector
    permission_required = 'case_studies.soilcom.view_collector'
    create_new_object_url = reverse_lazy('collector_create')


class CollectorCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CollectorModelForm
    success_url = reverse_lazy('collector_list')
    permission_required = 'case_studies.soilcom.add_collector'


class CollectorModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectorModalModelForm
    success_url = reverse_lazy('collector_list')
    permission_required = 'case_studies.soilcom.add_collector'


class CollectorDetailView(views.OwnedObjectDetailView):
    template_name = 'collector_detail.html'
    model = models.Collector
    permission_required = 'case_studies.soilcom.view_collector'


class CollectorModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.Collector
    permission_required = 'case_studies.soilcom.view_collector'


class CollectorUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.Collector
    form_class = forms.CollectorModelForm
    permission_required = 'case_studies.soilcom.change_collector'


class CollectorModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.Collector
    form_class = forms.CollectorModalModelForm
    permission_required = 'case_studies.soilcom.change_collector'


class CollectorModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.Collector
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collector_list')
    permission_required = 'case_studies.soilcom.delete_collector'
