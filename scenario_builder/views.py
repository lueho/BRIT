from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, View, UpdateView
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.edit import FormMixin, ModelFormMixin
from rest_framework.views import APIView

from flexibi_dst.views import DualUserListView
from layer_manager.models import Layer
from .forms import (
    CatchmentForm,
    CatchmentQueryForm,
    MaterialAddComponentGroupForm,
    MaterialModelForm,
    MaterialComponentModelForm,
    MaterialComponentGroupModelForm,
    MaterialComponentGroupAddComponentForm,
    MaterialComponentGroupSettings,
    MaterialComponentShareModelForm,
    ScenarioModelForm,
    ScenarioInventoryConfigurationAddForm,
    ScenarioInventoryConfigurationUpdateForm,
    SeasonalDistributionModelForm,
)
from .models import (
    Catchment,
    Scenario,
    ScenarioInventoryConfiguration,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialComponentShare,
    GeoDataset,
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    Region,
    ScenarioStatus,
)
from .serializers import CatchmentSerializer, BaseResultMapSerializer, RegionSerializer
from .tasks import run_inventory


# ----------- Catchments -----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CatchmentBrowseView(FormMixin, ListView):
    model = Catchment
    form_class = CatchmentQueryForm
    template_name = 'catchment_list.html'


class CatchmentCreateView(LoginRequiredMixin, CreateView):
    template_name = 'catchment_create.html'
    form_class = CatchmentForm
    success_url = reverse_lazy('catchment_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class CatchmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Catchment
    form_class = CatchmentForm

    def get_success_url(self):
        return reverse('catchment_list')

    def test_func(self):
        catchment = Catchment.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == catchment.owner


class CatchmentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Catchment
    success_url = reverse_lazy('catchment_list')

    def test_func(self):
        catchment = Catchment.objects.get(id=self.kwargs.get('pk'))
        return catchment.owner == self.request.user


def load_catchment_options(request):
    if request.GET.get('region_id'):
        region = Region.objects.get(id=request.GET.get('region_id'))
        catchment_owners = []
        if int(request.GET.get('category_standard')):
            catchment_owners.append(User.objects.get(username='flexibi'))
        if int(request.GET.get('category_custom')) and request.user.is_authenticated:
            catchment_owners.append(request.user)
        catchments = Catchment.objects.filter(region=region, owner__in=catchment_owners)
    else:
        catchments = Catchment.objects.none()
    return render(request, 'catchment_dropdown_list_options.html', {'catchments': catchments})


class CatchmentGeometryAPI(APIView):

    def get(self, request, *args, **kwargs):
        print(self.request.GET.get('catchment_id'))
        catchments = Catchment.objects.filter(id=self.request.GET.get('catchment_id'))
        serializer = CatchmentSerializer(catchments, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)


# ----------- Materials/Feedstocks -------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialListView(DualUserListView):
    model = Material
    template_name = 'material_list.html'


class MaterialCreateView(LoginRequiredMixin, CreateView):
    form_class = MaterialModelForm
    template_name = 'material_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('material_detail', kwargs={'scenario_pk': 0, 'material_pk': self.object.pk})


class MaterialDetailView(TemplateResponseMixin, FormMixin, View):
    model = Material
    template_name = 'material_detail.html'
    form_class = MaterialAddComponentGroupForm
    initial = {}
    scenario = None
    material = None
    object = None

    def get(self, request, *args, **kwargs):
        self.get_objects()
        self.initial = {
            'scenario': self.scenario,
            'material': self.material
        }
        context = {
            'view': self,
            'object': self.material,
            'material': self.material,
            'scenario': self.scenario,
            'composition': self.material.grouped_component_shares(scenario=self.scenario),
            'form': self.get_form
        }
        return self.render_to_response(context)

    def get_objects(self):
        self.scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        self.material = Material.objects.get(id=self.kwargs.get('material_pk'))

    def get_success_url(self):
        return reverse('material_detail',
                       kwargs={
                           'material_pk': self.material.id,
                           'scenario_pk': self.scenario.id
                       }
                       )

    def post(self, request, *args, **kwargs):
        self.get_objects()
        if 'add_group' in self.request.POST:
            form = self.get_form()
            if form.is_valid():
                form.save()
                return HttpResponseRedirect(self.get_success_url())
            else:
                return self.form_invalid(form)
        else:
            return HttpResponseRedirect(self.get_success_url())


class MaterialUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Material
    form_class = MaterialModelForm
    template_name = 'material_update.html'
    success_url = '/scenario_builder/materials/{id}'

    def get_object(self, **kwargs):
        return self.model.objects.get(id=self.kwargs.get('material_pk'))

    def test_func(self):
        material = Material.objects.get(id=self.kwargs.get('material_pk'))
        return material.owner == self.request.user


class MaterialDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Material
    template_name = 'material_delete.html'
    success_url = '/scenario_builder/materials'

    def get_object(self, **kwargs):
        return self.model.objects.get(id=self.kwargs.get('material_pk'))

    def test_func(self):
        material = Material.objects.get(id=self.kwargs.get('material_pk'))
        return material.owner == self.request.user


class MaterialComponentGroupListView(DualUserListView):
    model = MaterialComponentGroup
    template_name = 'material_component_group_list.html'


class MaterialComponentGroupCreateView(LoginRequiredMixin, CreateView):
    form_class = MaterialComponentGroupModelForm
    template_name = 'material_component_group_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('material_component_group_detail', kwargs={'pk': self.object.pk})


class MaterialComponentGroupDetailView(DetailView):
    model = MaterialComponentGroup
    template_name = 'material_component_group_detail.html'


class MaterialComponentGroupCompositionDetailView(DetailView):
    model = MaterialComponentGroup
    template_name = 'material_component_group_composition.html'
    object = None

    def get_object(self, **kwargs):
        return self.model.objects.get(id=self.kwargs.get('group_pk'))

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        context['grouped_component_shares'] = self.object.grouped_component_shares()
        return self.render_to_response(context)


class MaterialComponentGroupUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    form_class = MaterialComponentModelForm
    template_name = 'material_component_group_update.html'
    object = None

    def get_object(self, **kwargs):
        return MaterialComponentGroup.objects.get(id=self.kwargs.get('pk'))

    def get_success_url(self):
        return reverse('material_component_group_detail', kwargs={'pk': self.object.id})

    def test_func(self):
        self.object = self.get_object()
        return self.request.user == self.object.owner

    def form_valid(self, form):
        self.object = form.save()
        return redirect('material_component_group_detail', pk=self.kwargs.get('pk'))


class MaterialComponentGroupDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = MaterialComponentGroup
    template_name = 'material_component_group_delete.html'
    success_url = '/scenario_builder/materialcomponentgroups/'

    def get_object(self, **kwargs):
        return MaterialComponentGroup.objects.get(id=self.kwargs.get('pk'))

    def test_func(self):
        group = MaterialComponentGroup.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == group.owner


class MaterialComponentGroupCompositionView(TemplateResponseMixin, FormMixin, View):
    model = MaterialComponentGroup
    template_name = 'material_component_group_composition.html'
    form_class = MaterialComponentGroupAddComponentForm
    initial = {}
    group = None
    scenario = None
    material = None

    def get(self, request, *args, **kwargs):
        self.get_objects()
        self.initial = {
            'owner': self.request.user,
            'scenario': self.scenario,
            'material': self.material,
            'group': self.group
        }
        context = {
            'view': self,
            'object': self.group,
            'material': self.material,
            'scenario': self.scenario,
            'composition': MaterialComponentShare.objects.filter(scenario=self.scenario,
                                                                 material=self.material,
                                                                 group=self.group),
            'form': self.get_form
        }
        return self.render_to_response(context)

    def get_objects(self):
        self.group = MaterialComponentGroup.objects.get(id=self.kwargs.get('group_pk'))
        self.scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        self.material = Material.objects.get(id=self.kwargs.get('material_pk'))

    def get_success_url(self):
        return reverse('material_component_group_composition',
                       kwargs={'group_pk': self.group.id,
                               'material_pk': self.material.id,
                               'scenario_pk': self.scenario.id
                               }
                       )

    def post(self, request, *args, **kwargs):
        self.get_objects()
        if 'add_component' in self.request.POST:
            form = self.get_form()
            if form.is_valid():
                form.save()
                return HttpResponseRedirect(self.get_success_url())
            else:
                return self.form_invalid(form)
        elif 'remove_component' in self.request.POST:
            share = MaterialComponentShare.objects.get(id=self.request.POST['remove_component'])
            share.delete()
            return HttpResponseRedirect(self.get_success_url())
        else:
            return HttpResponseRedirect(self.get_success_url())


class MaterialComponentShareUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = MaterialComponentShare
    form_class = MaterialComponentShareModelForm
    template_name = 'material_component_group_share_update.html'

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        else:
            return reverse('material_component_group_list')

    def test_func(self):
        return True


class MaterialComponentGroupAddComponentView(LoginRequiredMixin, UserPassesTestMixin, TemplateResponseMixin, FormMixin,
                                             View):
    model = MaterialComponentShare
    form_class = MaterialComponentGroupAddComponentForm
    template_name = 'material_component_group_add_component.html'
    group = None
    scenario = None
    material = None
    group_settings = None

    def get(self, request, **kwargs):
        self.get_objects()
        self.initial = {
            'scenario': self.scenario,
            'material': self.material,
            'group': self.group,
            'group_settings': self.group_settings
        }
        context = {
            'view': self,
            'object': self.group,
            'material': self.material,
            'scenario': self.scenario,
            'group_settings': self.group_settings,
            'form': self.get_form
        }
        return self.render_to_response(context)

    def get_objects(self):
        self.group = MaterialComponentGroup.objects.get(id=self.kwargs.get('group_pk'))
        self.scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        self.material = Material.objects.get(id=self.kwargs.get('material_pk'))
        self.group_settings = MaterialComponentGroupSettings.objects.get(group=self.group, scenario=self.scenario,
                                                                         material=self.material)

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        else:
            return reverse('material_detail', kwargs={'scenario_pk': self.scenario.id, 'material_pk': self.material.id})

    def post(self, request, *args, **kwargs):
        self.get_objects()
        form = self.get_form()
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.form_invalid(form)

    def test_func(self):
        group = MaterialComponentGroup.objects.get(id=self.kwargs.get('group_pk'))
        return self.request.user == group.owner


class MaterialComponentGroupRemoveComponentView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    object = None

    def test_func(self):
        return True

    def get(self, request, *args, **kwargs):
        self.object = MaterialComponentShare.objects.get(id=self.kwargs.get('pk'))
        self.object.delete()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        else:
            return self.object.get_absolute_url()


class MaterialComponentListView(DualUserListView):
    model = MaterialComponentGroup
    template_name = 'material_component_list.html'


class MaterialComponentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    form_class = MaterialComponentModelForm
    template_name = 'material_component_create.html'
    object = None

    def test_func(self):
        material = Material.objects.get(id=self.kwargs.get('material_pk'))
        return self.request.user == material.owner

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.material = Material.objects.get(id=self.kwargs.get('material_pk'))
        self.object = form.save()
        return redirect('material_detail', scenario_pk=0, material_pk=self.kwargs.get('material_pk'))


class MaterialComponentDetailView(DetailView):
    model = MaterialComponentGroup
    template_name = 'material_component_detail.html'


class MaterialComponentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    form_class = MaterialComponentModelForm
    template_name = 'material_component_update.html'
    object = None

    def get_object(self, **kwargs):
        return MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))

    def test_func(self):
        component = MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))
        return self.request.user == component.owner

    def form_valid(self, form):
        self.object = form.save()
        return redirect('material_detail', scenario_pk=0, material_pk=self.kwargs.get('pk'))


class MaterialComponentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = MaterialComponent
    template_name = 'material_component_delete.html'
    success_url = '/scenario_builder/materials/{material_id}'

    def get_object(self, **kwargs):
        return MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))

    def test_func(self):
        component = MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))
        return self.request.user == component.owner


class SeasonalDistributionCreateView(LoginRequiredMixin, CreateView):
    form_class = SeasonalDistributionModelForm
    template_name = 'seasonal_distribution_create.html'
    success_url = '/scenario_builder/materials/{material_id}'


# ----------- Regions --------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionGeometryAPI(APIView):

    def get(self, request, *args, **kwargs):
        regions = Region.objects.filter(id=self.request.GET.get('region_id'))
        serializer = RegionSerializer(regions, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)


# ----------- Scenarios ------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class ScenarioListView(DualUserListView):
    model = Scenario
    template_name = 'scenario_list.html'


class ScenarioCreateView(LoginRequiredMixin, CreateView):
    model = Scenario
    form_class = ScenarioModelForm
    template_name = 'scenario_create.html'
    success_url = reverse_lazy('scenario_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class ScenarioUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Scenario
    template_name = 'scenario_create.html'
    form_class = ScenarioModelForm

    def get_success_url(self):
        return reverse('scenario_detail', kwargs={'pk': self.object.id})

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == scenario.owner


class ScenarioDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Scenario
    template_name = 'scenario_delete.html'
    success_url = '/scenario_builder/scenarios'

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == scenario.owner


def get_evaluation_status(request, task_id=None):
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result,
        "task_info": task_result.info
    }
    return JsonResponse(result, status=200)


