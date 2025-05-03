import json
import logging

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views import View
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)

class FilteredListFileExportView(LoginRequiredMixin, View):
    """
    Base view for exporting filtered model data to a file.

    Subclasses should define:
    - task_function: The Celery task function to execute
    - get_filter_params(request, params): Method to process filter parameters
    """
    task_function = None

    def get_filter_params(self, request, params):
        """
        Process the filter parameters from the request.

        Args:
            request: The HTTP request
            params: Dictionary of query parameters

        Returns:
            Dictionary of processed filter parameters
        """
        params.pop('page', None)
        list_type = params.pop('list_type', ['public'])[0]

        if list_type == 'private':
            params['owner'] = [request.user.pk]
        else:
            params['publication_status'] = ['published']
        return params

    def get_allowed_ids(self, request, params):
        """
        Determine the allowed IDs for export based on the view's restriction (published, owned, etc).
        """
        params = params.copy()
        params.pop('page', None)
        list_type = params.pop('list_type', ['public'])[0]
        from case_studies.soilcom.models import Collection
        if list_type == 'private':
            base_qs = Collection.objects.filter(owner=request.user)
        else:
            base_qs = Collection.objects.filter(publication_status='published')
        ids = list(base_qs.values_list('pk', flat=True))
        return ids

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests for file export.

        Args:
            request: The HTTP request

        Returns:
            JSON response with task ID
        """
        if not self.task_function:
            raise NotImplementedError("Subclasses must define task_function")

        params = dict(request.GET)
        file_format = params.pop('format', ['csv'])[0]

        filter_params = self.get_filter_params(request, params.copy())
        allowed_ids = self.get_allowed_ids(request, params.copy())

        task = self.task_function.delay(file_format, filter_params, allowed_ids)

        response_data = {
            'task_id': task.task_id
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class GenericUserCreatedObjectExportView(FilteredListFileExportView):
    """
    Generic export view for any UserCreatedObject-derived model.
    Subclasses must define model_label (e.g. 'soilcom.Collection').
    """
    model_label = None  # e.g. 'soilcom.Collection'
    file_format_param = 'format'

    def get_allowed_ids(self, request, params):
        params = params.copy()
        params.pop('page', None)
        list_type = params.pop('list_type', ['public'])[0]
        from django.apps import apps
        model = apps.get_model(self.model_label)
        if list_type == 'private':
            base_qs = model.objects.filter(owner=request.user)
        else:
            base_qs = model.objects.filter(publication_status='published')
        ids = list(base_qs.values_list('pk', flat=True))
        return ids

    def get(self, request, *args, **kwargs):
        from .generic_tasks import export_user_created_object_to_file
        if not self.model_label:
            raise NotImplementedError('Subclasses must set model_label')
        params = dict(request.GET)
        file_format = params.pop(self.file_format_param, ['csv'])[0]
        filter_params = self.get_filter_params(request, params.copy())
        allowed_ids = self.get_allowed_ids(request, params.copy())
        task = export_user_created_object_to_file.delay(self.model_label, file_format, filter_params, allowed_ids)
        response_data = {'task_id': task.task_id}
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class ExportModalView(LoginRequiredMixin, TemplateView):
    """
    View to render the export modal content for dynamic loading.
    """
    template_name = 'export_modal_content.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['export_url'] = self.request.GET.get('export_url', '')
        for k, v in self.request.GET.items():
            if k != 'export_url':
                context[k] = v
        return context


class FilteredListFileExportProgressView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            'state': result.state,
            'details': result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')
