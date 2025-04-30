from django.urls import reverse_lazy
from django.views.generic import TemplateView

from .forms import PropertyModelForm, UnitModelForm
from .models import Property, Unit
from ..views import (OwnedObjectModelSelectOptionsView, PrivateObjectListView, PublishedObjectListView,
                     UserCreatedObjectCreateView, UserCreatedObjectDetailView, UserCreatedObjectModalDeleteView,
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


class UnitCreateView(UserCreatedObjectCreateView):
    model = Unit
    form_class = UnitModelForm
    permission_required = ('properties.add_unit',)


class UnitDetailView(UserCreatedObjectDetailView):
    model = Unit


class UnitUpdateView(UserCreatedObjectUpdateView):
    model = Unit
    form_class = UnitModelForm


class UnitModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Unit


# ----------- Property CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PropertyPublishedListView(PublishedObjectListView):
    model = Property
    dashboard_url = reverse_lazy('properties-dashboard')


class PropertyPrivateListView(PrivateObjectListView):
    model = Property
    dashboard_url = reverse_lazy('properties-dashboard')


class PropertyCreateView(UserCreatedObjectCreateView):
    model = Property
    form_class = PropertyModelForm
    permission_required = ('properties.add_property',)


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
        obj = self.model.objects.get(id=self.kwargs.get('pk'))
        return obj.allowed_units.all()
