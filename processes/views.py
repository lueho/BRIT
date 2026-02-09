from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView

from utils.object_management.views import (
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
)

from .filters import (
    MechanismCategoryListFilter,
    ProcessGroupListFilter,
    ProcessTypeListFilter,
)
from .forms import (
    MechanismCategoryModalModelForm,
    MechanismCategoryModelForm,
    ProcessGroupModalModelForm,
    ProcessGroupModelForm,
    ProcessTypeModalModelForm,
    ProcessTypeModelForm,
)
from .models import MechanismCategory, ProcessGroup, ProcessType

# ----------- Dashboard ------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ProcessesExplorerView(TemplateView):
    template_name = "processes/processes_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["processtype_count"] = ProcessType.objects.filter(
            publication_status="published"
        ).count()
        context["processgroup_count"] = ProcessGroup.objects.filter(
            publication_status="published"
        ).count()
        context["mechanismcategory_count"] = MechanismCategory.objects.filter(
            publication_status="published"
        ).count()
        context["pulping_group"] = ProcessGroup.objects.filter(
            name="Pulping", publication_status="published"
        ).first()
        return context


# ----------- Process Group CRUD ---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ProcessGroupPublishedListView(PublishedObjectFilterView):
    model = ProcessGroup
    filterset_class = ProcessGroupListFilter
    dashboard_url = reverse_lazy("processes-explorer")


class ProcessGroupPrivateListView(PrivateObjectFilterView):
    model = ProcessGroup
    filterset_class = ProcessGroupListFilter
    dashboard_url = reverse_lazy("processes-explorer")


class ProcessGroupCreateView(UserCreatedObjectCreateView):
    form_class = ProcessGroupModelForm
    permission_required = "processes.add_processgroup"


class ProcessGroupModalCreateView(UserCreatedObjectModalCreateView):
    form_class = ProcessGroupModalModelForm
    permission_required = "processes.add_processgroup"


class ProcessGroupDetailView(UserCreatedObjectDetailView):
    model = ProcessGroup

    # Flowsheets keyed by group name (conditional section in template)
    GROUP_FLOWSHEETS = {
        "Pulping": [
            {"label": "Pulping of Straw", "url_name": "pulping-straw-infocard"},
        ],
    }

    # Short descriptions keyed by group name (lead subtitle)
    GROUP_SHORT_DESCRIPTIONS = {
        "Pulping": "Disintegration of biomass into individual fibres suitable for paper and packaging.",
    }

    # Aggregated parameter summaries keyed by group name
    GROUP_PARAMS = {
        "Pulping": {
            "mechanism": "Physico-chemical or chemical reactions",
            "temperature": "130 – 190 °C",
            "yield": "40 – 90 %",
        },
    }

    # Static fallback images for process types (keyed by lowercase substring match)
    STATIC_IMAGES = {
        "steam": "img/steam_reactor.jpg",
        "horizontal tube": "img/horizontal_tube_reactor.jpg",
        "liquor circulation": "img/liquor_circulation_reactor.jpg",
    }

    def _resolve_static_image(self, name):
        name_lower = name.lower()
        for keyword, path in self.STATIC_IMAGES.items():
            if keyword in name_lower:
                return path
        return ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        process_types = list(
            self.object.process_types.filter(publication_status="published")
        )
        for pt in process_types:
            if not pt.image:
                pt.static_image = self._resolve_static_image(pt.name)
        context["process_types"] = process_types

        context["short_description"] = self.GROUP_SHORT_DESCRIPTIONS.get(
            self.object.name, ""
        )
        context["aggregate_params"] = self.GROUP_PARAMS.get(self.object.name)

        flowsheets_config = self.GROUP_FLOWSHEETS.get(self.object.name, [])
        context["flowsheets"] = [
            {"label": fs["label"], "url": reverse(fs["url_name"])}
            for fs in flowsheets_config
        ]
        return context


class ProcessGroupModalDetailView(UserCreatedObjectModalDetailView):
    model = ProcessGroup


