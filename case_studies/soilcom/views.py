from django.shortcuts import render
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from bootstrap_modal_forms.generic import BSModalCreateView, BSModalUpdateView, BSModalDeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from brit.views import UserOwnsObjectMixin, NextOrSuccessUrlMixin

from . import models
from . import forms
from . import tables
from materials.models import Material


class CollectorListView(SingleTableView):
    template_name = 'collectors_list.html'
    model = models.Collector
    table_class = tables.CollectorsTable

    def get_queryset(self):
        return models.Collector.objects.filter(id=3)


class CollectorCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, BSModalCreateView):
    template_name = 'modal_form.html'
    form_class = forms.CollectorModelForm
    success_url = reverse_lazy('collector_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)
