from crispy_forms.helper import FormHelper
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import UpdateView
from extra_views import CreateWithInlinesView, UpdateWithInlinesView

from maps.models import Catchment, GeoDataset
from maps.views import GeoDataSetPublishedFilteredMapView
from materials.models import MaterialComponentGroup
from utils.file_export.views import GenericUserCreatedObjectExportView
from utils.object_management.views import (
    PrivateObjectFilterView,
    PrivateObjectListView,
    PublishedObjectFilterView,
    PublishedObjectListView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
    UserOwnsObjectMixin,
)
from utils.views import NextOrSuccessUrlMixin

from .filters import GreenhouseTypeFilter, NantesGreenhousesFilterSet
from .forms import (
    CultureModalModelForm,
    CultureModelForm,
    GreenhouseGrowthCycle,
    GreenhouseGrowthCycleModelForm,
    GreenhouseModalModelForm,
    GreenhouseModelForm,
    GrowthCycleCreateForm,
    GrowthShareFormSetHelper,
    GrowthTimestepInline,
    InlineGrowthShare,
    UpdateGreenhouseGrowthCycleValuesForm,
)
from .models import Culture, Greenhouse, GrowthTimeStepSet

# ----------- Culture CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CulturePublishedListView(PublishedObjectListView):
    model = Culture


class CulturePrivateListView(PrivateObjectListView):
    model = Culture


class CultureCreateView(UserCreatedObjectCreateView):
    model = Culture
    fields = ("name", "residue", "description")
    permission_required = "flexibi_nantes.add_culture"


class CultureModalCreateView(UserCreatedObjectModalCreateView):
    form_class = CultureModalModelForm
    permission_required = "flexibi_nantes.add_culture"


class CultureDetailView(UserCreatedObjectDetailView):
    model = Culture


class CultureUpdateView(UserCreatedObjectUpdateView):
    model = Culture
    form_class = CultureModelForm


class CultureModalUpdateView(UserCreatedObjectModalUpdateView):
    model = Culture
    form_class = CultureModalModelForm


class CultureModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Culture


# ----------- Greenhouse CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class GreenhousePublishedFilterView(PublishedObjectFilterView):
    model = Greenhouse
    filterset_class = GreenhouseTypeFilter


class GreenhousePrivateFilterView(PrivateObjectFilterView):
    model = Greenhouse
    filterset_class = GreenhouseTypeFilter


class GreenhouseCreateView(UserCreatedObjectCreateView):
    form_class = GreenhouseModelForm
    permission_required = "flexibi_nantes.add_greenhouse"


class GreenhouseModalCreateView(UserCreatedObjectModalCreateView):
    form_class = GreenhouseModalModelForm
    permission_required = "flexibi_nantes.add_greenhouse"


class GreenhouseDetailView(UserCreatedObjectDetailView):
    model = Greenhouse
    template_name = "greenhouse_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"growth_cycles": self.object.configuration()})
        return context


class GreenhouseUpdateView(UserCreatedObjectUpdateView):
    model = Greenhouse
    form_class = GreenhouseModelForm


class GreenhouseModalUpdateView(UserCreatedObjectModalUpdateView):
    model = Greenhouse
    form_class = GreenhouseModalModelForm


class GreenhouseModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Greenhouse


# ----------- Growthcycle CRUD -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class GreenhouseGrowthCycleCreateView(LoginRequiredMixin, CreateWithInlinesView):
    model = GreenhouseGrowthCycle
    inlines = [
        GrowthTimestepInline,
    ]
    fields = (
        "culture",
        "greenhouse",
        "group_settings",
    )
    template_name = "growth_cycle_inline_create.html"

    def get_success_url(self):
        return self.object.get_absolute_url()


