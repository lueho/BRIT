from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.views.generic import TemplateView
from django_tables2 import table_factory

from .tables import StandardItemTable, UserItemTable


class NextOrSuccessUrlMixin:
    """
    If a 'next=<url>' paramter is given the query string of the url, the user will be redirected to the given url
    instead of the url resulting from the get_success_url() method.
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


class DualUserListView(TemplateView):
    model = None

    def get_context_data(self, **kwargs):
        kwargs['item_name_plural'] = self.model._meta.verbose_name_plural
        standard_owner = User.objects.get(username='flexibi')
        kwargs['standard_item_table'] = table_factory(
            self.model,
            table=StandardItemTable
        )(self.model.objects.filter(owner=standard_owner))
        if not self.request.user.is_anonymous:
            kwargs['custom_item_table'] = table_factory(
                self.model,
                table=UserItemTable
            )(self.model.objects.filter(owner=self.request.user))
        return super().get_context_data(**kwargs)
