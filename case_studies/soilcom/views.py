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


# ----------- Collection System CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionSystemListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.CollectionSystem
    permission_required = 'case_studies.soilcom.view_collectionsystem'
    create_new_object_url = reverse_lazy('collection_system_create')


class CollectionSystemCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CollectionSystemModelForm
    success_url = reverse_lazy('collection_system_list')
    permission_required = 'case_studies.soilcom.add_collectionsystem'


class CollectionSystemModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectionSystemModalModelForm
    success_url = reverse_lazy('collection_system_list')
    permission_required = 'case_studies.soilcom.add_collectionsystem'


class CollectionSystemDetailView(views.OwnedObjectDetailView):
    template_name = 'collection_system_detail.html'
    model = models.CollectionSystem
    permission_required = 'case_studies.soilcom.view_collectionsystem'


class CollectionSystemModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.CollectionSystem
    permission_required = 'case_studies.soilcom.view_collectionsystem'


class CollectionSystemUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.CollectionSystem
    form_class = forms.CollectionSystemModelForm
    permission_required = 'case_studies.soilcom.change_collectionsystem'


class CollectionSystemModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.CollectionSystem
    form_class = forms.CollectionSystemModalModelForm
    permission_required = 'case_studies.soilcom.change_collectionsystem'


class CollectionSystemModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.CollectionSystem
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('collection_system_list')
    permission_required = 'case_studies.soilcom.delete_collectionsystem'


# ----------- Waste Stream Category CRUD -------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteCategoryListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.WasteCategory
    permission_required = 'case_studies.soilcom.view_wastecategory'
    create_new_object_url = reverse_lazy('waste_category_create')


class WasteCategoryCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.WasteCategoryModelForm
    success_url = reverse_lazy('waste_category_list')
    permission_required = 'case_studies.soilcom.add_wastecategory'


class WasteCategoryModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.WasteCategoryModalModelForm
    success_url = reverse_lazy('waste_category_list')
    permission_required = 'case_studies.soilcom.add_wastecategory'


class WasteCategoryDetailView(views.OwnedObjectDetailView):
    template_name = 'waste_category_detail.html'
    model = models.WasteCategory
    permission_required = 'case_studies.soilcom.view_wastecategory'


class WasteCategoryModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.WasteCategory
    permission_required = 'case_studies.soilcom.view_wastecategory'


class WasteCategoryUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.WasteCategory
    form_class = forms.WasteCategoryModelForm
    permission_required = 'case_studies.soilcom.change_wastecategory'


class WasteCategoryModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.WasteCategory
    form_class = forms.WasteCategoryModalModelForm
    permission_required = 'case_studies.soilcom.change_wastecategory'


class WasteCategoryModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.WasteCategory
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('waste_category_list')
    permission_required = 'case_studies.soilcom.delete_wastecategory'


# ----------- Waste Stream CRUD -------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class WasteStreamListView(views.OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = models.WasteStream
    permission_required = 'case_studies.soilcom.view_wastestream'
    create_new_object_url = reverse_lazy('waste_stream_create')


class WasteStreamCreateView(views.OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.WasteStreamModelForm
    success_url = reverse_lazy('waste_stream_list')
    permission_required = 'case_studies.soilcom.add_wastestream'


class WasteStreamModalCreateView(views.OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.WasteStreamModalModelForm
    success_url = reverse_lazy('waste_category_list')
    permission_required = 'case_studies.soilcom.add_wastestream'


class WasteStreamDetailView(views.OwnedObjectDetailView):
    template_name = 'waste_stream_detail.html'
    model = models.WasteStream
    permission_required = 'case_studies.soilcom.view_wastestream'


class WasteStreamModalDetailView(views.OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = models.WasteStream
    permission_required = 'case_studies.soilcom.view_wastestream'


class WasteStreamUpdateView(views.OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = models.WasteStream
    form_class = forms.WasteStreamModelForm
    permission_required = 'case_studies.soilcom.change_wastestream'


class WasteStreamModalUpdateView(views.OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = models.WasteStream
    form_class = forms.WasteStreamModalModelForm
    permission_required = 'case_studies.soilcom.change_wastestream'


class WasteStreamModalDeleteView(views.OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = models.WasteStream
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('waste_stream_list')
    permission_required = 'case_studies.soilcom.delete_wastestream'
