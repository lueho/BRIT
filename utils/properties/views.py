from django.urls import reverse_lazy
from django.views.generic import TemplateView

from .forms import PropertyModelForm, UnitModelForm
from .models import Property, Unit
from ..views import (OwnedObjectCreateView, OwnedObjectModalDeleteView, OwnedObjectModelSelectOptionsView,
                     PrivateObjectListView, PublishedObjectListView, UserCreatedObjectDetailView,
                     UserCreatedObjectUpdateView)


class PropertiesDashboardView(TemplateView):
    template_name = 'properties_dashboard.html'


# ----------- Unit CRUD ------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
class UnitPublishedListView(PublishedObjectListView):
    model = Unit
    dashboard_url = reverse_lazy('properties-dashboard')


class UnitPrivateListView(PrivateObjectListView):
    model = Unit
    dashboard_url = reverse_lazy('properties-dashboard')


class UnitCreateView(OwnedObjectCreateView):
    model = Unit
    form_class = UnitModelForm
    permission_required = ('properties.add_unit',)


class UnitDetailView(UserCreatedObjectDetailView):
    model = Unit


class UnitUpdateView(UserCreatedObjectUpdateView):
    model = Unit
    form_class = UnitModelForm


class UnitModalDeleteView(OwnedObjectModalDeleteView):
    model = Unit
    permission_required = ('properties.delete_unit',)
    success_message = 'Unit deleted successfully.'
    success_url = reverse_lazy('unit-list')


# ----------- Property CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PropertyPublishedListView(PublishedObjectListView):
    model = Property
    dashboard_url = reverse_lazy('properties-dashboard')


class PropertyPrivateListView(PrivateObjectListView):
    model = Property
    dashboard_url = reverse_lazy('properties-dashboard')


class PropertyCreateView(OwnedObjectCreateView):
    model = Property
    form_class = PropertyModelForm
    permission_required = ('properties.add_property',)


class PropertyDetailView(UserCreatedObjectDetailView):
    model = Property


class PropertyUpdateView(UserCreatedObjectUpdateView):
    model = Property
    form_class = PropertyModelForm


class PropertyModalDeleteView(OwnedObjectModalDeleteView):
    model = Property
    permission_required = ('properties.delete_property',)
    success_message = 'Property deleted successfully.'
    success_url = reverse_lazy('property-list')


class PropertyUnitOptionsView(OwnedObjectModelSelectOptionsView):
    model = Property
    include_empty_option = False
    permission_required = set()

    def get_selected_object(self):
        return self.object_list.first()

    def get_queryset(self):
        obj = self.model.objects.get(id=self.kwargs.get('pk'))
        return obj.allowed_units.all()
