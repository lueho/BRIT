from bootstrap_modal_forms.generic import BSModalFormView, BSModalReadView, BSModalUpdateView, BSModalDeleteView
from crispy_forms.helper import FormHelper
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, TemplateView
from extra_views import UpdateWithInlinesView

from brit.views import (
    OwnedObjectListView,
    OwnedObjectCreateView,
    OwnedObjectModalCreateView,
    OwnedObjectDetailView,
    OwnedObjectModalDetailView,
    OwnedObjectUpdateView,
    OwnedObjectModalUpdateView,
    OwnedObjectDeleteView,
)
from brit.views import UserOwnsObjectMixin, NextOrSuccessUrlMixin
from distributions.models import TemporalDistribution
from distributions.plots import DoughnutChart
from . import forms
from .forms import (
    AddComponentModalForm,
    AddCompositionModalForm,
    AddLiteratureSourceForm,
    AddSeasonalVariationForm,
    ComponentModelForm,
    ComponentGroupModelForm,
    Composition,
    ComponentShareDistributionFormSetHelper,
    WeightShareUpdateFormSetHelper,
    InlineWeightShare, ComponentModalModelForm, ComponentGroupModalModelForm, ModalInlineComponentShare
)
from .models import (
    Material,
    SampleSeries,
    Sample,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialCategory, WeightShare, MaterialProperty, MaterialPropertyValue, )
from .serializers import CompositionDoughnutChartSerializer, SampleModelSerializer, SampleSeriesModelSerializer


class MaterialsDashboardView(PermissionRequiredMixin, TemplateView):
    template_name = 'materials_dashboard.html'
    permission_required = 'materials.view_material'


# ----------- Material Category CRUD ----------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------

class MaterialCategoryListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = MaterialCategory
    permission_required = set()


class MaterialCategoryCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.MaterialCategoryModelForm
    success_url = reverse_lazy('materialcategory-list')
    permission_required = 'materials.add_materialcategory'


class MaterialCategoryModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.MaterialCategoryModalModelForm
    success_url = reverse_lazy('materialcategory-list')
    permission_required = 'materials.add_materialcategory'


class MaterialCategoryDetailView(OwnedObjectDetailView):
    template_name = 'material_group_detail.html'
    model = MaterialCategory
    permission_required = set()


class MaterialCategoryModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = MaterialCategory
    permission_required = set()


class MaterialCategoryUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = MaterialCategory
    form_class = forms.MaterialCategoryModelForm
    permission_required = 'materials.change_materialcategory'


class MaterialCategoryModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = MaterialCategory
    form_class = forms.MaterialCategoryModalModelForm
    permission_required = 'materials.change_materialcategory'


class MaterialCategoryModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialCategory
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('materialcategory-list')
    permission_required = 'materials.delete_materialcategory'


# ----------- Material CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = Material
    permission_required = set()


class MaterialCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.MaterialModelForm
    success_url = reverse_lazy('material-list')
    permission_required = 'materials.add_material'


class MaterialModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.MaterialModalModelForm
    success_url = reverse_lazy('material-list')
    permission_required = 'materials.add_material'


class MaterialDetailView(OwnedObjectDetailView):
    template_name = 'material_detail.html'
    model = Material
    permission_required = set()


class MaterialModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = Material
    permission_required = set()


class MaterialUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = Material
    form_class = forms.MaterialModelForm
    permission_required = 'materials.change_material'


class MaterialModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = Material
    form_class = forms.MaterialModalModelForm
    permission_required = 'materials.change_material'


class MaterialModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = Material
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('material-list')
    permission_required = 'materials.delete_material'


# ----------- Material Components CRUD ---------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class ComponentListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = MaterialComponent
    permission_required = set()


class ComponentCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = ComponentModelForm
    success_url = reverse_lazy('materialcomponent-list')
    permission_required = 'materials.add_materialcomponent'


class ComponentModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = ComponentModalModelForm
    success_url = reverse_lazy('materialcomponent-list')
    permission_required = 'materials.add_materialcomponent'


class ComponentDetailView(OwnedObjectDetailView):
    template_name = 'component_detail.html'
    model = MaterialComponent
    permission_required = set()


class ComponentModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = MaterialComponent
    permission_required = set()


class ComponentUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = MaterialComponent
    form_class = ComponentModelForm
    permission_required = 'materials.change_materialcomponent'


class ComponentModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = MaterialComponent
    form_class = forms.ComponentModalModelForm
    permission_required = 'materials.change_materialcomponent'


class ComponentModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialComponent
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('materialcomponent-list')
    permission_required = 'materials.delete_materialcomponent'


