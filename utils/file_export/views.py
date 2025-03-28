import json

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views import View


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
        # Remove pagination parameters
        params.pop('page', None)
        list_type = params.pop('list_type', ['public'])[0]

        if list_type == 'private':
            params['owner'] = [request.user.pk]
        else:
            params['publication_status'] = ['published']
        return params

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

        filter_params = self.get_filter_params(request, params)

        task = self.task_function.delay(file_format, filter_params)

        response_data = {
            'task_id': task.task_id
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')


class FilteredListFileExportProgressView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            'state': result.state,
            'details': result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')
