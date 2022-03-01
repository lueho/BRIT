from bootstrap_modal_forms.generic import BSModalFormView, BSModalCreateView, BSModalReadView, BSModalUpdateView, \
    BSModalDeleteView
from crispy_forms.helper import FormHelper
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, View, ListView
from extra_views import UpdateWithInlinesView

from brit.views import DualUserListView, UserOwnsObjectMixin, NextOrSuccessUrlMixin
from brit.views import (
    OwnedObjectListView,
    OwnedObjectCreateView,
    OwnedObjectModalCreateView,
    OwnedObjectDetailView,
    OwnedObjectModalDetailView,
    OwnedObjectUpdateView,
    OwnedObjectModalUpdateView,
    OwnedObjectDeleteView,
)
from distributions.models import TemporalDistribution
from users.models import get_default_owner
from . import forms
from .forms import (
    AddComponentForm,
    AddComponentGroupForm,
    AddLiteratureSourceForm,
    AddSeasonalVariationForm,
    MaterialModelForm,
    ComponentModelForm,
    ComponentGroupModelForm,
    MaterialComponentGroupSettings,
    ComponentShareDistributionFormSetHelper,
    InlineComponentShare
)
from .models import (
    Material,
    MaterialSettings,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialGroup,
    CompositionSet
)


# ----------- Material Group CRUD --------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class MaterialGroupListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = MaterialGroup
    permission_required = 'materials.view_materialgroup'
    create_new_object_url = reverse_lazy('material_group_create')


class MaterialGroupCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.MaterialGroupModelForm
    success_url = reverse_lazy('material_group_list')
    permission_required = 'materials.add_materialgroup'


class MaterialGroupModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.MaterialGroupModalModelForm
    success_url = reverse_lazy('material_group_list')
    permission_required = 'materials.add_materialgroup'


class MaterialGroupDetailView(OwnedObjectDetailView):
    template_name = 'material_group_detail.html'
    model = MaterialGroup
    permission_required = 'materials.view_materialgroup'


class MaterialGroupModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = MaterialGroup
    permission_required = 'materials.view_materialgroup'


class MaterialGroupUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = MaterialGroup
    form_class = forms.MaterialGroupModelForm
    permission_required = 'materials.change_materialgroup'


class MaterialGroupModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = MaterialGroup
    form_class = forms.MaterialGroupModalModelForm
    permission_required = 'materials.change_materialgroup'


class MaterialGroupModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = MaterialGroup
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('material_group_list')
    permission_required = 'materials.delete_materialgroup'


# ----------- Material CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialListView(OwnedObjectListView):
    template_name = 'simple_list_card.html'
    model = Material
    permission_required = 'materials.view_material'
    create_new_object_url = reverse_lazy('material-create')


class MaterialCreateView(OwnedObjectCreateView):
    template_name = 'simple_form_card.html'
    form_class = forms.MaterialModelForm
    success_url = reverse_lazy('material-list')
    permission_required = 'materials.add_material'


class MaterialModalCreateView(OwnedObjectModalCreateView):
    template_name = 'modal_form.html'
    form_class = MaterialModelForm
    success_url = reverse_lazy('material-list')
    permission_required = 'materials.add_material'


class MaterialDetailView(OwnedObjectDetailView):
    template_name = 'material_detail.html'
    model = Material
    permission_required = 'materials.view_material'


class MaterialModalDetailView(OwnedObjectModalDetailView):
    template_name = 'modal_detail.html'
    model = Material
    permission_required = 'materials.view_material'


class MaterialUpdateView(OwnedObjectUpdateView):
    template_name = 'simple_form_card.html'
    model = Material
    form_class = forms.MaterialModelForm
    permission_required = 'materials.change_material'


class MaterialModalUpdateView(OwnedObjectModalUpdateView):
    template_name = 'modal_form.html'
    model = Material
    form_class = forms.MaterialModalModelForm
    permission_required = 'materials.change_material'


class MaterialModalDeleteView(OwnedObjectDeleteView):
    template_name = 'modal_delete.html'
    model = Material
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('material-list')
    permission_required = 'materials.delete_material'


# ----------- Material Components CRUD ---------------------------------------------------------------------------------


class MaterialComponentListView(DualUserListView):
    model = MaterialComponent
    template_name = 'dual_user_item_list.html'


class MaterialComponentCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, BSModalCreateView):
    form_class = ComponentModelForm
    template_name = 'modal_form.html'
    success_url = reverse_lazy('component_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create new material component',
            'submit_button_text': 'Create'
        })
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class MaterialComponentDetailView(UserOwnsObjectMixin, DetailView):
    model = MaterialComponent
    template_name = 'item_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': 'Component details',
        })
        return context


class MaterialComponentUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = MaterialComponent
    form_class = ComponentModelForm
    template_name = 'modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Edit material component',
            'submit_button_text': 'Edit'
        })
        return context


class MaterialComponentDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = MaterialComponent
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('component_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Delete component',
            'submit_button_text': 'Delete'
        })
        return context


# ----------- Material Component Groups CRUD----------------------------------------------------------------------------


class ComponentGroupListView(DualUserListView):
    model = MaterialComponentGroup
    template_name = 'dual_user_item_list.html'


class ComponentGroupCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, BSModalCreateView):
    form_class = ComponentGroupModelForm
    template_name = 'modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create new component group',
            'submit_button_text': 'Create'
        })
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class ComponentGroupDetailView(UserOwnsObjectMixin, DetailView):
    model = MaterialComponentGroup
    template_name = 'modal_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': 'Component group details',
        })
        return context


class ComponentGroupUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = MaterialComponentGroup
    form_class = ComponentGroupModelForm
    template_name = 'modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Edit component group description',
            'submit_button_text': 'Edit'
        })
        return context


class ComponentGroupDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = MaterialComponentGroup
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('material_component_group_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Delete component group',
            'submit_button_text': 'Delete'
        })
        return context


# ----------- Materials/Components/Groups Relation -----------------------------------------------------------------


# TODO: This view can be used to create customized materials for user's scenarios. But where and how should it be used?
class MaterialSettingsCreateView(LoginRequiredMixin, UserPassesTestMixin, NextOrSuccessUrlMixin, CreateView):
    model = MaterialSettings
    template_name = 'material_settings_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def test_func(self):
        # TODO: test if user is owner of scenario
        return False


# TODO: beautify 'show seasonal variation' button
# TODO: possibility to upload image of a material


class MaterialSettingsDetailView(UserPassesTestMixin, DetailView):
    model = MaterialSettings
    template_name = 'material_settings_detail.html'
    allow_edit = False
    object = None

    def get_context_data(self, **kwargs):
        kwargs['composition'] = self.object.composition()
        charts = {}
        for group_settings, content in kwargs['composition'].items():
            charts[f'composition-chart-{group_settings.id}'] = content['averages_chart'].as_dict()
        kwargs['charts'] = charts
        kwargs['allow_edit'] = self.allow_edit
        return super().get_context_data(**kwargs)

    def test_func(self):
        self.object = self.get_object()
        standard_owner = get_default_owner()
        if self.object.owner == standard_owner:
            if self.request.user == standard_owner:
                self.allow_edit = True
            return True
        elif self.object.owner == self.request.user:
            self.allow_edit = True
            return True
        else:
            return False


class MaterialSettingsDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, DeleteView):
    model = MaterialSettings
    template_name = 'material_settings_delete.html'
    success_url = reverse_lazy('material_setting_list')