class ProcessGroupUpdateView(UserCreatedObjectUpdateView):
    model = ProcessGroup
    form_class = ProcessGroupModelForm


class ProcessGroupModalUpdateView(UserCreatedObjectModalUpdateView):
    model = ProcessGroup
    form_class = ProcessGroupModalModelForm


class ProcessGroupModalDeleteView(UserCreatedObjectModalDeleteView):
    model = ProcessGroup


class ProcessGroupAutocompleteView(UserCreatedObjectAutocompleteView):
    model = ProcessGroup


# ----------- Mechanism Category CRUD ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MechanismCategoryPublishedListView(PublishedObjectFilterView):
    model = MechanismCategory
    filterset_class = MechanismCategoryListFilter
    dashboard_url = reverse_lazy("processes-explorer")


class MechanismCategoryPrivateListView(PrivateObjectFilterView):
    model = MechanismCategory
    filterset_class = MechanismCategoryListFilter
    dashboard_url = reverse_lazy("processes-explorer")


class MechanismCategoryCreateView(UserCreatedObjectCreateView):
    form_class = MechanismCategoryModelForm
    permission_required = "processes.add_mechanismcategory"


class MechanismCategoryModalCreateView(UserCreatedObjectModalCreateView):
    form_class = MechanismCategoryModalModelForm
    permission_required = "processes.add_mechanismcategory"


class MechanismCategoryDetailView(UserCreatedObjectDetailView):
    model = MechanismCategory


class MechanismCategoryModalDetailView(UserCreatedObjectModalDetailView):
    model = MechanismCategory


class MechanismCategoryUpdateView(UserCreatedObjectUpdateView):
    model = MechanismCategory
    form_class = MechanismCategoryModelForm


class MechanismCategoryModalUpdateView(UserCreatedObjectModalUpdateView):
    model = MechanismCategory
    form_class = MechanismCategoryModalModelForm


class MechanismCategoryModalDeleteView(UserCreatedObjectModalDeleteView):
    model = MechanismCategory


class MechanismCategoryAutocompleteView(UserCreatedObjectAutocompleteView):
    model = MechanismCategory


# ----------- Process Type CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ProcessTypePublishedListView(PublishedObjectFilterView):
    model = ProcessType
    filterset_class = ProcessTypeListFilter
    dashboard_url = reverse_lazy("processes-explorer")


class ProcessTypePrivateListView(PrivateObjectFilterView):
    model = ProcessType
    filterset_class = ProcessTypeListFilter
    dashboard_url = reverse_lazy("processes-explorer")


class ProcessTypeCreateView(UserCreatedObjectCreateView):
    form_class = ProcessTypeModelForm
    permission_required = "processes.add_processtype"


class ProcessTypeModalCreateView(UserCreatedObjectModalCreateView):
    form_class = ProcessTypeModalModelForm
    permission_required = "processes.add_processtype"


class ProcessTypeDetailView(UserCreatedObjectDetailView):
    model = ProcessType


class ProcessTypeModalDetailView(UserCreatedObjectModalDetailView):
    model = ProcessType


class ProcessTypeUpdateView(UserCreatedObjectUpdateView):
    model = ProcessType
    form_class = ProcessTypeModelForm


class ProcessTypeModalUpdateView(UserCreatedObjectModalUpdateView):
    model = ProcessType
    form_class = ProcessTypeModalModelForm


class ProcessTypeModalDeleteView(UserCreatedObjectModalDeleteView):
    model = ProcessType


class ProcessTypeAutocompleteView(UserCreatedObjectAutocompleteView):
    model = ProcessType


# ----------- Pulping overview & flowsheets ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PulpingOverviewRedirectView(TemplateView):
    """Redirects the legacy pulping overview URL to the Pulping group detail page."""

    def get(self, request, *args, **kwargs):
        from django.shortcuts import redirect

        pulping = ProcessGroup.objects.filter(name="Pulping").first()
        if pulping:
            return redirect(pulping.get_absolute_url())
        return redirect("processes-explorer")


class StrawAndWoodProcessInfoView(TemplateView):
    template_name = "processes/pulping_straw_infocard.html"
