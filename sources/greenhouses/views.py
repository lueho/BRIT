from crispy_forms.helper import FormHelper
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from extra_views import CreateWithInlinesView

from maps.views import CatchmentAutocompleteView, GeoDataSetPublishedFilteredMapView
from materials.models import Composition, MaterialComponentGroup
from sources.greenhouses.filters import (
    CultureListFilter,
    GreenhouseTypeFilter,
    NantesGreenhousesFilterSet,
)
from sources.greenhouses.forms import (
    CultureModalModelForm,
    CultureModelForm,
    GreenhouseGrowthCycleModelForm,
    GreenhouseModalModelForm,
    GreenhouseModelForm,
    GrowthCycleCreateForm,
    GrowthShareFormSetHelper,
    GrowthTimestepInline,
    InlineGrowthShare,
    UpdateGreenhouseGrowthCycleValuesForm,
)
from sources.greenhouses.models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthTimeStepSet,
)
from utils.file_export.views import GenericUserCreatedObjectExportView
from utils.modal import is_ajax
from utils.object_management.permissions import filter_queryset_for_user
from utils.object_management.views import (
    CreateUserObjectMixin,
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
    UserCreatedObjectUpdateWithInlinesView,
)


class CulturePublishedListView(PublishedObjectFilterView):
    model = Culture
    filterset_class = CultureListFilter


class CulturePrivateListView(PrivateObjectFilterView):
    model = Culture
    filterset_class = CultureListFilter


class CultureAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Culture


class CultureCreateView(UserCreatedObjectCreateView):
    model = Culture
    fields = ("name", "residue", "description")
    permission_required = "greenhouses.add_culture"


class CultureModalCreateView(UserCreatedObjectModalCreateView):
    form_class = CultureModalModelForm
    permission_required = "greenhouses.add_culture"


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


class GreenhousePublishedFilterView(PublishedObjectFilterView):
    model = Greenhouse
    filterset_class = GreenhouseTypeFilter


class GreenhousePrivateFilterView(PrivateObjectFilterView):
    model = Greenhouse
    filterset_class = GreenhouseTypeFilter


class GreenhouseCreateView(UserCreatedObjectCreateView):
    form_class = GreenhouseModelForm
    permission_required = "greenhouses.add_greenhouse"


class GreenhouseModalCreateView(UserCreatedObjectModalCreateView):
    form_class = GreenhouseModalModelForm
    permission_required = "greenhouses.add_greenhouse"


class GreenhouseDetailView(UserCreatedObjectDetailView):
    model = Greenhouse

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