class AddComponentGroupView(LoginRequiredMixin, UserOwnsObjectMixin, BSModalFormView):
    form_class = AddComponentGroupForm
    template_name = 'modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Select a component group to add',
            'submit_button_text': 'Add'
        })
        return context

    def get_form(self, **kwargs):
        form = super().get_form(**kwargs)
        form.fields['group'].queryset = MaterialComponentGroup.objects.exclude(
            id__in=self.get_object().blocked_ids)
        form.fields['fractions_of'].queryset = MaterialComponent.objects.filter(
            id__in=self.get_object().component_ids)
        form.fields['fractions_of'].empty_label = None
        return form

    def get_object(self):
        return MaterialSettings.objects.get(id=self.kwargs.get('pk'))

    def form_valid(self, form):
        # Due to the way the django-bootstrap modal-forms package is built, the post request and this method are
        # executed twice.
        # See: https://github.com/trco/django-bootstrap-modal-forms/issues/14
        if not self.request.is_ajax():
            self.get_object().add_component_group(form.cleaned_data['group'],
                                                  fractions_of=form.cleaned_data['fractions_of'])
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class RemoveComponentGroupView(LoginRequiredMixin, UserOwnsObjectMixin, BSModalDeleteView):
    model = MaterialComponentGroupSettings
    template_name = 'modal_delete.html'
    success_message = 'Successfully removed'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Remove group',
            'submit_button_text': 'Remove'
        })
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class AddComponentView(LoginRequiredMixin, UserOwnsObjectMixin, BSModalFormView):
    form_class = AddComponentForm
    template_name = 'modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Select a component to add',
            'submit_button_text': 'Add'
        })
        return context

    def get_form(self, **kwargs):
        form = super().get_form(**kwargs)
        form.fields['component'].queryset = MaterialComponent.objects.exclude(
            id__in=self.get_object().blocked_component_ids)
        return form

    def get_object(self):
        return MaterialComponentGroupSettings.objects.get(id=self.kwargs.get('pk'))

    def form_valid(self, form):
        # Due to the way the django-bootstrap modal-forms package is built, the post request and this method are
        # executed twice.
        # See: https://github.com/trco/django-bootstrap-modal-forms/issues/14
        if not self.request.is_ajax():
            self.get_object().add_component(form.cleaned_data['component'])
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class RemoveComponentView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, View):

    def get(self, request, *args, **kwargs):
        self.get_object().remove_component(self.get_component())
        return HttpResponseRedirect(self.get_success_url())

    def get_object(self):
        return MaterialComponentGroupSettings.objects.get(id=self.kwargs.get('pk'))

    def get_component(self):
        return MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class AddSourceView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalFormView):
    form_class = AddLiteratureSourceForm
    template_name = 'modal_form.html'

    def get_object(self):
        return MaterialComponentGroupSettings.objects.get(id=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Select a source to add',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        if not self.request.is_ajax():
            self.get_object().sources.add(form.cleaned_data['source'])
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class AddSeasonalVariationView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalFormView):
    form_class = AddSeasonalVariationForm
    template_name = 'modal_form.html'

    def get_object(self):
        return MaterialComponentGroupSettings.objects.get(id=self.kwargs.get('pk'))

    def get_form(self, **kwargs):
        form = super().get_form(**kwargs)
        form.fields['temporal_distribution'].queryset = TemporalDistribution.objects.exclude(
            id__in=self.get_object().blocked_distribution_ids)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Select a distribution to add',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        if not self.request.is_ajax():
            self.get_object().add_temporal_distribution(form.cleaned_data['temporal_distribution'])
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class RemoveSeasonalVariationView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalReadView):
    template_name = 'modal_delete.html'
    model = MaterialComponentGroupSettings

    def get_distribution(self):
        return TemporalDistribution.objects.get(id=self.kwargs.get('distribution_pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Remove seasonal variation',
            'submit_button_text': 'Remove'
        })
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def post(self, request, *args, **kwargs):
        success_url = self.get_success_url()
        self.get_object().remove_temporal_distribution(self.get_distribution())
        return HttpResponseRedirect(success_url)


class RemoveSeasonalVariationViewILD(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = MaterialComponentGroupSettings
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'

    def delete(self, request, *args, **kwargs):
        success_url = self.get_success_url()
        self.get_object().remove_temporal_distribution(self.get_distribution())
        return HttpResponseRedirect(success_url)

    def get_distribution(self):
        return TemporalDistribution.objects.get(id=self.kwargs.get('distribution_pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Remove seasonal variation',
            'submit_button_text': 'Remove'
        })
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class CompositionSetUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, UpdateWithInlinesView):
    model = CompositionSet
    inlines = [InlineComponentShare, ]
    fields = ['group_settings', 'timestep']
    template_name = 'item_formset.html'

    def get_context_data(self, **kwargs):
        inline_helper = ComponentShareDistributionFormSetHelper()
        inline_helper.form_tag = False
        form_helper = FormHelper()
        form_helper.form_tag = False
        context = {
            'inline_helper': inline_helper,
            'form_helper': form_helper
        }
        context.update(kwargs)
        return super().get_context_data(**context)


class CompositionSetModalUpdateView(PermissionRequiredMixin,
                                    NextOrSuccessUrlMixin,
                                    UpdateWithInlinesView):
    model = CompositionSet
    inlines = [InlineComponentShare, ]
    fields = []
    template_name = 'modal_item_formset.html'
    permission_required = (
        'materials.change_compositionset',
        'materials.change_materialcomponentshare',
    )

    def get_context_data(self, **kwargs):
        inline_helper = ComponentShareDistributionFormSetHelper()
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


class FeaturedMaterialListView(ListView):
    template_name = 'featured_materials_list.html'
    model = MaterialSettings

    def get_queryset(self):
        user_groups = self.request.user.groups.all()
        return MaterialSettings.objects.filter(Q(visible_to_groups__in=user_groups) | Q(publish=True))
