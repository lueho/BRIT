from bootstrap_modal_forms.generic import BSModalCreateView, BSModalDeleteView, BSModalReadView, BSModalUpdateView
from django.contrib.auth.mixins import PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView
from django_tables2 import table_factory

from users.models import get_default_owner
from .models import Property
from .tables import StandardItemTable, UserItemTable


class NextOrSuccessUrlMixin:
    """
    If a 'next=<url>' parameter is given in the query string of the url,
    the user will be redirected to the given url instead of the url resulting
    from the get_success_url() method.
    """

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        return next_url if next_url else super().get_success_url()


class UserOwnsObjectMixin(UserPassesTestMixin):
    """
    All models that have access restrictions specific to a user contain a field named 'owner'. This mixin prevents
    access to objects owned by other users.
    """

    def test_func(self):
        return self.get_object().owner == self.request.user


class DualUserListView(TemplateView):
    model = None

    def get_context_data(self, **kwargs):
        kwargs['item_name_plural'] = self.model._meta.verbose_name_plural
        kwargs['standard_item_table'] = table_factory(
            self.model,
            table=StandardItemTable
        )(self.model.objects.filter(owner=get_default_owner()))
        if not self.request.user.is_anonymous:
            kwargs['custom_item_table'] = table_factory(
                self.model,
                table=UserItemTable
            )(self.model.objects.filter(owner=self.request.user))
        return super().get_context_data(**kwargs)


class ModalMessageView(TemplateView):
    template_name = 'modal_message.html'
    title = 'Title'
    message = 'Message'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': self.title,
            'message': self.message
        })
        return context


class BRITFilterView(FilterView):
    paginate_by = 10


class OwnedObjectListView(PermissionRequiredMixin, ListView):
    paginate_by = 15

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'header': self.model._meta.verbose_name_plural.capitalize(),
            'create_url': self.model.create_url,
            'create_url_text': f'New {self.model._meta.verbose_name}',
            'create_permission': f'{self.model.__module__.split(".")[-2]}.add_{self.model.__name__.lower()}'
        })
        return context

    def get_queryset(self):
        try:
            return super().get_queryset().order_by('name')
        except FieldError:
            return super().get_queryset()

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append('simple_list_card.html')
        return template_names


class CreateOwnedObjectMixin(PermissionRequiredMixin, NextOrSuccessUrlMixin):
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class OwnedObjectCreateView(CreateOwnedObjectMixin, SuccessMessageMixin, CreateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Create New {self.form_class._meta.model._meta.verbose_name}',
        })
        return context

    def get_success_message(self, cleaned_data):
        return str(self.object.pk)

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append('simple_form_card.html')
        return template_names


class OwnedObjectModalCreateView(CreateOwnedObjectMixin, BSModalCreateView):
    template_name = 'modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'Create New {self.form_class._meta.model._meta.verbose_name}',
            'submit_button_text': 'Save'
        })
        return context

    def get_success_message(self, cleaned_data):
        return str(self.object.pk)


class OwnedObjectDetailView(PermissionRequiredMixin, DetailView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'model_name': self.object._meta.verbose_name.capitalize(),
        })
        return context


class OwnedObjectModalDetailView(PermissionRequiredMixin, BSModalReadView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'Details of {self.object._meta.verbose_name}',
        })
        return context


class OwnedObjectUpdateView(PermissionRequiredMixin, SuccessMessageMixin, NextOrSuccessUrlMixin, UpdateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Update {self.object._meta.verbose_name}',
            'submit_button_text': 'Save'
        })
        return context

    def get_success_message(self, cleaned_data):
        return str(self.object.pk)

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append('simple_form_card.html')
        return template_names


class OwnedObjectModalUpdateView(PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    template_name = 'modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'Update {self.object._meta.verbose_name}',
            'submit_button_text': 'Save'
        })
        return context

    def get_success_message(self, cleaned_data):
        return str(self.object.pk)


class OwnedObjectModalDeleteView(PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    template_name = 'modal_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Delete {self.object._meta.verbose_name}',
            'submit_button_text': 'Delete'
        })
        return context


class ModelSelectOptionsView(ListView):
    """
    Returns a pre-rendered list of options for a select DOM element as json response. This is useful for updating
    options when new objects have been created via ajax.
    """

    model = None
    template_name = 'html_select_element_options.html'
    object_list = None
    include_empty_option = True
    selected_object = None

    def get_selected_object(self):
        """
        Returns the element, which will be selected in the new options list. By default this will be the
        newest created element. Override this if you require a different behaviour.
        """
        return self.selected_object

    def get_selected_object_pk(self):
        """
        Returns the primary key of the selected object, if there is any.
        """
        selected_object = self.get_selected_object()
        if selected_object:
            return selected_object.pk
        return None

    def get_queryset(self):
        """
        Returns a queryset of all the options that will be rendered in the template. By default returns all objects.
        Override this if you want to limit the choices.
        """
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'include_empty_option': self.include_empty_option,
            'selected': self.get_selected_object_pk()
        })
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        return JsonResponse({
            'options': render_to_string(
                self.template_name,
                context=self.get_context_data(),
                request=self.request
            )
        })


class OwnedObjectModelSelectOptionsView(PermissionRequiredMixin, ModelSelectOptionsView):
    pass


class PropertyUnitOptionsView(OwnedObjectModelSelectOptionsView):
    model = Property
    include_empty_option = False
    permission_required = set()

    def get_selected_object(self):
        return self.object_list.first()

    def get_queryset(self):
        obj = self.model.objects.get(id=self.kwargs.get('pk'))
        return obj.allowed_units.all()
