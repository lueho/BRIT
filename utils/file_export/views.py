import logging

from celery.result import AsyncResult
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin

from utils.object_management.permissions import (
    build_scope_filter_params,
    filter_queryset_for_user,
)

logger = logging.getLogger(__name__)

SESSION_KEY = "export_task_ids"


def _store_task_id(request, task_id):
    """Store a Celery task ID in the session so only the initiating user can poll it."""
    session = getattr(request, "session", None)
    if session is None:
        return
    pending = session.setdefault(SESSION_KEY, [])
    pending.append(task_id)
    session.modified = True


class SingleObjectFileExportView(LoginRequiredMixin, SingleObjectMixin, View):
    """Base view for triggering an async export of a single object.

    Subclasses must define:
    - ``model``: the Django model to export.
    - ``task_function`` **or** override ``get_task_function()``: the Celery
      task that performs the export.

    Optional overrides:
    - ``get_task_args(obj)`` – positional args passed to the task
      (default: ``(obj.pk,)``).
    - ``get_task_kwargs(obj)`` – keyword args passed to the task
      (default: ``{}``).
    - ``get_queryset()`` – default implementation applies
      ``filter_queryset_for_user`` for visibility.
    """

    task_function = None

    def get_task_function(self):
        """Return the Celery task callable.

        Override this instead of setting ``task_function`` when an inline
        import is needed to avoid circular imports.
        """
        if self.task_function is None:
            raise NotImplementedError(
                "Subclasses must define task_function or override get_task_function()."
            )
        return self.task_function

    def get_task_args(self, obj):
        """Return positional args for the Celery task."""
        return (obj.pk,)

    def get_task_kwargs(self, obj):
        """Return keyword args for the Celery task."""
        return {}

    def get_queryset(self):
        """Restrict to objects visible to the requesting user."""
        return filter_queryset_for_user(super().get_queryset(), self.request.user)

    def get(self, request, *args, **kwargs):
        """Dispatch the export task and return a JSON response with the task ID."""
        obj = self.get_object()
        task_fn = self.get_task_function()
        task = task_fn.delay(*self.get_task_args(obj), **self.get_task_kwargs(obj))
        _store_task_id(request, task.task_id)
        return JsonResponse({"task_id": task.task_id})


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
        params.pop("page", None)
        list_type = params.pop("list_type", ["published"])[0]

        params.update(build_scope_filter_params(list_type, request.user))
        return params

    def get_export_context(self, request, params):
        """
        Build context dict for export task (e.g., user_id, list_type).
        """
        context = {
            "user_id": request.user.pk,
            "list_type": params.get("list_type", ["published"])[0],
        }
        return context

    def _dispatch_task(self, request, file_format, filter_params, export_context):
        """Dispatch the Celery export task.

        Override in subclasses that need a different task signature.
        Returns the Celery ``AsyncResult``.
        """
        if not self.task_function:
            raise NotImplementedError("Subclasses must define task_function")
        return self.task_function.delay(file_format, filter_params, export_context)

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests for file export.

        Args:
            request: The HTTP request

        Returns:
            JSON response with task ID
        """
        params = dict(request.GET)
        file_format = params.pop("format", ["csv"])[0]

        filter_params = self.get_filter_params(request, params.copy())
        export_context = self.get_export_context(request, params.copy())

        task = self._dispatch_task(request, file_format, filter_params, export_context)
        _store_task_id(request, task.task_id)

        return JsonResponse({"task_id": task.task_id})


class GenericUserCreatedObjectExportView(FilteredListFileExportView):
    """
    Generic export view for any UserCreatedObject-derived model.
    Subclasses must define model_label (e.g. 'soilcom.Collection').
    """

    model_label = None  # e.g. 'soilcom.Collection'

    def _dispatch_task(self, request, file_format, filter_params, export_context):
        """Dispatch the generic UserCreatedObject export task."""
        from .generic_tasks import export_user_created_object_to_file

        if not self.model_label:
            raise NotImplementedError("Subclasses must set model_label")
        return export_user_created_object_to_file.delay(
            self.model_label, file_format, filter_params, export_context
        )


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
    """Poll Celery task progress for an export initiated by the current user.

    The view validates that ``task_id`` belongs to the requesting session
    (stored by ``_store_task_id``) and cleans up the session entry once the
    task reaches a terminal state (``SUCCESS`` or ``FAILURE``).
    """

    def get(self, request, task_id):
        """Return current task state as JSON."""
        allowed_ids = request.session.get(SESSION_KEY, [])
        if task_id not in allowed_ids:
            return JsonResponse(
                {"state": "DENIED", "details": "Not authorised to view this task."},
                status=403,
            )

        result = AsyncResult(task_id)
        info = result.info
        # Handle non-serializable info (e.g., exceptions)
        if isinstance(info, Exception):
            info = {"error": str(info)}

        # Clean up completed/failed tasks from session
        if result.state in {"SUCCESS", "FAILURE"}:
            allowed_ids.remove(task_id)
            request.session.modified = True

        return JsonResponse({"state": result.state, "details": info})