class ScenarioDetailView(UserPassesTestMixin, DetailView):
    """Summary of the Scenario with complete configuration. Page for final review, which also contains the
    'run' button."""

    model = Scenario
    template_name = 'scenario_detail.html'
    object = None
    config = None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.config = self.object.configuration_for_template()
        context = self.get_context_data(object=self.object)
        context['config'] = self.config
        context['static'] = self.object.owner.username == 'flexibi'
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        scenario = self.object
        scenario.set_status(ScenarioStatus.Status.RUNNING)
        run_inventory(scenario.id)
        return redirect('scenario_result', scenario.id)

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == scenario.owner or scenario.owner.username == 'flexibi'


class ScenarioAddInventoryAlgorithmView(LoginRequiredMixin, UserPassesTestMixin,
                                        TemplateResponseMixin, ModelFormMixin, View):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationAddForm
    template_name = 'scenario_configuration_add.html'
    object = None

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('pk'))
        return self.request.user == scenario.owner

    @staticmethod
    def post(request, *args, **kwargs):
        scenario_id = request.POST.get('scenario')
        scenario = Scenario.objects.get(id=scenario_id)
        feedstock = Material.objects.get(id=request.POST.get('feedstock'))
        algorithm_id = request.POST.get('inventory_algorithm')
        algorithm = InventoryAlgorithm.objects.get(id=algorithm_id)
        parameters = algorithm.inventoryalgorithmparameter_set.all()
        values = {}
        for parameter in parameters:
            values[parameter] = []
            parameter_id = 'parameter_' + str(parameter.pk)
            if parameter_id in request.POST:
                value_id = request.POST.get(parameter_id)
                values[parameter].append(InventoryAlgorithmParameterValue.objects.get(id=value_id))
        scenario.add_inventory_algorithm(feedstock, algorithm, values)
        return redirect('scenario_detail', pk=scenario_id)

    def get_object(self, **kwargs):
        return Scenario.objects.get(pk=self.kwargs.get('pk'))

    def get_initial(self):
        return {
            'feedstocks': self.object.available_feedstocks(),
            'scenario': self.object
        }

    def get_context_data(self, **kwargs):
        context = {'scenario': self.object,
                   'form': self.get_form()}
        return super().get_context_data(**context)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class ScenarioAlgorithmConfigurationUpdateView(LoginRequiredMixin, UserPassesTestMixin,
                                               TemplateResponseMixin, ModelFormMixin, View):
    model = ScenarioInventoryConfiguration
    form_class = ScenarioInventoryConfigurationUpdateForm
    template_name = 'scenario_configuration_update.html'
    object = None

    def test_func(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        return self.request.user == scenario.owner

    @staticmethod
    def post(request, *args, **kwargs):
        scenario = Scenario.objects.get(id=request.POST.get('scenario'))
        current_algorithm = InventoryAlgorithm.objects.get(id=request.POST.get('current_algorithm'))
        feedstock = Material.objects.get(id=request.POST.get('feedstock'))
        scenario.remove_inventory_algorithm(current_algorithm, feedstock)
        new_algorithm = InventoryAlgorithm.objects.get(id=request.POST.get('inventory_algorithm'))
        parameters = new_algorithm.inventoryalgorithmparameter_set.all()
        values = {}
        for parameter in parameters:
            values[parameter] = []
            parameter_id = 'parameter_' + str(parameter.pk)
            if parameter_id in request.POST:
                value_id = request.POST.get(parameter_id)
                values[parameter].append(InventoryAlgorithmParameterValue.objects.get(id=value_id))
        scenario.add_inventory_algorithm(feedstock, new_algorithm, values)
        return redirect('scenario_detail', pk=request.POST.get('scenario'))

    def get_object(self, **kwargs):
        return Scenario.objects.get(pk=self.kwargs.get('scenario_pk'))

    def get_initial(self):
        scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        algorithm = InventoryAlgorithm.objects.get(id=self.kwargs.get('algorithm_pk'))
        config = scenario.inventory_algorithm_config(algorithm)
        return config

    def get_context_data(self, **kwargs):
        context = self.get_initial()
        context['form'] = self.get_form()
        return super().get_context_data(**context)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class ScenarioRemoveInventoryAlgorithmView(LoginRequiredMixin, UserPassesTestMixin, View):
    scenario = None
    algorithm = None
    feedstock = None

    def test_func(self):
        self.scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        return self.scenario.owner == self.request.user

    def get(self, request, *args, **kwargs):
        self.scenario = Scenario.objects.get(id=self.kwargs.get('scenario_pk'))
        self.algorithm = InventoryAlgorithm.objects.get(id=self.kwargs.get('algorithm_pk'))
        self.feedstock = Material.objects.get(id=self.kwargs.get('feedstock_pk'))
        self.scenario.remove_inventory_algorithm(algorithm=self.algorithm, feedstock=self.feedstock)
        return redirect('scenario_detail', pk=self.scenario.id)


def load_geodataset_options(request):
    scenario = Scenario.objects.get(id=request.GET.get('scenario'))
    if request.GET.get('feedstock'):
        feedstock = Material.objects.get(id=request.GET.get('feedstock'))
        if request.GET.get('options') == 'create':
            geodatasets = scenario.remaining_geodataset_options(feedstock=feedstock)
        elif request.GET.get('options') == 'update':
            current = GeoDataset.objects.filter(id=request.GET.get('current_geodataset'))
            geodatasets = scenario.remaining_geodataset_options(feedstock=feedstock).union(current)
        else:
            geodatasets = scenario.available_geodatasets()
    else:
        geodatasets = GeoDataset.objects.none()
    return render(request, 'geodataset_dropdown_list_options.html', {'geodatasets': geodatasets})


def load_algorithm_options(request):
    scenario = Scenario.objects.get(id=request.GET.get('scenario'))
    if request.GET.get('feedstock') and request.GET.get('geodataset'):
        feedstock = Material.objects.get(id=request.GET.get('feedstock'))
        geodataset = GeoDataset.objects.get(id=request.GET.get('geodataset'))
        if request.GET.get('options') == 'create':
            algorithms = scenario.remaining_inventory_algorithm_options(feedstock, geodataset)
        elif request.GET.get('options') == 'update':
            current_algorithm = InventoryAlgorithm.objects.filter(id=request.GET.get('current_inventory_algorithm'),
                                                                  feedstock=feedstock, geodataset=geodataset)
            algorithms = scenario.remaining_inventory_algorithm_options(feedstock, geodataset).union(current_algorithm)
        else:
            algorithms = scenario.available_inventory_algorithms()
    else:
        algorithms = InventoryAlgorithm.objects.none()
    return render(request, 'algorithm_dropdown_list_options.html', {'algorithms': algorithms})


def load_parameter_options(request):
    if request.GET.get('inventory_algorithm'):
        algorithm = InventoryAlgorithm.objects.get(id=request.GET.get('inventory_algorithm'))
        parameters = InventoryAlgorithmParameter.objects.filter(inventory_algorithm=algorithm)
        context = {
            'parameters': {
                parameter: InventoryAlgorithmParameterValue.objects.filter(parameter=parameter) for parameter in
                parameters}}
        return render(request, 'parameters_dropdown_list_options.html', context)
    else:
        return HttpResponse("")


class ResultMapAPI(APIView):
    """Rest API to get features from automatically generated result tables. Endpoint for Leaflet maps"""

    @staticmethod
    def get(request, *args, **kwargs):
        layer = Layer.objects.get(table_name=kwargs['layer_name'])
        feature_collection = layer.get_feature_collection()
        features = feature_collection.objects.all()
        serializer_class = BaseResultMapSerializer
        serializer_class.Meta.model = feature_collection

        serializer = serializer_class(features, many=True)
        data = {
            'geoJson': serializer.data,
        }

        return JsonResponse(data, safe=False)
