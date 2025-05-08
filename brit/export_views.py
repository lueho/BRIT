"""BRIT-specific wrapper views around the generic `file_export` package.

This module re-introduces BRIT permission logic (public vs. private, owner checks)
that was stripped out of the generic `file_export` package.  Import these classes
from BRIT apps instead of the generic ones.
"""

import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from utils.file_export.views import BaseFileExportView, GenericUserCreatedObjectExportView as _GenericUCV


class BritFilteredListFileExportView(LoginRequiredMixin, BaseFileExportView):
    """Equivalent to the old `FilteredListFileExportView` with BRIT logic."""

    def get_filter_params(self, request, params):
        """Add owner/publication filters based on list_type like the legacy view."""
        params.pop("page", None)
        list_type = params.pop("list_type", ["public"])[0]
        if list_type == "private":
            params["owner"] = [request.user.pk]
        else:
            params["publication_status"] = ["published"]
        return params

    def get_export_context(self, request, params):
        return {
            "user_id": request.user.pk,
            "list_type": params.get("list_type", ["public"])[0],
        }


class BritGenericUserCreatedObjectExportView(BritFilteredListFileExportView, _GenericUCV):
    """Generic export view with BRIT permission logic baked in."""

    # Inherits behaviour from both parents; method resolution order ensures our
    # get_filter_params / get_export_context override the generic ones.
    pass
