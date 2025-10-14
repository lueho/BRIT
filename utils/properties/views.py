from django.urls import reverse_lazy
from django.views.generic import TemplateView

from utils.object_management.views import (
    OwnedObjectModelSelectOptionsView,
    PrivateObjectListView,
    PublishedObjectListView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectUpdateView,
)

from .forms import PropertyModelForm, PropertyUnitModelForm
from .models import Property, PropertyUnit


class PropertiesDashboardView(TemplateView):
    template_name = "properties_dashboard.html"


# ----------- PropertyUnit CRUD ----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
class PropertyUnitPublishedListView(PublishedObjectListView):
    model = PropertyUnit
    dashboard_url = reverse_lazy("properties-dashboard")


class PropertyUnitPrivateListView(PrivateObjectListView):
    model = PropertyUnit
    dashboard_url = reverse_lazy("properties-dashboard")


class PropertyUnitCreateView(UserCreatedObjectCreateView):
    model = PropertyUnit
    form_class = PropertyUnitModelForm
    permission_required = ("properties.add_propertyunit",)


class PropertyUnitDetailView(UserCreatedObjectDetailView):
    model = PropertyUnit


class PropertyUnitUpdateView(UserCreatedObjectUpdateView):
    model = PropertyUnit
    form_class = PropertyUnitModelForm


class PropertyUnitModalDeleteView(UserCreatedObjectModalDeleteView):
    model = PropertyUnit


# ----------- Property CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PropertyPublishedListView(PublishedObjectListView):
    model = Property
    dashboard_url = reverse_lazy("properties-dashboard")


class PropertyPrivateListView(PrivateObjectListView):
    model = Property
    dashboard_url = reverse_lazy("properties-dashboard")


class PropertyCreateView(UserCreatedObjectCreateView):
    model = Property
    form_class = PropertyModelForm
    permission_required = ("properties.add_property",)


class PropertyDetailView(UserCreatedObjectDetailView):
    model = Property


class PropertyUpdateView(UserCreatedObjectUpdateView):
    model = Property
    form_class = PropertyModelForm


class PropertyModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Property


class PropertyUnitOptionsView(OwnedObjectModelSelectOptionsView):
    model = Property
    include_empty_option = False
    permission_required = set()

    def get_selected_object(self):
        return self.object_list.first()

    def get_queryset(self):
        obj = self.model.objects.get(id=self.kwargs.get("pk"))
        return obj.allowed_units.all()
