from bootstrap_modal_forms.generic import BSModalCreateView, BSModalUpdateView, BSModalDeleteView, BSModalReadView
from django.contrib.auth.mixins import UserPassesTestMixin, PermissionRequiredMixin
from django.core.exceptions import FieldError
from django.views.generic import CreateView, UpdateView
from django.views.generic import TemplateView, ListView, DetailView
from django_tables2 import table_factory

from users.models import get_default_owner
from .tables import StandardItemTable, UserItemTable


class Chart:
    id = None
    type = None
    labels = None
    datasets = None
    options = None


class DoughnutView(TemplateView):
    template_name = 'doughnut.html'

    def get_context_data(self, **kwargs):

        chart1 = Chart()
        chart1.id = 'chart_1'

        context = super().get_context_data(**kwargs)
        context.update({
            'charts': {
                'chart_1': {
                    'type': 'doughnut',
                    'data': {
                        'labels': ['Red', 'Blue', 'Yellow', 'Green', 'Purple', 'Orange'],
                        'datasets': [{
                            'label': '# of Votes',
                            'data': [12, 19, 3, 5, 2, 3],
                            'backgroundColor': [
                                'rgba(255, 99, 132, 0.2)',
                                'rgba(54, 162, 235, 0.2)',
                                'rgba(255, 206, 86, 0.2)',
                                'rgba(75, 192, 192, 0.2)',
                                'rgba(153, 102, 255, 0.2)',
                                'rgba(255, 159, 64, 0.2)'
                            ],
                            'borderColor': [
                                'rgba(255, 99, 132, 1)',
                                'rgba(54, 162, 235, 1)',
                                'rgba(255, 206, 86, 1)',
                                'rgba(75, 192, 192, 1)',
                                'rgba(153, 102, 255, 1)',
                                'rgba(255, 159, 64, 1)'
                            ],
                            'borderWidth': 1,
                            'hoverOffset': 4
                        }]
                    },
                    'options': {
                        'scales': {
                            'y': {
                                'beginAtZero': 'true'
                            }
                        }
                    }
                },
                'chart_2': {
                    'type': 'doughnut',
                    'data': {
                        'labels': ['Red', 'Blue', 'Yellow', 'Green', 'Purple', 'Orange'],
                        'datasets': [{
                            'label': '# of Votes',
                            'data': [12, 19, 3, 5, 2, 3],
                            'backgroundColor': [
                                'rgba(255, 99, 132, 0.2)',
                                'rgba(54, 162, 235, 0.2)',
                                'rgba(255, 206, 86, 0.2)',
                                'rgba(75, 192, 192, 0.2)',
                                'rgba(153, 102, 255, 0.2)',
                                'rgba(255, 159, 64, 0.2)'
                            ],
                            'borderColor': [
                                'rgba(255, 99, 132, 1)',
                                'rgba(54, 162, 235, 1)',
                                'rgba(255, 206, 86, 1)',
                                'rgba(75, 192, 192, 1)',
                                'rgba(153, 102, 255, 1)',
                                'rgba(255, 159, 64, 1)'
                            ],
                            'borderWidth': 1,
                            'hoverOffset': 4
                        }]
                    },
                    'options': {
                        'scales': {
                            'y': {
                                'beginAtZero': 'true'
                            }
                        }
                    }
                }
            }
        })
        return context


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

    def get_queryset(self):
        try:
            return super().get_queryset().order_by('name')
        except FieldError:
            return super().get_queryset()


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
            'modal_title': f'Details of {self.object._meta.verbose_name}',
        })
        return context


class OwnedObjectUpdateView(PermissionRequiredMixin, NextOrSuccessUrlMixin, UpdateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Update {self.object._meta.verbose_name}',
            'submit_button_text': 'Save'
        })
        return context


class OwnedObjectModalUpdateView(PermissionRequiredMixin, NextOrSuccessUrlMixin, BSModalUpdateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': f'Update {self.object._meta.verbose_name}',
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