class GrowthCycleModalCreateView(UserCreatedObjectModalCreateView):
    form_class = GrowthCycleCreateForm
    permission_required = "flexibi_nantes.add_greenhousegrowthcycle"

    def form_valid(self, form):
        if not self.request.is_ajax():
            form.instance.greenhouse = Greenhouse.objects.get(id=self.kwargs.get("pk"))
            material_settings = form.instance.culture.residue
            macro_components = MaterialComponentGroup.objects.get(
                name="Macro Components"
            )
            # base_group = BaseObjects.objects.get.base_group
            base_group = MaterialComponentGroup.objects.default()
            try:
                group_settings = (
                    material_settings.materialcomponentgroupsettings_set.get(
                        group=macro_components
                    )
                )
            except ObjectDoesNotExist:
                group_settings = (
                    material_settings.materialcomponentgroupsettings_set.get(
                        group=base_group
                    )
                )
            form.instance.group_settings = group_settings
            self.object = form.save()
            for timestep in form.cleaned_data["timesteps"]:
                self.object.add_timestep(timestep)
            self.object.greenhouse.sort_growth_cycles()
        return HttpResponseRedirect(self.get_success_url())


class GrowthCycleDetailView(UserCreatedObjectDetailView):
    model = GreenhouseGrowthCycle
    template_name = "growthcycle_detail.html"

    def get_context_data(self, **kwargs):
        kwargs["table_data"] = self.object.table_data
        kwargs["growth_cycle"] = self.object
        return super().get_context_data(**kwargs)


class GrowthCycleUpdateView(UserCreatedObjectUpdateView):
    model = GreenhouseGrowthCycle
    form_class = GreenhouseGrowthCycleModelForm


class GrowthCycleModalDeleteView(UserCreatedObjectModalDeleteView):
    model = GreenhouseGrowthCycle

    def get_success_url(self):
        return reverse("greenhouse-detail", kwargs={"pk": self.object.greenhouse.pk})


class GrowthTimeStepSetModalUpdateView(
    LoginRequiredMixin,
    UserOwnsObjectMixin,
    NextOrSuccessUrlMixin,
    UpdateWithInlinesView,
):
    model = GrowthTimeStepSet
    inlines = [
        InlineGrowthShare,
    ]
    fields = []
    template_name = "modal_form_with_formset.html"

    def get_context_data(self, **kwargs):
        inline_helper = GrowthShareFormSetHelper()
        inline_helper.form_tag = False
        form_helper = FormHelper()
        form_helper.form_tag = False
        context = {
            "form_title": "Change the composition",
            "submit_button_text": "Save",
            "inline_helper": inline_helper,
            "form_helper": form_helper,
        }
        context.update(kwargs)
        return super().get_context_data(**context)


class UpdateGreenhouseGrowthCycleValuesView(LoginRequiredMixin, UpdateView):
    # TODO: Is this still required?
    model = GreenhouseGrowthCycle
    form_class = UpdateGreenhouseGrowthCycleValuesForm
    template_name = "greenhouse_growth_cycle_update_values.html"
    object = None

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_object(self, **kwargs):
        return GreenhouseGrowthCycle.objects.get(id=self.kwargs.get("cycle_pk"))

    def get_success_url(self):
        return reverse("greenhouse-detail", kwargs={"pk": self.kwargs.get("pk")})

    def get_initial(self):
        return {"material": self.object.material, "component": self.object.component}


# ----------- Nantes Greenhouses GeoDataSet ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class NantesGreenhousesCatchmentAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Catchment
    geodataset_model_name = "NantesGreenhouses"

    def get_queryset(self):
        queryset = super().get_queryset()
        dataset_region = GeoDataset.objects.get(
            model_name=self.geodataset_model_name
        ).region
        return queryset.filter(region__borders__geom__within=dataset_region.geom)


class GreenhousesPublishedMapView(GeoDataSetPublishedFilteredMapView):
    model_name = "NantesGreenhouses"
    template_name = "nantes_greenhouses_map.html"
    filterset_class = NantesGreenhousesFilterSet
    features_layer_api_basename = "api-nantes-greenhouses"
    map_title = "Nantes Greenhouses"


class NantesGreenhousesListFileExportView(GenericUserCreatedObjectExportView):
    model_label = "flexibi_nantes.NantesGreenhouses"
