from django.urls import reverse_lazy

from .forms import PropertyModelForm, UnitModelForm
from .models import Property, Unit
from ..views import (OwnedObjectCreateView, OwnedObjectListView, OwnedObjectModalDeleteView,
                     OwnedObjectModelSelectOptionsView, OwnedObjectUpdateView, UserCreatedObjectDetailView)


class UnitListView(OwnedObjectListView):
    model = Unit
    permission_required = set()


class UnitCreateView(OwnedObjectCreateView):
    model = Unit
    form_class = UnitModelForm
    permission_required = ('properties.add_unit',)


class UnitDetailView(UserCreatedObjectDetailView):
    model = Unit


class UnitUpdateView(OwnedObjectUpdateView):
    model = Unit
    form_class = UnitModelForm
    permission_required = ('properties.change_unit',)


class UnitModalDeleteView(OwnedObjectModalDeleteView):
    model = Unit
    permission_required = ('properties.delete_unit',)
    success_message = 'Unit deleted successfully.'
    success_url = reverse_lazy('unit-list')


class PropertyListView(OwnedObjectListView):
    model = Property
    permission_required = set()


class PropertyCreateView(OwnedObjectCreateView):
    model = Property
    form_class = PropertyModelForm
    permission_required = ('properties.add_property',)


class PropertyDetailView(UserCreatedObjectDetailView):
    model = Property


class PropertyUpdateView(OwnedObjectUpdateView):
    model = Property
    form_class = PropertyModelForm
    permission_required = ('properties.change_property',)


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
