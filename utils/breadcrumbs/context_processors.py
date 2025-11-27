"""
Context processor for breadcrumbs.

Provides breadcrumbs to all templates, falling back to URL-based generation
when views don't use BreadcrumbMixin.
"""

from django.urls import resolve, reverse

from .config import MODEL_SECTIONS, SECTIONS
from .mixins import Breadcrumb


def breadcrumbs(request):
    """
    Add breadcrumbs to template context.

    Priority:
    1. Use view's get_breadcrumbs() if BreadcrumbMixin is present
    2. Generate from URL pattern if possible
    3. Return minimal breadcrumbs (just Home)
    """
    crumbs = []

    # Try to get from view (if it has breadcrumbs)
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

    # Fallback: generate from URL pattern
    crumbs = _generate_from_url(request)

    return {"breadcrumbs": crumbs}


def _generate_from_url(request) -> list[Breadcrumb]:
    """Generate breadcrumbs from URL pattern analysis."""
    crumbs = [Breadcrumb("Home", reverse("home"), "fa-home")]

    try:
        match = resolve(request.path)
        url_name = match.url_name
        kwargs = match.kwargs

        if not url_name:
            return crumbs

        # Determine section from URL pattern
        section = _get_section_from_url(request.path, url_name)
        if section:
            try:
                section_url = reverse(section["url_name"])
                crumbs.append(
                    Breadcrumb(section["label"], section_url, section.get("icon"))
                )
            except Exception:
                crumbs.append(Breadcrumb(section["label"], None, section.get("icon")))

        # Add view-specific breadcrumb
        view_crumb = _get_view_breadcrumb(url_name, kwargs)
        if view_crumb:
            crumbs.append(view_crumb)

    except Exception:
        pass

    # Mark last as active
    if crumbs:
        crumbs[-1].url = None
        crumbs[-1].is_active = True

    return crumbs


def _get_section_from_url(path: str, url_name: str) -> dict | None:
    """Determine section from URL path or name."""
    # Check path prefix
    path_lower = path.lower()
    for section_key, section in SECTIONS.items():
        if f"/{section_key}/" in path_lower:
            return section

    # Check URL name prefix (e.g., "sample-list" -> materials)
    url_prefix = url_name.split("-")[0] if "-" in url_name else url_name
    section_key = MODEL_SECTIONS.get(url_prefix)
    if section_key:
        return SECTIONS.get(section_key)

    return None


def _get_view_breadcrumb(url_name: str, kwargs: dict) -> Breadcrumb | None:
    """Generate a breadcrumb for the current view based on URL name."""
    # Common URL name patterns
    if url_name.endswith("-list") or url_name.endswith("-list-owned"):
        # List views don't need extra breadcrumb (section covers it)
        return None

    if url_name.endswith("-create"):
        model_name = url_name.replace("-create", "")
        return Breadcrumb(f"Create {model_name.replace('-', ' ').title()}")

    if url_name.endswith("-detail"):
        # Detail views need the object, which we can't access here
        # The view's get_context_data should handle this
        return None

    if url_name.endswith("-update"):
        return Breadcrumb("Edit")

    # Static pages
    static_pages = {
        "home": None,  # Home is already added
        "about": Breadcrumb("About"),
        "learning": Breadcrumb("Learning"),
        "privacypolicy": Breadcrumb("Privacy Policy"),
    }
    return static_pages.get(url_name)
