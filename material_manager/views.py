from crispy_forms.layout import Submit
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, View, UpdateView
from extra_views import ModelFormSetView

from flexibi_dst.views import DualUserListView
from .forms import (
    AddComponentForm,
    MaterialAddComponentGroupForm,
    MaterialModelForm,
    MaterialComponentModelForm,
    MaterialComponentGroupModelForm,
    MaterialComponentGroupAddTemporalDistributionForm,
    MaterialComponentGroupSettings,
    MaterialComponentDistributionFormSetHelper,
    MaterialComponentShareUpdateForm,
)
from .models import (
    Material,
    MaterialSettings,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialComponentShare,
)


# ----------- Materials/Feedstocks -------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# ----------- Materials CRUD -------------------------------------------------------------------------------------------

class MaterialListView(DualUserListView):
    model = Material
    template_name = 'material_list.html'


class MaterialCreateView(LoginRequiredMixin, CreateView):
    form_class = MaterialModelForm
    template_name = 'material_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class MaterialDetailView(UserPassesTestMixin, DetailView):
    model = Material
    template_name = 'material_detail.html'

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Material
    form_class = MaterialModelForm
    template_name = 'material_update.html'

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Material
    template_name = 'material_delete.html'
    success_url = reverse_lazy('material_list')

    def test_func(self):
        return self.request.user == self.get_object().owner


# ----------- Material Components CRUD ---------------------------------------------------------------------------------


class MaterialComponentListView(DualUserListView):
    model = MaterialComponent
    template_name = 'material_component_list.html'


class MaterialComponentCreateView(LoginRequiredMixin, CreateView):
    form_class = MaterialComponentModelForm
    template_name = 'material_component_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class MaterialComponentDetailView(UserPassesTestMixin, DetailView):
    model = MaterialComponent
    template_name = 'material_component_detail.html'

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialComponentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = MaterialComponent
    form_class = MaterialComponentModelForm
    template_name = 'material_component_update.html'

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialComponentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = MaterialComponent
    template_name = 'material_component_delete.html'
    success_url = reverse_lazy('material_component_list')

    def test_func(self):
        return self.request.user == self.get_object().owner


# ----------- Material Component Groups CRUD----------------------------------------------------------------------------


class MaterialComponentGroupListView(DualUserListView):
    model = MaterialComponentGroup
    template_name = 'material_component_group_list.html'


class MaterialComponentGroupCreateView(LoginRequiredMixin, CreateView):
    form_class = MaterialComponentGroupModelForm
    template_name = 'material_component_group_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class MaterialComponentGroupDetailView(UserPassesTestMixin, DetailView):
    model = MaterialComponentGroup
    template_name = 'material_component_group_detail.html'

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialComponentGroupUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = MaterialComponentGroup
    form_class = MaterialComponentGroupModelForm
    template_name = 'material_component_group_update.html'

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialComponentGroupDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = MaterialComponentGroup
    template_name = 'material_component_group_delete.html'
    success_url = reverse_lazy('material_component_group_list')

    def test_func(self):
        return self.request.user == self.get_object().owner


# ----------- Materials/Components/Groups Organisation -----------------------------------------------------------------


class MaterialSettingsListView(DualUserListView):
    model = MaterialSettings
    template_name = 'material_setting_list.html'


# TODO: This view can be used to create customized materials for user's scenarios. But where and how should it be used?
class MaterialSettingsCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = MaterialSettings
    template_name = 'material_settings_create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def test_func(self):
        # TODO: test if user is owner of scenario
        return True


class MaterialSettingsDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = MaterialSettings
    template_name = 'material_configuration.html'

    def get_context_data(self, **kwargs):
        kwargs['composition'] = self.object.composition()
        return super().get_context_data(**kwargs)

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialSettingsDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = MaterialSettings
    template_name = 'material_settings_delete.html'
    success_url = reverse_lazy('material_setting_list')

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialAddComponentGroupView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = MaterialSettings
    form_class = MaterialAddComponentGroupForm
    template_name = 'material_add_component_group.html'

    def get_form(self, **kwargs):
        form = super().get_form(**kwargs)
        form.fields['group'].queryset = MaterialComponentGroup.objects.exclude(id__in=self.get_object().blocked_ids)
        form.fields['fractions_of'].queryset = MaterialComponent.objects.filter(id__in=self.get_object().component_ids)
        return form

    def form_valid(self, form):
        self.get_object().add_component_group(form.cleaned_data['group'],
                                              fractions_of=form.cleaned_data['fractions_of'])
        return HttpResponseRedirect(self.get_object().get_absolute_url())

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialRemoveComponentGroupView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = MaterialComponentGroupSettings
    template_name = 'material_component_group_remove.html'

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialComponentGroupAddComponentView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = MaterialComponentGroupSettings
    form_class = AddComponentForm
    template_name = 'material_component_group_add_component.html'

    def get_form(self, **kwargs):
        form = super().get_form(**kwargs)
        form.fields['component'].queryset = MaterialComponent.objects.exclude(id__in=self.get_object().blocked_ids)
        return form

    def form_valid(self, form):
        self.object.add_component(form.cleaned_data['component'])
        return HttpResponseRedirect(self.get_success_url())

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialComponentGroupRemoveComponentView(LoginRequiredMixin, UserPassesTestMixin, View):
    component = None
    group_settings = None

    def get(self, request, *args, **kwargs):
        self.get_objects()
        self.group_settings.remove_component(self.component)
        return HttpResponseRedirect(self.get_success_url())

    def get_objects(self):
        self.component = MaterialComponent.objects.get(id=self.kwargs.get('component_pk'))
        self.group_settings = MaterialComponentGroupSettings.objects.get(id=self.kwargs.get('pk'))

    def get_success_url(self):
        self.get_objects()
        return self.group_settings.get_absolute_url()

    def test_func(self):
        self.get_objects()
        return self.request.user == self.group_settings.owner


class MaterialComponentShareUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = MaterialComponentShare
    form_class = MaterialComponentShareUpdateForm
    template_name = 'material_component_group_share_update.html'

    def test_func(self):
        return self.request.user == self.get_object().group_settings.owner


class MaterialComponentGroupAddTemporalDistributionView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = MaterialComponentGroupSettings
    form_class = MaterialComponentGroupAddTemporalDistributionForm
    template_name = 'material_component_group_add_temporal_distribution.html'

    def test_func(self):
        return self.request.user == self.get_object().owner


class MaterialComponentGroupShareDistributionUpdateView(ModelFormSetView):
    model = MaterialComponentShare
    fields = ['component', 'average', 'standard_deviation']
    template_name = 'model_formset_test_view.html'
    factory_kwargs = {'extra': 0}

    def get_context_data(self, **kwargs):
        helper = MaterialComponentDistributionFormSetHelper()
        helper.add_input(Submit('submit', 'Save'))
        context = {
            'helper': helper
        }
        context.update(kwargs)
        return super().get_context_data(**context)

    def get_queryset(self, *args, **kwargs):
        group_settings = MaterialComponentGroupSettings.objects.get(id=self.kwargs.get('pk'))
        queryset = MaterialComponentShare.objects.filter(
            group_settings=group_settings,
            timestep=self.kwargs.get('timestep_pk')
        )
        return queryset

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        else:
            group_settings = MaterialComponentGroupSettings.objects.get(id=self.kwargs.get('pk'))
            material_settings = group_settings.material_settings
            return reverse('material_settings', kwargs={'pk': material_settings.id})
