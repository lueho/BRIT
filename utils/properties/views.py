from django.urls import reverse_lazy

from .forms import PropertyModelForm, PropertyUnitModelForm
from .models import Property, PropertyUnit
from ..views import (OwnedObjectCreateView, OwnedObjectListView, OwnedObjectModalDeleteView,
                     OwnedObjectModelSelectOptionsView, OwnedObjectUpdateView, UserCreatedObjectDetailView)


class PropertyUnitListView(OwnedObjectListView):
    model = PropertyUnit
    permission_required = set()


class PropertyUnitCreateView(OwnedObjectCreateView):
    model = PropertyUnit
    form_class = PropertyUnitModelForm
    permission_required = ('properties.add_propertyunit',)


class PropertyUnitDetailView(UserCreatedObjectDetailView):
    model = PropertyUnit


class PropertyUnitUpdateView(OwnedObjectUpdateView):
    model = PropertyUnit
    form_class = PropertyUnitModelForm
    permission_required = ('properties.change_propertyunit',)


class PropertyUnitModalDeleteView(OwnedObjectModalDeleteView):
    model = PropertyUnit
    permission_required = ('properties.delete_propertyunit',)
    success_message = 'Property unit deleted successfully.'
    success_url = reverse_lazy('propertyunit-list')


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
