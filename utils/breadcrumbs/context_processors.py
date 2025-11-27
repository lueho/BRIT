"""
Context processor for breadcrumbs.

Provides minimal breadcrumbs to all templates, falling back to just Home
when views don't use BreadcrumbMixin.
"""

from django.urls import resolve, reverse

from .mixins import Breadcrumb


def breadcrumbs(request):
    """
    Add breadcrumbs to template context.

    Priority:
    1. Use view's get_breadcrumbs() if BreadcrumbMixin is present
    2. Generate minimal breadcrumbs (just Home) as fallback

    Note: Views using BreadcrumbMixin will override this via get_context_data.
    This processor only handles views without BreadcrumbMixin.
    """
    # Try to detect if view will provide its own breadcrumbs
    try:
        match = resolve(request.path)
        view_func = match.func

        # Check for class-based view with breadcrumbs
        if hasattr(view_func, "view_class"):
            view_class = view_func.view_class
            if hasattr(view_class, "get_breadcrumbs"):
                # View will add its own breadcrumbs via get_context_data
                return {}
    except Exception:
        pass

    # Fallback: provide minimal breadcrumbs
    # Only show Home for views without BreadcrumbMixin
    try:
        home_url = reverse("home")
        current_path = request.path

        # If we're on the home page, just show "Home" as active
        if current_path.rstrip("/") == home_url.rstrip("/"):
            return {"breadcrumbs": [Breadcrumb("Home", None, "fa-home")]}

        # Otherwise show Home as a link
        return {"breadcrumbs": [Breadcrumb("Home", home_url, "fa-home")]}
    except Exception:
        return {"breadcrumbs": []}
