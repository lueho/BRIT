from bootstrap_modal_forms.generic import BSModalDeleteView, BSModalFormView, BSModalReadView, BSModalUpdateView
from crispy_forms.helper import FormHelper
from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, RedirectView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from extra_views import UpdateWithInlinesView

from bibliography.forms import SourceSimpleFilterForm
from distributions.models import TemporalDistribution
from distributions.plots import DoughnutChart
from utils.views import (NextOrSuccessUrlMixin, OwnedObjectCreateView, OwnedObjectDetailView,
                         OwnedObjectListView, OwnedObjectModalCreateView, OwnedObjectModalDeleteView,
                         OwnedObjectModalDetailView, OwnedObjectModalUpdateView, OwnedObjectUpdateView,
                         PublishedObjectFilterView, UserOwnedObjectFilterView, UserOwnsObjectMixin)
from .filters import SampleFilter, SampleSeriesFilter
from .forms import (AddComponentModalForm, AddCompositionModalForm, AddLiteratureSourceForm, AddSeasonalVariationForm,
                    ComponentGroupModalModelForm, ComponentGroupModelForm, ComponentModalModelForm, ComponentModelForm,
                    ComponentShareDistributionFormSetHelper, Composition, CompositionModalModelForm,
                    CompositionModelForm, InlineWeightShare, MaterialCategoryModalModelForm, MaterialCategoryModelForm,
                    MaterialModalModelForm, MaterialModelForm, MaterialPropertyModalModelForm,
                    MaterialPropertyModelForm, MaterialPropertyValueModalModelForm, MaterialPropertyValueModelForm,
                    ModalInlineComponentShare, SampleModalModelForm, SampleModelForm,
                    SampleSeriesAddTemporalDistributionModalModelForm, SampleSeriesModalModelForm,
                    SampleSeriesModelForm, WeightShareUpdateFormSetHelper)
from .models import (Material, MaterialCategory, MaterialComponent, MaterialComponentGroup, MaterialProperty,
                     MaterialPropertyValue, Sample, SampleSeries, WeightShare)
from .serializers import (CompositionDoughnutChartSerializer, SampleModelSerializer, SampleSeriesModelSerializer)


class MaterialsDashboardView(PermissionRequiredMixin, TemplateView):
    template_name = 'materials_dashboard.html'
    permission_required = 'materials.change_material'


# ----------- Material Category CRUD ----------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------

class MaterialCategoryListView(OwnedObjectListView):
    model = MaterialCategory
    permission_required = set()


class MaterialCategoryCreateView(OwnedObjectCreateView):
    form_class = MaterialCategoryModelForm
    permission_required = 'materials.add_materialcategory'


class MaterialCategoryModalCreateView(OwnedObjectModalCreateView):
    form_class = MaterialCategoryModalModelForm
    permission_required = 'materials.add_materialcategory'