class GreenhouseGrowthCycleCreateView(CreateUserObjectMixin, CreateWithInlinesView):
    """Inline growth-cycle create bound to the posted greenhouse.

    The cycle is an owned child of its ``greenhouse``: the bound create
    adapter resolves the parent from the validated form, locks it under
    ``content_mutation``, and re-decides the owned-child create inside the
    write boundary. The advisory gate requires at least one editable
    greenhouse.
    """

    model = GreenhouseGrowthCycle
    inlines = [
        GrowthTimestepInline,
    ]
    fields = (
        "culture",
        "greenhouse",
        "group_settings",
    )
    template_name = "greenhouses/growth_cycle_inline_create.html"

    def forms_valid(self, form, inlines):
        # extra_views persists inline formsets after ``form_valid`` returns —
        # outside the bound create. Stash them so the timestep rows save
        # inside the same mutation boundary on the greenhouse root.
        self._inlines = inlines
        return self.form_valid(form)

    def _call_super_form_valid(self, form):
        response = super()._call_super_form_valid(form)
        for formset in self._inlines:
            formset.instance = self.object
            formset.save()
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class GrowthCycleModalCreateView(UserCreatedObjectModalCreateView):
    form_class = GrowthCycleCreateForm
    permission_required = "greenhouses.add_greenhousegrowthcycle"
    greenhouse = None

    def dispatch(self, request, *args, **kwargs):
        self.greenhouse = get_object_or_404(Greenhouse, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_policy_parent(self):
        # Advisory and authoritative create gates both decide against the
        # greenhouse resolved from the URL.
        return self.greenhouse

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["greenhouse"] = self.greenhouse
        return kwargs

    def form_valid(self, form):
        form.instance.greenhouse = self.greenhouse
        residue = form.instance.culture.residue
        if residue is None:
            form.add_error("culture", "The selected culture has no residue.")
            return self.form_invalid(form)

        compositions = filter_queryset_for_user(
            Composition.objects.filter(sample__series=residue), self.request.user
        ).order_by("order", "pk")
        if self.greenhouse.is_published:
            compositions = compositions.filter(
                publication_status=Composition.STATUS_PUBLISHED
            )
        group_settings = compositions.filter(group__name="Macro Components").first()
        if group_settings is None:
            group_settings = compositions.filter(
                group=MaterialComponentGroup.objects.default()
            ).first()
        if group_settings is None:
            form.add_error(
                "culture",
                "The selected culture's residue has no Macro Components or default composition.",
            )
            return self.form_invalid(form)

        if is_ajax(self.request):
            return HttpResponse(status=204)

        form.instance.group_settings = group_settings
        # ``timesteps`` carries the shared seed distributions (private,
        # default-owner rows). Like the season formset rows of the frequency
        # boundary they are child writes of this create, not governed
        # cross-references — they leave the form's validated reference
        # surface here and are written inside the boundary instead.
        self._timesteps = form.cleaned_data.pop("timesteps")
        return super().form_valid(form)

    def _call_super_form_valid(self, form):
        # The bound create adapter persists the cycle inside a
        # ``content_mutation`` on the parent greenhouse: the timestep rows
        # and the cycle ordering write inside the same atomic boundary so
        # the parent's snapshot captures the whole compound change.
        response = super()._call_super_form_valid(form)
        for timestep in self._timesteps:
            self.object.add_timestep(timestep)
        self.object.greenhouse.sort_growth_cycles()
        return response


class GrowthCycleDetailView(UserCreatedObjectDetailView):
    model = GreenhouseGrowthCycle

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


class GrowthTimeStepSetModalUpdateView(UserCreatedObjectUpdateWithInlinesView):
    model = GrowthTimeStepSet
    inlines = [
        InlineGrowthShare,
    ]
    fields = []
    template_name = "modal_form_with_formset.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        inline_helper = GrowthShareFormSetHelper()
        inline_helper.form_tag = False
        form_helper = FormHelper()
        form_helper.form_tag = False
        context.update(
            {
                "form_title": "Change the composition",
                "submit_button_text": "Save",
                "inline_helper": inline_helper,
                "form_helper": form_helper,
            }
        )
        return context


class UpdateGreenhouseGrowthCycleValuesView(UserCreatedObjectUpdateView):
    model = GreenhouseGrowthCycle
    form_class = UpdateGreenhouseGrowthCycleValuesForm
    template_name = "greenhouses/greenhouse_growth_cycle_update_values.html"
    object = None

    def get_object(self, **kwargs):
        return GreenhouseGrowthCycle.objects.get(id=self.kwargs.get("cycle_pk"))

    def get_success_url(self):
        return reverse("greenhouse-detail", kwargs={"pk": self.kwargs.get("pk")})


class NantesGreenhousesCatchmentAutocompleteView(CatchmentAutocompleteView):
    geodataset_model_name = "NantesGreenhouses"


class GreenhousesPublishedMapView(GeoDataSetPublishedFilteredMapView):
    model_name = "NantesGreenhouses"
    template_name = "greenhouses/nantes_greenhouses_map.html"
    filterset_class = NantesGreenhousesFilterSet
    features_layer_api_basename = "api-nantes-greenhouses"
    map_title = "Nantes Greenhouses"


class NantesGreenhousesListFileExportView(GenericUserCreatedObjectExportView):
    model_label = "greenhouses.NantesGreenhouses"


__all__ = [
    "CultureAutocompleteView",
    "CultureCreateView",
    "CultureDetailView",
    "CultureModalCreateView",
    "CultureModalDeleteView",
    "CultureModalUpdateView",
    "CulturePrivateListView",
    "CulturePublishedListView",
    "CultureUpdateView",
    "GreenhouseCreateView",
    "GreenhouseDetailView",
    "GreenhouseGrowthCycleCreateView",
    "GreenhouseModalCreateView",
    "GreenhouseModalDeleteView",
    "GreenhouseModalUpdateView",
    "GreenhousePrivateFilterView",
    "GreenhousePublishedFilterView",
    "GreenhousesPublishedMapView",
    "GreenhouseUpdateView",
    "GrowthCycleDetailView",
    "GrowthCycleModalCreateView",
    "GrowthCycleModalDeleteView",
    "GrowthCycleUpdateView",
    "GrowthTimeStepSetModalUpdateView",
    "NantesGreenhousesCatchmentAutocompleteView",
    "NantesGreenhousesListFileExportView",
    "UpdateGreenhouseGrowthCycleValuesView",
]
