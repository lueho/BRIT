from bootstrap_modal_forms.generic import BSModalCreateView, BSModalUpdateView, BSModalDeleteView, BSModalReadView
from django.contrib.auth.mixins import UserPassesTestMixin, PermissionRequiredMixin
from django.views.generic import CreateView, UpdateView
from django.views.generic import TemplateView, ListView, DetailView
from django_tables2 import table_factory

from users.models import ReferenceUsers
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


class HomeView(TemplateView):
    template_name = 'home.html'


class ContributorsView(TemplateView):
    template_name = 'contributors.html'


class DualUserListView(TemplateView):
    model = None

    def get_context_data(self, **kwargs):
        kwargs['item_name_plural'] = self.model._meta.verbose_name_plural
        kwargs['standard_item_table'] = table_factory(
            self.model,
            table=StandardItemTable
        )(self.model.objects.filter(owner=ReferenceUsers.objects.get.standard_owner))
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


class OwnedObjectListView(PermissionRequiredMixin, ListView):
    create_new_object_url = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'header': self.model._meta.verbose_name_plural,
            'create_url': self.create_new_object_url,
            'create_url_text': f'New {self.model._meta.verbose_name}'
        })
        return context


class CreateOwnedObjectMixin(PermissionRequiredMixin, NextOrSuccessUrlMixin):
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class OwnedObjectCreateView(CreateOwnedObjectMixin, CreateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Create New {self.form_class._meta.model._meta.verbose_name}',
        })
        return context


class OwnedObjectModalCreateView(CreateOwnedObjectMixin, BSModalCreateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'Create New {self.form_class._meta.model._meta.verbose_name}',
            'submit_button_text': 'Save'
        })
        return context


class OwnedObjectDetailView(PermissionRequiredMixin, DetailView):
    pass


class OwnedObjectModalDetailView(PermissionRequiredMixin, BSModalReadView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'{self.object._meta.verbose_name} Details',
        })
        return context


class OwnedObjectUpdateView(PermissionRequiredMixin, NextOrSuccessUrlMixin, UpdateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'{self.object._meta.verbose_name} Update',
            'submit_button_text': 'Save'
        })
        return context


class OwnedObjectModalUpdateView(PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalUpdateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'{self.object._meta.verbose_name} Update',
            'submit_button_text': 'Save'
        })
        return context


class OwnedObjectDeleteView(PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalDeleteView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Delete {self.object._meta.verbose_name}',
            'submit_button_text': 'Delete'
        })
        return context


class RestrictedAccessListView(PermissionRequiredMixin, ListView):

    def get_queryset(self):
        user = self.request.user
        return self.model.objects.readable(user)