class MaterialCategoryDetailView(OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = MaterialCategory
    permission_required = set()


class MaterialCategoryModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = MaterialCategory
    permission_required = set()


class MaterialCategoryUpdateView(OwnedObjectUpdateView):
    model = MaterialCategory
    form_class = MaterialCategoryModelForm
    permission_required = 'materials.change_materialcategory'


class MaterialCategoryModalUpdateView(OwnedObjectModalUpdateView):
    model = MaterialCategory
    form_class = MaterialCategoryModalModelForm
    permission_required = 'materials.change_materialcategory'


class MaterialCategoryModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialCategory
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('materialcategory-list')
    permission_required = 'materials.delete_materialcategory'


# ----------- Material CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialListView(OwnedObjectListView):
    model = Material
    queryset = Material.objects.filter(type='material')
    permission_required = set()


class MaterialCreateView(OwnedObjectCreateView):
    form_class = MaterialModelForm
    permission_required = 'materials.add_material'


class MaterialModalCreateView(OwnedObjectModalCreateView):
    form_class = MaterialModalModelForm
    permission_required = 'materials.add_material'


class MaterialDetailView(OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = Material
    permission_required = set()


class MaterialModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = Material
    permission_required = set()


class MaterialUpdateView(OwnedObjectUpdateView):
    model = Material
    form_class = MaterialModelForm
    permission_required = 'materials.change_material'


class MaterialModalUpdateView(OwnedObjectModalUpdateView):
    model = Material
    form_class = MaterialModalModelForm
    permission_required = 'materials.change_material'


class MaterialModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Material
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('material-list')
    permission_required = 'materials.delete_material'


# ----------- Material Utils -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Material.objects.filter(type='material').order_by('id')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


# ----------- Material Components CRUD ---------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class ComponentListView(OwnedObjectListView):
    model = MaterialComponent
    permission_required = set()


class ComponentCreateView(OwnedObjectCreateView):
    form_class = ComponentModelForm
    permission_required = 'materials.add_materialcomponent'


class ComponentModalCreateView(OwnedObjectModalCreateView):
    form_class = ComponentModalModelForm
    permission_required = 'materials.add_materialcomponent'


class ComponentDetailView(OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = MaterialComponent
    permission_required = set()


class ComponentModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = MaterialComponent
    permission_required = set()


class ComponentUpdateView(OwnedObjectUpdateView):
    model = MaterialComponent
    form_class = ComponentModelForm
    permission_required = 'materials.change_materialcomponent'


class ComponentModalUpdateView(OwnedObjectModalUpdateView):
    model = MaterialComponent
    form_class = ComponentModalModelForm
    permission_required = 'materials.change_materialcomponent'


class ComponentModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialComponent
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('materialcomponent-list')
    permission_required = 'materials.delete_materialcomponent'


# ----------- Material Component Groups CRUD----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ComponentGroupListView(OwnedObjectListView):
    model = MaterialComponentGroup
    permission_required = set()


class ComponentGroupCreateView(OwnedObjectCreateView):
    form_class = ComponentGroupModelForm
    permission_required = 'materials.add_materialcomponentgroup'


class ComponentGroupDetailView(OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = MaterialComponentGroup
    permission_required = set()


class ComponentGroupModalCreateView(OwnedObjectModalCreateView):
    form_class = ComponentGroupModalModelForm
    permission_required = 'materials.add_materialcomponentgroup'


class ComponentGroupModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = MaterialComponentGroup
    permission_required = set()


class ComponentGroupUpdateView(OwnedObjectUpdateView):
    model = MaterialComponentGroup
    form_class = ComponentGroupModelForm
    permission_required = 'materials.change_materialcomponentgroup'


class ComponentGroupModalUpdateView(OwnedObjectModalUpdateView):
    model = MaterialComponentGroup
    form_class = ComponentGroupModalModelForm
    permission_required = 'materials.change_materialcomponentgroup'


class ComponentGroupModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialComponentGroup
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('materialcomponentgroup-list')
    permission_required = 'materials.delete_materialcomponentgroup'


# ----------- Material Property CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class MaterialPropertyListView(OwnedObjectListView):
    model = MaterialProperty
    permission_required = set()


class MaterialPropertyCreateView(OwnedObjectCreateView):
    form_class = MaterialPropertyModelForm
    permission_required = 'materials.add_materialproperty'


class MaterialPropertyModalCreateView(OwnedObjectModalCreateView):
    form_class = MaterialPropertyModalModelForm
    permission_required = 'materials.add_materialproperty'


class MaterialPropertyDetailView(OwnedObjectDetailView):
    template_name = 'simple_detail_card.html'
    model = MaterialProperty
    permission_required = set()


class MaterialPropertyModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = MaterialProperty
    permission_required = set()


class MaterialPropertyUpdateView(OwnedObjectUpdateView):
    model = MaterialProperty
    form_class = MaterialPropertyModelForm
    permission_required = 'materials.change_materialproperty'


class MaterialPropertyModalUpdateView(OwnedObjectModalUpdateView):
    model = MaterialProperty
    form_class = MaterialPropertyModalModelForm
    permission_required = 'materials.change_materialproperty'


class MaterialPropertyModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialProperty
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('materialproperty-list')
    permission_required = 'materials.delete_materialproperty'


# ----------- Material Property Value CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialPropertyValueModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialPropertyValue
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('home')
    permission_required = 'materials.delete_materialpropertyvalue'


# ----------- Sample Series CRUD ---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PublishedSampleSeriesListView(PublishedObjectFilterView):
    model = SampleSeries
    filterset_class = SampleSeriesFilter


class UserOwnedSampleSeriesListView(UserOwnedObjectFilterView):
    model = SampleSeries
    filterset_class = SampleSeriesFilter


class SampleSeriesCreateView(OwnedObjectCreateView):
    form_class = SampleSeriesModelForm
    permission_required = 'materials.add_sampleseries'


class SampleSeriesModalCreateView(OwnedObjectModalCreateView):
    form_class = SampleSeriesModalModelForm
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
    model = SampleSeries
    form_class = SampleSeriesModelForm
    permission_required = 'materials.change_sampleseries'


class SampleSeriesModalUpdateView(OwnedObjectModalUpdateView):
    model = SampleSeries
    form_class = SampleSeriesModalModelForm
    permission_required = 'materials.change_sampleseries'


class SampleSeriesModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = SampleSeries
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('sampleseries-list')
    permission_required = 'materials.delete_sampleseries'


# ----------- Sample Series Utilities ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleSeriesCreateDuplicateView(OwnedObjectUpdateView):
    model = SampleSeries
    form_class = SampleSeriesModelForm
    permission_required = 'materials.add_sampleseries'
    object = None

    def form_valid(self, form):
        self.object = self.object.duplicate(creator=self.request.user, **form.cleaned_data)
        return super().form_valid(form)


class SampleSeriesModalCreateDuplicateView(OwnedObjectModalUpdateView):
    model = SampleSeries
    form_class = SampleSeriesModalModelForm
    permission_required = 'materials.add_sampleseries'
    object = None

    def form_valid(self, form):
        self.object = self.object.duplicate(creator=self.request.user, **form.cleaned_data)
        return super().form_valid(form)


class SampleSeriesModalAddDistributionView(OwnedObjectModalUpdateView):
    model = SampleSeries
    form_class = SampleSeriesAddTemporalDistributionModalModelForm
    permission_required = 'materials.change_sampleseries'

    def form_valid(self, form):
        self.object.temporal_distributions.add(form.cleaned_data['distribution'])
        return HttpResponseRedirect(self.get_success_url())


class SampleSeriesAutoCompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return SampleSeries.objects.none()

        qs = SampleSeries.objects.filter(owner=self.request.user)

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs


# ----------- Sample CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PublishedSampleListView(PublishedObjectFilterView):
    model = Sample
    filterset_class = SampleFilter


class UserOwnedSampleListView(UserOwnedObjectFilterView):
    model = Sample
    filterset_class = SampleFilter


class FeaturedSampleListView(OwnedObjectListView):
    template_name = 'featured_sample_list.html'
    model = Sample
    queryset = Sample.objects.filter(series__publish=True)
    permission_required = set()


class SampleCreateView(LoginRequiredMixin, OwnedObjectCreateView):
    form_class = SampleModelForm
    permission_required = set()


class SampleModalCreateView(OwnedObjectModalCreateView):
    form_class = SampleModalModelForm
    permission_required = 'materials.add_sample'


class SampleDetailView(OwnedObjectDetailView):
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


class SampleUpdateView(OwnedObjectUpdateView):
    model = Sample
    form_class = SampleModelForm
    permission_required = 'materials.change_sample'


class SampleModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = Sample
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('sample-list')
    permission_required = 'materials.delete_sample'


# ----------- Sample Utilities -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleAutoCompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Sample.objects.order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class SampleAddPropertyView(OwnedObjectCreateView):
    form_class = MaterialPropertyValueModelForm
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
    form_class = MaterialPropertyValueModalModelForm
    permission_required = 'materials.add_materialpropertyvalue'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        property_value = form.save()
        sample = Sample.objects.get(pk=self.kwargs.get('pk'))
        sample.properties.add(property_value)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('sample-detail', kwargs={'pk': self.kwargs.get('pk')})


class SampleAddSourceView(OwnedObjectUpdateView):
    model = Sample
    form_class = SourceSimpleFilterForm
    permission_required = 'materials.change_sample'

    def form_valid(self, form):
        self.object.sources.add(form.cleaned_data['source'])
        return HttpResponseRedirect(self.get_success_url())


class SampleCreateDuplicateView(OwnedObjectUpdateView):
    model = Sample
    form_class = SampleModelForm
    permission_required = 'materials.add_sample'
    object = None

    def form_valid(self, form):
        self.object = self.object.duplicate(creator=self.request.user, **form.cleaned_data)
        return super().form_valid(form)


class SampleModalCreateDuplicateView(OwnedObjectModalUpdateView):
    model = Sample
    form_class = SampleModalModelForm
    permission_required = 'materials.add_sample'
    object = None

    def form_valid(self, form):
        self.object = self.object.duplicate(creator=self.request.user, **form.cleaned_data)
        return super().form_valid(form)


# ----------- Composition CRUD -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CompositionListView(OwnedObjectListView):
    model = Composition
    permission_required = set()


class CompositionCreateView(OwnedObjectCreateView):
    form_class = CompositionModelForm
    permission_required = 'materials.add_composition'


class CompositionModalCreateView(OwnedObjectModalCreateView):
    form_class = CompositionModalModelForm
    permission_required = 'materials.add_composition'


class CompositionDetailView(OwnedObjectDetailView):
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
    template_name = 'modal_form_with_formset.html'
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


class CompositionModalDeleteView(OwnedObjectModalDeleteView):
    model = Composition
    template_name = 'modal_delete.html'
    success_message = 'Successfully removed'
    success_url = reverse_lazy('composition-list')
    permission_required = 'materials.delete_composition'

    def get_success_url(self):
        return reverse('sample-detail', kwargs={'pk': self.object.sample.pk})


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
        self.get_object().add_component(form.cleaned_data['component'])
        return HttpResponseRedirect(self.get_success_url())


class CompositionOrderUpView(PermissionRequiredMixin, SingleObjectMixin, RedirectView):
    model = Composition
    object = None
    permission_required = 'materials.change_composition'

    def get_redirect_url(self, *args, **kwargs):
        return reverse('sample-detail', kwargs={'pk': self.object.sample.pk})

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.order_up()
        return super().get(request, *args, **kwargs)


class CompositionOrderDownView(PermissionRequiredMixin, SingleObjectMixin, RedirectView):
    model = Composition
    object = None
    permission_required = 'materials.change_composition'

    def get_redirect_url(self, *args, **kwargs):
        return reverse('sample-detail', kwargs={'pk': self.object.sample.pk})

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.order_down()
        return super().get(request, *args, **kwargs)


# ----------- Weight Share CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WeightShareModalDeleteView(OwnedObjectModalDeleteView):
    template_name = 'modal_delete.html'
    model = WeightShare
    success_message = 'Successfully deleted.'
    permission_required = 'materials.delete_weightshare'

    def get_success_url(self):
        return reverse('sample-detail', kwargs={'pk': self.object.composition.sample.pk})


# ----------- Materials/Components/Groups Relation -----------------------------------------------------------------


class AddCompositionView(PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = SampleSeries
    form_class = AddCompositionModalForm
    template_name = 'modal_form.html'
    permission_required = ('materials.add_composition', 'materials.add_weightshare')
    success_message = 'Composition successfully added.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Select a component group to add',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        self.get_object().add_component_group(
            form.cleaned_data['group'],
            fractions_of=form.cleaned_data['fractions_of']
        )
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
        return SampleSeries.objects.filter(publish=True)