# ----------- Material Component Groups CRUD----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ComponentGroupListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = MaterialComponentGroup
    permission_required = set()


class ComponentGroupCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = ComponentGroupModelForm
    success_url = reverse_lazy('materialcomponentgroup-list')
    permission_required = 'materials.add_materialcomponentgroup'


class ComponentGroupDetailView(OwnedObjectDetailView):
    template_name = 'componentgroup_detail.html'
    model = MaterialComponentGroup
    permission_required = set()


class ComponentGroupModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = ComponentGroupModalModelForm
    success_url = reverse_lazy('materialcomponentgroup-list')
    permission_required = 'materials.add_materialcomponentgroup'


class ComponentGroupModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = MaterialComponentGroup
    permission_required = set()


class ComponentGroupUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = MaterialComponentGroup
    form_class = ComponentGroupModelForm
    permission_required = 'materials.change_materialcomponentgroup'


class ComponentGroupModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = MaterialComponentGroup
    form_class = ComponentGroupModalModelForm
    permission_required = 'materials.change_materialcomponentgroup'


class ComponentGroupModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialComponentGroup
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('materialcomponentgroup-list')
    permission_required = 'materials.delete_materialcomponentgroup'


# ----------- Material Property CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class MaterialPropertyListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = MaterialProperty
    permission_required = set()


class MaterialPropertyCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.MaterialPropertyModelForm
    success_url = reverse_lazy('materialproperty-list')
    permission_required = 'materials.add_materialproperty'


class MaterialPropertyModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.MaterialPropertyModalModelForm
    success_url = reverse_lazy('materialproperty-list')
    permission_required = 'materials.add_materialproperty'


class MaterialPropertyDetailView(OwnedObjectDetailView):
    template_name = 'material_property_detail.html'
    model = MaterialProperty
    permission_required = set()


class MaterialPropertyModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = MaterialProperty
    permission_required = set()


class MaterialPropertyUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = MaterialProperty
    form_class = forms.MaterialPropertyModelForm
    permission_required = 'materials.change_materialproperty'


class MaterialPropertyModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = MaterialProperty
    form_class = forms.MaterialPropertyModalModelForm
    permission_required = 'materials.change_materialproperty'


class MaterialPropertyModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialProperty
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('materialproperty-list')
    permission_required = 'materials.delete_materialproperty'


# ----------- Material Property Value CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialPropertyValueModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialPropertyValue
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('home')
    permission_required = 'materials.delete_materialpropertyvalue'


# ----------- Sample Series CRUD ---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class SampleSeriesListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = SampleSeries
    permission_required = set()


class SampleSeriesCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.SampleSeriesModelForm
    success_url = reverse_lazy('sampleseries-list')
    permission_required = 'materials.add_sampleseries'


class SampleSeriesModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.SampleSeriesModalModelForm
    success_url = reverse_lazy('sampleseries-list')
    permission_required = 'materials.add_sampleseries'


class SampleSeriesDetailView(OwnedObjectDetailView):
    model = SampleSeries
    template_name = 'sample_series_detail.html'
    permission_required = set()

    def get_context_data(self, **kwargs):
        kwargs['data'] = SampleSeriesModelSerializer(self.object).data
        return super().get_context_data(**kwargs)


class SampleSeriesModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = SampleSeries
    permission_required = set()


class SampleSeriesUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = SampleSeries
    form_class = forms.SampleSeriesModelForm
    permission_required = 'materials.change_sampleseries'


class SampleSeriesModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = SampleSeries
    form_class = forms.SampleSeriesModalModelForm
    permission_required = 'materials.change_sampleseries'


class SampleSeriesModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = SampleSeries
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('sampleseries-list')
    permission_required = 'materials.delete_sampleseries'


