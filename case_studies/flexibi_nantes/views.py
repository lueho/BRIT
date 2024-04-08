from bootstrap_modal_forms.generic import BSModalCreateView, BSModalDeleteView, BSModalReadView, BSModalUpdateView
from crispy_forms.helper import FormHelper
from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Sum
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, UpdateView
from django_filters import rest_framework as rf_filters
from extra_views import CreateWithInlinesView, UpdateWithInlinesView
from rest_framework.generics import GenericAPIView

from maps.models import Catchment, GeoDataset
from maps.views import GeoDataSetDetailView
from materials.models import MaterialComponentGroup
from utils.views import (BRITFilterView, NextOrSuccessUrlMixin, OwnedObjectListView, UserOwnsObjectMixin)
from .filters import GreenhouseTypeFilter, NantesGreenhousesFilterSet
from .forms import (CultureModelForm, GreenhouseGrowthCycle, GreenhouseModalModelForm, GrowthCycleCreateForm,
                    GrowthShareFormSetHelper, GrowthTimestepInline, InlineGrowthShare,
                    UpdateGreenhouseGrowthCycleValuesForm)
from .models import Culture, Greenhouse, GrowthTimeStepSet, NantesGreenhouses
from .serializers import NantesGreenhousesGeometrySerializer


# ----------- Culture CRUD ---------------------------------------------------------------------------------------------

class CultureListView(OwnedObjectListView):
    model = Culture
    permission_required = set()


class CultureCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, BSModalCreateView):
    form_class = CultureModelForm
    template_name = '../../brit/templates/modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create new culture',
            'submit_button_text': 'Create'
        })
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class CultureDetailView(UserOwnsObjectMixin, BSModalReadView):
    model = Culture
    template_name = 'modal_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': 'Culture details',
        })
        return context


class CultureUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = Culture
    form_class = CultureModelForm
    template_name = '../../brit/templates/modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Edit culture',
            'submit_button_text': 'Edit'
        })
        return context


class CultureDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = Culture
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('culture-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Delete culture',
            'submit_button_text': 'Delete'
        })
        return context


# ----------- Greenhouse CRUD ------------------------------------------------------------------------------------------

class GreenhouseListView(BRITFilterView):
    model = Greenhouse
    filterset_class = GreenhouseTypeFilter


class GreenhouseCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, BSModalCreateView):
    form_class = GreenhouseModalModelForm
    template_name = '../../brit/templates/modal_form.html'
    success_url = reverse_lazy('greenhouse-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create new greenhouse type',
            'submit_button_text': 'Create'
        })
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class GreenhouseDetailView(DetailView):
    model = Greenhouse
    template_name = 'greenhouse_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'growth_cycles': self.object.configuration()})
        return context


class GreenhouseUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = Greenhouse
    form_class = GreenhouseModalModelForm
    template_name = '../../brit/templates/modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Edit greenhouse',
            'submit_button_text': 'Edit'
        })
        return context


class GreenhouseDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = Greenhouse
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('greenhouse-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Delete greenhouse',
            'submit_button_text': 'Delete'
        })
        return context


# ----------- Growthcycle CRUD -----------------------------------------------------------------------------------------


class GreenhouseGrowthCycleCreateView(LoginRequiredMixin, CreateWithInlinesView):
    model = GreenhouseGrowthCycle
    inlines = [GrowthTimestepInline, ]
    fields = ('culture', 'greenhouse', 'group_settings',)
    template_name = 'growth_cycle_inline_create.html'

    def get_success_url(self):
        return self.object.get_absolute_url()


class GrowthCycleCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, BSModalCreateView):
    model = GreenhouseGrowthCycle
    form_class = GrowthCycleCreateForm
    template_name = '../../brit/templates/modal_form.html'
    object = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Add growth cycle',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        if not self.request.is_ajax():
            form.instance.owner = self.request.user
            form.instance.greenhouse = Greenhouse.objects.get(id=self.kwargs.get('pk'))
            material_settings = form.instance.culture.residue
            macro_components = MaterialComponentGroup.objects.get(name='Macro Components')
            # base_group = BaseObjects.objects.get.base_group
            base_group = MaterialComponentGroup.objects.default()
            try:
                group_settings = material_settings.materialcomponentgroupsettings_set.get(group=macro_components)
            except ObjectDoesNotExist:
                group_settings = material_settings.materialcomponentgroupsettings_set.get(group=base_group)
            form.instance.group_settings = group_settings
            self.object = form.save()
            for timestep in form.cleaned_data['timesteps']:
                self.object.add_timestep(timestep)
            self.object.greenhouse.sort_growth_cycles()
        return HttpResponseRedirect(self.get_success_url())


class GrowthCycleDetailView(DetailView):
    model = GreenhouseGrowthCycle
    template_name = 'growthcycle_detail.html'

    def get_context_data(self, **kwargs):
        kwargs['table_data'] = self.object.table_data
        kwargs['growth_cycle'] = self.object
        return super().get_context_data(**kwargs)


class GrowthCycleDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = GreenhouseGrowthCycle
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('greenhouse-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Remove growth cycle',
            'submit_button_text': 'Remove'
        })
        return context


class GrowthTimeStepSetModalUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin,
                                       UpdateWithInlinesView):
    model = GrowthTimeStepSet
    inlines = [InlineGrowthShare, ]
    fields = []
    template_name = 'modal_form_with_formset.html'

    def get_context_data(self, **kwargs):
        inline_helper = GrowthShareFormSetHelper()
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


class UpdateGreenhouseGrowthCycleValuesView(LoginRequiredMixin, UpdateView):
    # TODO: Is this still required?
    model = GreenhouseGrowthCycle
    form_class = UpdateGreenhouseGrowthCycleValuesForm
    template_name = 'greenhouse_growth_cycle_update_values.html'
    object = None

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_object(self, **kwargs):
        return GreenhouseGrowthCycle.objects.get(id=self.kwargs.get('cycle_pk'))

    def get_success_url(self):
        return reverse('greenhouse-detail', kwargs={'pk': self.kwargs.get('pk')})

    def get_initial(self):
        return {
            'material': self.object.material,
            'component': self.object.component
        }


class NantesGreenhousesCatchmentAutocompleteView(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated:
            qs = Catchment.objects.filter(Q(owner=self.request.user) | Q(publication_status='published'))
        else:
            qs = Catchment.objects.filter(publication_status='published')
        dataset_region = GeoDataset.objects.get(model_name='NantesGreenhouses').region
        qs = qs.filter(region__borders__geom__within=dataset_region.geom).order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class GreenhousesMapView(GeoDataSetDetailView):
    model_name = 'NantesGreenhouses'
    template_name = 'greenhouse_map.html'
    filterset_class = NantesGreenhousesFilterSet
    map_title = 'Nantes Greenhouses'
    load_region = True
    load_catchment = True
    load_features = True
    feature_url = reverse_lazy('data.nantes_greenhouses')
    apply_filter_to_features = True
    feature_layer_style = {
        'color': '#4061d2',
        'fillOpacity': 1,
        'radius': 5,
        'stroke': False
    }
    catchment_layer_style = {
        'color': '#04555E',
        'fillOpacity': 0.1,
        'weight': 1
    }


class NantesGreenhousesAPIView(GenericAPIView):
    queryset = NantesGreenhouses.objects.all()
    serializer_class = NantesGreenhousesGeometrySerializer
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filterset_class = NantesGreenhousesFilterSet
    permission_classes = set()

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        area = queryset.aggregate(Sum('surface_ha'))['surface_ha__sum']
        area = str(round(area, 1)) if area else str(0)
        serializer = self.get_serializer(queryset, many=True)
        data = {
            'geoJson': serializer.data,
            'summaries': [
                {
                    'greenhouse_count': {'label': 'Number of greenhouses',
                                         'value': f'{len(serializer.data["features"])}'},
                    'growth_area': {'label': 'Total growth area', 'value': f'{area} ha'}
                },
            ]
        }
        return JsonResponse(data)
