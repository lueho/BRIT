from urllib.parse import urlencode

from bootstrap_modal_forms.generic import BSModalCreateView, BSModalDeleteView, BSModalReadView, BSModalUpdateView
from bootstrap_modal_forms.mixins import is_ajax
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.template.loader import render_to_string
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView
from django_tables2 import table_factory

from users.models import get_default_owner
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


class FilterDefaultsMixin:
    """
    A mixin that extends FilterView to add the query string of the default filter values to the URL of the resulting page.
    This is useful when you want to have default filters applied when the page is first loaded.
    """
    initial_values = {}
    filterset_class = None

    def get_default_filters(self):
        initial_values = {}
        for name, filter_ in self.filterset_class.base_filters.items():
            if filter_.extra.get('initial'):
                initial_values[name] = filter_.extra['initial']
        return initial_values

    def get(self, request, *args, **kwargs):
        """
        Overrides the get method of the FilterView.
        If the request method is GET and the request's parameters are empty,
        it redirects to the same page but with the default filters as parameters.

        Args:
            request: The request that triggered this view.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: The HttpResponse object.
        """
        response = super().get(request, *args, **kwargs)

        if request.method == 'GET' and not request.GET:
            self.initial_values = self.get_default_filters()
            if self.initial_values:
                params = urlencode(self.initial_values)
                return HttpResponseRedirect(f"{request.path}?{params}")

        return response


class BRITFilterView(FilterDefaultsMixin, FilterView):
    paginate_by = 10
    ordering = 'id'


class PublishedObjectFilterView(FilterDefaultsMixin, FilterView):
    """
    A view to display a list of published objects with default filters applied.
    """
    paginate_by = 10
    ordering = 'id'

    def get_queryset(self):
        return super().get_queryset().filter(publication_status='published')


class UserOwnedObjectFilterView(LoginRequiredMixin, FilterDefaultsMixin, FilterView):
    """
    A view to display a list of objects owned by the currently logged-in user with default filters applied.
    """
    template_name_suffix = '_filter_owned'
    paginate_by = 10
    ordering = 'id'

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)


class OwnedObjectListView(PermissionRequiredMixin, ListView):
    paginate_by = 10

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
    success_message = 'Object created successfully.'
    object = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'Create New {self.form_class._meta.model._meta.verbose_name}',
            'submit_button_text': 'Save'
        })
        return context

    def get_success_message(self):
        return str(self.object.pk)

    def form_valid(self, form):
        isAjaxRequest = is_ajax(self.request.META)
        asyncUpdate = self.request.POST.get('asyncUpdate') == 'True'

        if isAjaxRequest:
            if asyncUpdate:
                self.object = form.save()
            return HttpResponse(status=204)

        self.object = form.save()
        messages.success(self.request, self.get_success_message())
        return HttpResponseRedirect(self.get_success_url())


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
    success_message = 'Object updated successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'Update {self.object._meta.verbose_name}',
            'submit_button_text': 'Save'
        })
        return context

    def get_success_message(self):
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


class UtilsDashboardView(PermissionRequiredMixin, TemplateView):
    template_name = 'utils_dashboard.html'
    permission_required = ('properties.view_property',)
