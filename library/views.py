from bootstrap_modal_forms.generic import BSModalReadView, BSModalUpdateView, BSModalDeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView

from flexibi_dst.views import UserOwnsObjectMixin, NextOrSuccessUrlMixin
from .forms import LitSourceModelForm
from .models import LiteratureSource
from .tables import SourceTable


# ----------- LiteratureSource CRUD ------------------------------------------------------------------------------------

class LiteratureSourceListView(ListView):
    model = LiteratureSource
    template_name = 'source_list.html'
    queryset = LiteratureSource.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'table': SourceTable(self.get_queryset())})
        return context


class LiteratureSourceCreateView(LoginRequiredMixin, NextOrSuccessUrlMixin, CreateView):
    form_class = LitSourceModelForm
    template_name = 'source_create.html'
    success_url = reverse_lazy('literature source_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Add new source',
            'submit_button_text': 'Add'
        })
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class LiteratureSourceDetailView(BSModalReadView):
    model = LiteratureSource
    template_name = 'modal_source_detail.html'
    object = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': 'Source details',
        })
        return context


class LiteratureSourceUpdateView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalUpdateView):
    model = LiteratureSource
    form_class = LitSourceModelForm
    template_name = 'modal_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Edit source',
            'submit_button_text': 'Edit'
        })
        return context


class LiteratureSourceDeleteView(LoginRequiredMixin, UserOwnsObjectMixin, NextOrSuccessUrlMixin, BSModalDeleteView):
    model = LiteratureSource
    template_name = 'modal_delete.html'
    success_message = 'Successfully deleted.'
    success_url = reverse_lazy('litsource_list')