# ----------- Sample Series Utilities ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleSeriesCreateDuplicateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = SampleSeries
    form_class = forms.SampleSeriesModelForm
    permission_required = 'materials.add_sampleseries'
    object = None

    def form_valid(self, form):
        self.object = self.object.duplicate(
            creator=self.request.user,
            **form.cleaned_data
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('sampleseries-detail', kwargs={'pk': self.object.pk})


class SampleSeriesModalCreateDuplicateView(OwnedObjectUpdateView):
    template_name = 'modal_form.html'
    model = SampleSeries
    form_class = forms.SampleSeriesModalModelForm
    permission_required = 'materials.add_sampleseries'
    object = None

    def form_valid(self, form):
        if not self.request.is_ajax():
            self.object = self.object.duplicate(
                creator=self.request.user,
                **form.cleaned_data
            )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('sampleseries-detail', kwargs={'pk': self.object.pk})


# ----------- Sample CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class SampleListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = Sample
    permission_required = set()


class FeaturedSampleListView(OwnedObjectListView):
    template_name = 'sample_list.html'
    model = Sample
    queryset = Sample.objects.filter(series__publish=True)
    permission_required = set()


class SampleCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.SampleModelForm
    success_url = reverse_lazy('sample-list')
    permission_required = 'materials.add_sample'


class SampleModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.SampleModalModelForm
    success_url = reverse_lazy('sample-list')
    permission_required = 'materials.add_sample'


class SampleDetailView(OwnedObjectDetailView):
    template_name = 'sample_detail.html'
    model = Sample
    permission_required = set()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = SampleModelSerializer(self.object, context={'request': self.request}).data
        charts = {}
        for composition in self.object.compositions.all():
            chart_data = CompositionDoughnutChartSerializer(composition).data
            chart = DoughnutChart(**chart_data)
            charts[f'composition-chart-{composition.id}'] = chart.as_dict()
        context.update({
            'data': data,
            'charts': charts
        })
        return context


class SampleModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = Sample
    permission_required = set()


class SampleUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = Sample
    form_class = forms.SampleModelForm
    permission_required = 'materials.change_sample'


class SampleModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = Sample
    form_class = forms.SampleModalModelForm
    permission_required = 'materials.change_sample'


class SampleModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = Sample
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('sample-list')
    permission_required = 'materials.delete_sample'


# ----------- Sample Utilities -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleAddPropertyView(OwnedObjectCreateView):
    form_class = forms.MaterialPropertyValueModelForm
    template_name = 'simple_form_card.html'
    permission_required = 'materials.add_materialpropertyvalue'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        property_value = form.save()
        sample = Sample.objects.get(pk=self.kwargs.get('pk'))
        sample.properties.add(property_value)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('sample-detail', kwargs={'pk': self.kwargs.get('pk')})


class SampleModalAddPropertyView(OwnedObjectModalCreateView):
    form_class = forms.MaterialPropertyValueModalModelForm
    template_name = 'modal_form.html'
    permission_required = 'materials.add_materialpropertyvalue'

    def form_valid(self, form):
        if not self.request.is_ajax():
            form.instance.owner = self.request.user
            property_value = form.save()
            sample = Sample.objects.get(pk=self.kwargs.get('pk'))
            sample.properties.add(property_value)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('sample-detail', kwargs={'pk': self.kwargs.get('pk')})


class SampleCreateDuplicateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = Sample
    form_class = forms.SampleModelForm
    permission_required = 'materials.add_sample'
    object = None

    def form_valid(self, form):
        self.object = self.object.duplicate(
            creator=self.request.user,
            **form.cleaned_data
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('sample-detail', kwargs={'pk': self.object.pk})


class SampleModalCreateDuplicateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = Sample
    form_class = forms.SampleModalModelForm
    permission_required = 'materials.add_sample'
    object = None

    def form_valid(self, form):
        if not self.request.is_ajax():
            self.object = self.object.duplicate(
                creator=self.request.user,
                **form.cleaned_data
            )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('sample-detail', kwargs={'pk': self.object.pk})


# ----------- Composition CRUD -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CompositionListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = Composition
    permission_required = set()


class CompositionCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.CompositionModelForm
    success_url = reverse_lazy('composition-list')
    permission_required = 'materials.add_composition'


class CompositionModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CompositionModalModelForm
    success_url = reverse_lazy('composition-list')
    permission_required = 'materials.add_composition'


class CompositionDetailView(OwnedObjectDetailView):
    template_name = 'composition_detail.html'
    model = Composition
    permission_required = set()


class CompositionModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = Composition
    permission_required = set()


class CompositionUpdateView(PermissionRequiredMixin, NextOrSuccessUrlMixin, UpdateWithInlinesView):
    model = Composition
    inlines = [InlineWeightShare, ]
    fields = set()
    template_name = 'composition_update.html'
    permission_required = (
        'materials.change_composition',
        'materials.change_weightshare',
    )

    def get_context_data(self, **kwargs):
        inline_helper = WeightShareUpdateFormSetHelper()
        inline_helper.form_tag = False
        form_helper = FormHelper()
        form_helper.form_tag = False
        context = {
            'inline_helper': inline_helper,
            'form_helper': form_helper
        }
        context.update(kwargs)
        return super().get_context_data(**context)


class CompositionModalUpdateView(PermissionRequiredMixin, NextOrSuccessUrlMixin, UpdateWithInlinesView):
    model = Composition
    inlines = [ModalInlineComponentShare, ]
    fields = []
    template_name = 'modal_item_formset.html'
    permission_required = (
        'materials.change_composition',
        'materials.change_weightshare',
    )

    def get_context_data(self, **kwargs):
        inline_helper = ComponentShareDistributionFormSetHelper()
        inline_helper.form_tag = False
        form_helper = FormHelper()
        form_helper.form_tag = False
        context = {
            'form_title': 'Change the composition',
            'submit_button_text': 'Save',
            'inline_helper': inline_helper,
            'form_helper': form_helper
        }
        context.update(kwargs)
        return super().get_context_data(**context)


class CompositionModalDeleteView(OwnedObjectDeleteView):
    model = Composition
    template_name = 'modal_delete.html'
    success_message = 'Successfully removed'
    success_url = reverse_lazy('composition-list')
    permission_required = 'materials.delete_composition'


# ----------- Composition utilities ------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AddComponentView(PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = Composition
    form_class = AddComponentModalForm
    template_name = 'modal_form.html'
    permission_required = 'materials.add_weightshare'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Select a component to add',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        # Due to the way the django-bootstrap modal-forms package is built, the post request and this method are
        # executed twice.
        # See: https://github.com/trco/django-bootstrap-modal-forms/issues/14
        if not self.request.is_ajax():
            self.get_object().add_component(form.cleaned_data['component'])
        return HttpResponseRedirect(self.get_success_url())


# ----------- Weight Share CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WeightShareModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = WeightShare
    success_message = 'Successfully deleted.'
    permission_required = 'materials.delete_weightshare'

    def get_success_url(self):
        return reverse('sampleseries-detail', kwargs={'pk': self.object.composition.sample.series.pk})


# ----------- Materials/Components/Groups Relation -----------------------------------------------------------------


class AddCompositionView(PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = SampleSeries
    form_class = AddCompositionModalForm
    template_name = 'modal_form.html'
    permission_required = ('materials.add_composition', 'materials.add_weightshare')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Select a component group to add',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        # Due to the way the django-bootstrap modal-forms package is built, the post request and this method are
        # executed twice.
        # See: https://github.com/trco/django-bootstrap-modal-forms/issues/14
        if not self.request.is_ajax():
            self.get_object().add_component_group(form.cleaned_data['group'],
                                                  fractions_of=form.cleaned_data['fractions_of'])
        return HttpResponseRedirect(self.get_success_url())


# For removal of component groups use CompositionModalDeleteView


class AddSourceView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalFormView):
    form_class = AddLiteratureSourceForm
    template_name = 'modal_form.html'

    def get_object(self):
        return Composition.objects.get(id=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Select a source to add',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        if not self.request.is_ajax():
            self.get_object().sources.add(form.cleaned_data['source'])
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class AddSeasonalVariationView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalFormView):
    form_class = AddSeasonalVariationForm
    template_name = 'modal_form.html'

    def get_object(self):
        return Composition.objects.get(id=self.kwargs.get('pk'))

    def get_form(self, **kwargs):
        form = super().get_form(**kwargs)
        form.fields['temporal_distribution'].queryset = TemporalDistribution.objects.exclude(
            id__in=self.get_object().blocked_distribution_ids)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Select a distribution to add',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        if not self.request.is_ajax():
            self.get_object().add_temporal_distribution(form.cleaned_data['temporal_distribution'])
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class RemoveSeasonalVariationView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalReadView):
    template_name = 'modal_delete.html'
    model = Composition

    def get_distribution(self):
        return TemporalDistribution.objects.get(id=self.kwargs.get('distribution_pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Remove seasonal variation',
            'submit_button_text': 'Remove'
        })
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def post(self, request, *args, **kwargs):
        success_url = self.get_success_url()
        self.get_object().remove_temporal_distribution(self.get_distribution())
        return HttpResponseRedirect(success_url)


class RemoveSeasonalVariationViewILD(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = Composition
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'

    def delete(self, request, *args, **kwargs):
        success_url = self.get_success_url()
        self.get_object().remove_temporal_distribution(self.get_distribution())
        return HttpResponseRedirect(success_url)

    def get_distribution(self):
        return TemporalDistribution.objects.get(id=self.kwargs.get('distribution_pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Remove seasonal variation',
            'submit_button_text': 'Remove'
        })
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class FeaturedMaterialListView(ListView):
    template_name = 'featured_materials_list.html'
    model = SampleSeries

    def get_queryset(self):
        user_groups = self.request.user.groups.all()
        return SampleSeries.objects.filter(Q(visible_to_groups__in=user_groups) | Q(publish=True))
