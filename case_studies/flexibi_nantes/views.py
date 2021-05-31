from bootstrap_modal_forms.generic import BSModalCreateView, BSModalReadView, BSModalUpdateView, \
    BSModalDeleteView
from crispy_forms.helper import FormHelper
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, UpdateView
from django.views.generic import TemplateView
from django_tables2 import table_factory
from extra_views import CreateWithInlinesView, UpdateWithInlinesView
from rest_framework.views import APIView

from flexibi_dst.views import DualUserListView, UserOwnsObjectMixin, NextOrSuccessUrlMixin
from material_manager.models import MaterialComponentGroup, BaseObjects
from users.models import ReferenceUsers
from .forms import (CultureModelForm,
                    GreenhouseModalModelForm,
                    GreenhouseGrowthCycle,
                    UpdateGreenhouseGrowthCycleValuesForm,
                    NantesGreenhousesFilterForm,
                    GrowthCycleCreateForm,
                    GrowthTimestepInline,
                    GrowthShareFormSetHelper,
                    InlineGrowthShare, )
from .models import Culture, Greenhouse, NantesGreenhouses, GrowthTimeStepSet
from .serializers import NantesGreenhousesGeometrySerializer
from .tables import growthcycle_table_factory, StandardGreenhouseTable, UserGreenhouseTable


# ----------- Culture CRUD ---------------------------------------------------------------------------------------------

class CultureListView(DualUserListView):
    model = Culture
    template_name = 'dual_user_item_list.html'


class CultureCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, BSModalCreateView):
    form_class = CultureModelForm
    template_name = '../../flexibi_dst/templates/modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create new culture',
            'submit_button_text': 'Create'
        })
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class CultureDetailView(UserOwnsObjectMixin, BSModalReadView):
    model = Culture
    template_name = 'modal_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': 'Culture details',
        })
        return context


class CultureUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = Culture
    form_class = CultureModelForm
    template_name = '../../flexibi_dst/templates/modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Edit culture',
            'submit_button_text': 'Edit'
        })
        return context


class CultureDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = Culture
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('culture_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Delete culture',
            'submit_button_text': 'Delete'
        })
        return context


# ----------- Greenhouse CRUD ------------------------------------------------------------------------------------------

class DualUserListView(TemplateView):
    model = None

    def get_context_data(self, **kwargs):
        kwargs['item_name_plural'] = self.model._meta.verbose_name_plural
        kwargs['standard_item_table'] = table_factory(
            self.model,
            table=StandardGreenhouseTable
        )(self.model.objects.filter(owner=ReferenceUsers.objects.get.standard_owner))
        if not self.request.user.is_anonymous:
            kwargs['custom_item_table'] = table_factory(
                self.model,
                table=UserGreenhouseTable
            )(self.model.objects.filter(owner=self.request.user))
        return super().get_context_data(**kwargs)


class GreenhouseListView(DualUserListView):
    model = Greenhouse
    template_name = 'dual_user_item_list.html'


class GreenhouseCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, BSModalCreateView):
    form_class = GreenhouseModalModelForm
    template_name = '../../flexibi_dst/templates/modal_form.html'
    success_url = reverse_lazy('greenhouse_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create new greenhouse type',
            'submit_button_text': 'Create'
        })
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class GreenhouseDetailView(UserOwnsObjectMixin, DetailView):
    model = Greenhouse
    template_name = 'greenhouse_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'growth_cycles': self.object.configuration()})
        return context


class GreenhouseUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = Greenhouse
    form_class = GreenhouseModalModelForm
    template_name = '../../flexibi_dst/templates/modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Edit greenhouse',
            'submit_button_text': 'Edit'
        })
        return context


class GreenhouseDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = Greenhouse
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('greenhouse_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Delete greenhouse',
            'submit_button_text': 'Delete'
        })
        return context


# ----------- Growthcycle CRUD -----------------------------------------------------------------------------------------


class GreenhouseGrowthCycleCreateView(LoginRequiredMixin, CreateWithInlinesView):
    model = GreenhouseGrowthCycle
    inlines = [GrowthTimestepInline, ]
    fields = ('culture', 'greenhouse', 'group_settings',)
    template_name = 'growth_cycle_inline_create.html'

    def get_success_url(self):
        return self.object.get_absolute_url()


class GrowthCycleCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, BSModalCreateView):
    model = GreenhouseGrowthCycle
    form_class = GrowthCycleCreateForm
    template_name = '../../flexibi_dst/templates/modal_form.html'
    object = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Add growth cycle',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        if not self.request.is_ajax():
            form.instance.owner = self.request.user
            form.instance.greenhouse = Greenhouse.objects.get(id=self.kwargs.get('pk'))
            material_settings = form.instance.culture.residue
            macro_components = MaterialComponentGroup.objects.get(name='Macro Components')
            base_group = BaseObjects.objects.get.base_group
            try:
                group_settings = material_settings.materialcomponentgroupsettings_set.get(group=macro_components)
            except ObjectDoesNotExist:
                group_settings = material_settings.materialcomponentgroupsettings_set.get(group=base_group)
            form.instance.group_settings = group_settings
            self.object = form.save()
            for timestep in form.cleaned_data['timesteps']:
                self.object.add_timestep(timestep)
            self.object.greenhouse.sort_growth_cycles()
        return HttpResponseRedirect(self.get_success_url())


class GrowthCycleDetailView(DetailView):
    model = GreenhouseGrowthCycle
    template_name = 'growth_cycle_detail.html'

    def get_context_data(self, **kwargs):
        kwargs['table'] = growthcycle_table_factory(self.object)
        return super().get_context_data(**kwargs)


class GrowthCycleDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = GreenhouseGrowthCycle
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('greenhouse_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Remove growth cycle',
            'submit_button_text': 'Remove'
        })
        return context


class GrowthTimeStepSetModalUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin,
                                       UpdateWithInlinesView):
    model = GrowthTimeStepSet
    inlines = [InlineGrowthShare, ]
    fields = []
    template_name = 'modal_item_formset.html'

    def get_context_data(self, **kwargs):
        inline_helper = GrowthShareFormSetHelper()
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


class UpdateGreenhouseGrowthCycleValuesView(LoginRequiredMixin, UpdateView):
    model = GreenhouseGrowthCycle
    form_class = UpdateGreenhouseGrowthCycleValuesForm
    template_name = 'greenhouse_growth_cycle_update_values.html'
    object = None

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_object(self, **kwargs):
        return GreenhouseGrowthCycle.objects.get(id=self.kwargs.get('cycle_pk'))

    def get_success_url(self):
        return reverse('greenhouse_detail', kwargs={'pk': self.kwargs.get('pk')})

    def get_initial(self):
        return {
            'material': self.object.material,
            'component': self.object.component
        }


class NantesGreenhousesView(FormView):
    template_name = 'explore_nantes_greenhouses.html'
    form_class = NantesGreenhousesFilterForm
    initial = {'heated': 'Yes', 'lighted': 'Yes'}


class NantesGreenhousesAPIView(APIView):

    @staticmethod
    def get(request):
        qs = NantesGreenhouses.objects.all()

        if request.GET.get('lighting') == '2':
            qs = qs.filter(lighted=True)
        elif request.GET.get('lighting') == '3':
            qs = qs.filter(lighted=False)

        if request.GET.get('heating') == '2':
            qs = qs.filter(heated=True)
        elif request.GET.get('heating') == '3':
            qs = qs.filter(heated=False)

        if request.GET.get('prod_mode') == '2':
            qs = qs.filter(above_ground=False)
        elif request.GET.get('prod_mode') == '3':
            qs = qs.filter(above_ground=True)

        if request.GET.get('cult_man') == '2':
            qs = qs.filter(high_wire=False)
        elif request.GET.get('cult_man') == '3':
            qs = qs.filter(heated=True)

        crops = []
        if request.GET.get('cucumber') == 'true':
            crops.append('Cucumber')
        if request.GET.get('tomato') == 'true':
            crops.append('Tomato')

        qs = qs.filter(culture_1__in=crops)

        serializer = NantesGreenhousesGeometrySerializer(qs, many=True)
        data = {
            'geoJson': serializer.data,
            'analysis': {
                'gh_count': len(serializer.data['features']),
                'gh_surface': round(qs.aggregate(Sum('surface_ha'))['surface_ha__sum'], 1)
            }
        }

        return JsonResponse(data, safe=False)
