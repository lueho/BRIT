from urllib.parse import urlencode

from bootstrap_modal_forms.generic import BSModalCreateView, BSModalDeleteView, BSModalReadView, BSModalUpdateView
from bootstrap_modal_forms.mixins import is_ajax
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import post_save
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView
from extra_views import CreateWithInlinesView, UpdateWithInlinesView
from factory.django import mute_signals

from .forms import DynamicTableInlineFormSetHelper
from .models import Redirect


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
        # If the user is not authenticated, fail the test
        if not self.request.user.is_authenticated:
            return False

        # Allow access only if the user owns the object
        return self.get_object().owner == self.request.user


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


class UserCreatedObjectListMixin:
    paginate_by = 10
    list_type = None
    dashboard_url = None

    def get_queryset(self):
        queryset = super().get_queryset()

        if not hasattr(queryset.model, 'publication_status'):
            raise ImproperlyConfigured(
                f"The model {queryset.model.__name__} must have a 'publication_status' field."
            )

        query_params = {}
        if self.list_type == 'public':
            query_params['publication_status'] = 'published'
        elif self.list_type == 'private':
            query_params['owner'] = self.request.user

        queryset = queryset.filter(**query_params)

        if hasattr(queryset.model, 'name'):
            return queryset.order_by('name')

        return queryset.order_by('id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'header': self.model._meta.verbose_name_plural.capitalize(),
            'create_url': self.model.create_url,
            'create_url_text': f'New {self.model._meta.verbose_name}',
            'create_permission': f'{self.model.__module__.split(".")[-2]}.add_{self.model.__name__.lower()}',
            'list_type': self.list_type,
        })
        if self.list_type == 'private':
            context.update({'private_list_owner': self.request.user, })
        if self.dashboard_url:
            context.update({'dashboard_url': self.dashboard_url})
        return context


class PublishedObjectListMixin(UserCreatedObjectListMixin):
    list_type = 'public'


class PrivateObjectListMixin(LoginRequiredMixin, UserCreatedObjectListMixin):
    list_type = 'private'


class PublishedObjectFilterView(PublishedObjectListMixin, FilterDefaultsMixin, FilterView):
    """
    A view to display a list of published objects with default filters applied.
    """

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append('filtered_list.html')
        return template_names


class PrivateObjectFilterView(PrivateObjectListMixin, FilterDefaultsMixin, FilterView):
    """
    A view to display a list of objects owned by the currently logged-in user with default filters applied.
    """

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append('filtered_list.html')
        return template_names


class PublishedObjectListView(PublishedObjectListMixin, ListView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'header': self.model._meta.verbose_name_plural.capitalize(),
            'create_url': self.model.create_url,
            'create_url_text': f'New {self.model._meta.verbose_name}',
            'create_permission': f'{self.model.__module__.split(".")[-2]}.add_{self.model.__name__.lower()}'
        })
        return context

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append('simple_list_card.html')
        return template_names


class PrivateObjectListView(PrivateObjectListMixin, ListView):
    """
    A view to display a list of objects owned by the currently logged-in user.
    """

    def get_template_names(self):
        template_names = super().get_template_names()
        template_names.append('simple_list_card.html')
        return template_names


class UserCreatedObjectReadAccessMixin(UserPassesTestMixin):
    """
    A Mixin to control access to objects based on 'publication_status' and 'owner'.

    - Published objects ('publication_status' == 'published') are accessible to all users.
    - Unpublished objects are only accessible to their owners.
    """
    publication_status_field = 'publication_status'
    owner_field = 'owner'
    published_status = 'published'
    permission_denied_message = "You do not have permission to access this object."

    def test_func(self):

        obj = self.get_object()

        # Ensure the object has the required fields
        if not hasattr(obj, self.publication_status_field) or not hasattr(obj, self.owner_field):
            raise ImproperlyConfigured(
                f"The model {obj.__class__.__name__} must have '{self.publication_status_field}' and '{self.owner_field}' fields."
            )

        publication_status = getattr(obj, self.publication_status_field)
        owner = getattr(obj, self.owner_field)
        user = self.request.user

        if publication_status == self.published_status:
            # Published: accessible to all
            return True
        else:
            if user.is_authenticated:
                # Private: accessible only to the owner and staff
                return owner == user or user.is_staff
            else:
                # Private: not accessible for unauthenticated users
                return False


