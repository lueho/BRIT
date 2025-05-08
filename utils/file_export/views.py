import json
import logging

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views import View
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)


class BaseFileExportView(View):
    """
    Generic base view for exporting filtered model data to a file.
    Subclasses should define:
    - task_function: The Celery task function to execute
    - get_filter_params(request, params): Method to process filter parameters (default: no-op)
    - get_export_context(request, params): Method to provide export context (default: empty dict)
    This class is permission-agnostic and suitable for use as a standalone package.
    """
    task_function = None

    def get_filter_params(self, request, params):
        """
        Override in subclasses to process filter parameters.
        By default, returns params unchanged.
        """
        return params

    def get_export_context(self, request, params):
        """
        Override in subclasses to build a context dict for export task.
        By default, returns empty dict.
        """
        return {}

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
        file_format = params.pop("format", ["csv"])[0]

        filter_params = self.get_filter_params(request, params.copy())
        export_context = self.get_export_context(request, params.copy())

        task = self.task_function.delay(file_format, filter_params, export_context)

        response_data = {"task_id": task.task_id}
        return HttpResponse(json.dumps(response_data), content_type="application/json")


class GenericUserCreatedObjectExportView(LoginRequiredMixin, BaseFileExportView):
    """
    Generic export view for any UserCreatedObject-derived model.
    Subclasses must define model_label (e.g. 'soilcom.Collection').
    """

    model_label = None  # e.g. 'soilcom.Collection'
    file_format_param = "format"

    def get(self, request, *args, **kwargs):
        from .generic_tasks import export_user_created_object_to_file

        if not self.model_label:
            raise NotImplementedError("Subclasses must set model_label")
        params = dict(request.GET)
        file_format = params.pop(self.file_format_param, ["csv"])[0]
        filter_params = self.get_filter_params(request, params.copy())
        export_context = self.get_export_context(request, params.copy())
        task = export_user_created_object_to_file.delay(
            self.model_label, file_format, filter_params, export_context
        )
        response_data = {"task_id": task.task_id}
        return HttpResponse(json.dumps(response_data), content_type="application/json")


class ExportModalView(LoginRequiredMixin, TemplateView):
    """
    View to render the export modal content for dynamic loading.
    """

    template_name = "export_modal_content.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["export_url"] = self.request.GET.get("export_url", "")
        for k, v in self.request.GET.items():
            if k != "export_url":
                context[k] = v
        return context


class FilteredListFileExportProgressView(LoginRequiredMixin, View):

    @staticmethod
    def get(request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            "state": result.state,
            "details": result.info,
        }
        return HttpResponse(json.dumps(response_data), content_type="application/json")