class UserCreatedObjectWriteAccessMixin(UserPassesTestMixin):
    """
    A Mixin to control write access to objects based on 'publication_status' and 'owner'.

    - Published objects ('publication_status' == 'published') are accessible to all users.
    - Unpublished objects are only accessible to their owners.
    """
    publication_status_field = 'publication_status'
    owner_field = 'owner'
    published_status = 'published'
    permission_denied_message = "You do not have permission to access this object."

    def test_func(self):

        user = self.request.user

        # Authentication is required for all write operations
        if not user.is_authenticated:
            return False

        obj = self.get_object()

        # Ensure the object has the required fields
        if not hasattr(obj, self.publication_status_field) or not hasattr(obj, self.owner_field):
            raise ImproperlyConfigured(
                f"The model {obj.__class__.__name__} must have '{self.publication_status_field}' and '{self.owner_field}' fields."
            )

        publication_status = getattr(obj, self.publication_status_field)
        owner = getattr(obj, self.owner_field)

        # staff can change any object
        if user.is_staff:
            return True

        # published objects can only be changed by staff
        if publication_status == self.published_status:
            return False

        # owners can change their own objects if they are not published
        if publication_status in ('private', 'review'):
            return owner == user


class CreateOwnedObjectMixin(PermissionRequiredMixin, NextOrSuccessUrlMixin):
    # TODO: EOL
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class CreateUserObjectMixin(LoginRequiredMixin, NextOrSuccessUrlMixin):
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


class UserCreatedObjectCreateView(CreateUserObjectMixin, SuccessMessageMixin, CreateView):

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
        with mute_signals(post_save):
            self.object = form.save()
        messages.success(self.request, self.get_success_message())
        return super().form_valid(form)


class UserCreatedObjectModalCreateView(CreateUserObjectMixin, BSModalCreateView):
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
        with mute_signals(post_save):
            self.object = form.save()
        messages.success(self.request, self.get_success_message())
        return HttpResponseRedirect(self.get_success_url())


class UserCreatedObjectDetailView(UserCreatedObjectReadAccessMixin, DetailView):
    """
    A view to display the details of a user created object only if it is either published or owned by the currently
    logged-in user. Views that inherit from this view must use models that inherit from UserCreatedObject.
    """

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append('simple_detail_card.html')
        return template_names


class OwnedObjectModalDetailView(PermissionRequiredMixin, BSModalReadView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'Details of {self.object._meta.verbose_name}',
        })
        return context


class UserCreatedObjectUpdateView(UserCreatedObjectWriteAccessMixin, NextOrSuccessUrlMixin, UpdateView):
    # TODO: Implement permission flow for publication process and moderators.

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Update {self.object._meta.verbose_name}',
            'submit_button_text': 'Save'
        })
        return context

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append('simple_form_card.html')
        return template_names


class OwnedObjectCreateWithInlinesView(CreateOwnedObjectMixin, CreateWithInlinesView):
    formset_helper_class = DynamicTableInlineFormSetHelper

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Create New {self.form_class._meta.model._meta.verbose_name}',
            'submit_button_text': 'Save',
            'formset_helper': self.formset_helper_class
        })
        return context

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append('form_with_inlines_card.html')
        return template_names


class UserCreatedObjectUpdateWithInlinesView(UserCreatedObjectWriteAccessMixin, NextOrSuccessUrlMixin,
                                             UpdateWithInlinesView):
    formset_helper_class = DynamicTableInlineFormSetHelper

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Update {self.object._meta.verbose_name}',
            'submit_button_text': 'Save',
            'formset_helper': self.formset_helper_class
        })
        return context

    def get_template_names(self):
        try:
            template_names = super().get_template_names()
        except ImproperlyConfigured:
            template_names = []
        template_names.append('form_with_inlines_card.html')
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


class UserCreatedObjectModalDeleteView(UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    template_name = 'modal_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Delete {self.object._meta.verbose_name}',
            'submit_button_text': 'Delete'
        })
        return context


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


class UtilsDashboardView(TemplateView):
    template_name = 'utils_dashboard.html'


class DynamicRedirectView(View):
    """
    A view that handles dynamic redirection based on a short code.
    If no such object exists, it returns a proper 404 response without logging an error.
    """

    def get(self, request, short_code):
        try:
            redirect_obj = Redirect.objects.get(short_code=short_code)
            return HttpResponseRedirect(f"{request.scheme}://{request.get_host()}{redirect_obj.full_path}")
        except Redirect.DoesNotExist:
            return render(request, '404.html', status=404)
