"""
Breadcrumb mixin for class-based views.

Provides automatic breadcrumb generation based on view type and model hierarchy.
"""

from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .config import (
    SECTIONS,
    get_section_for_model,
    get_subsection_for_model,
)


def _urls_match(url1: str | None, url2: str | None) -> bool:
    """Check if two URLs point to the same page (ignoring query strings)."""
    if not url1 or not url2:
        return False
    # Strip query strings and trailing slashes for comparison
    return url1.rstrip("/").split("?")[0] == url2.rstrip("/").split("?")[0]


class Breadcrumb:
    """A single breadcrumb item."""

    __slots__ = ("label", "url", "icon", "is_active")

    def __init__(self, label: str, url: str | None = None, icon: str | None = None):
        self.label = label
        self.url = url
        self.icon = icon
        self.is_active = url is None

    def __repr__(self):
        return f"Breadcrumb({self.label!r}, {self.url!r})"

    def __iter__(self):
        """Allow tuple unpacking: label, url, icon = breadcrumb."""
        return iter((self.label, self.url, self.icon))


class BreadcrumbMixin:
    """
    Mixin for views to provide breadcrumb navigation.

    Usage:
        class MyDetailView(BreadcrumbMixin, DetailView):
            model = MyModel

        # Or with manual breadcrumbs:
        class MyView(BreadcrumbMixin, TemplateView):
            def get_breadcrumbs(self):
                return [
                    Breadcrumb("Home", reverse("home")),
                    Breadcrumb("Current Page"),
                ]
    """

    # Override in subclass to provide custom breadcrumbs
    breadcrumb_section: str | None = None  # e.g., "materials", "maps"
    breadcrumb_label: str | None = None  # Override the final breadcrumb label

    def get_breadcrumbs(self) -> list[Breadcrumb]:
        """
        Generate breadcrumbs for the current view.

        Returns a list of Breadcrumb objects. Override in subclass for custom behavior.
        """
        crumbs = []

        # Get current request path for comparison
        current_path = None
        try:
            current_path = self.request.path
        except AttributeError:
            pass

        home_url = reverse("home")

        # Always start with Home (unless we ARE home)
        if not _urls_match(current_path, home_url):
            crumbs.append(Breadcrumb("Home", home_url, "fa-home"))

        # Determine section from model or explicit setting
        section = self._get_section()
        section_url = None
        is_on_section_page = False
        if section:
            try:
                section_url = reverse(section["url_name"])
            except Exception:
                section_url = None

            is_on_section_page = _urls_match(current_path, section_url)
            # Add section as link if we're not ON it, otherwise we'll add it as active later
            if not is_on_section_page:
                crumbs.append(
                    Breadcrumb(section["label"], section_url, section["icon"])
                )

        # Add subsection if applicable (e.g., "Samples" within "Materials")
        subsection = self._get_subsection()
        is_on_subsection_page = False
        if subsection and subsection != section:
            try:
                subsection_url = reverse(subsection["url_name"])
                is_on_subsection_page = _urls_match(current_path, subsection_url)
                # Add subsection as link if we're not ON it
                if not is_on_subsection_page:
                    crumbs.append(Breadcrumb(subsection["label"], subsection_url))
            except Exception:
                pass

        # Add view-specific breadcrumbs
        view_crumbs = self._get_view_breadcrumbs()

        # If we're on a section/subsection page with no other breadcrumbs, add it as active
        if not view_crumbs:
            if is_on_subsection_page and subsection:
                crumbs.append(Breadcrumb(subsection["label"]))
            elif is_on_section_page and section:
                crumbs.append(Breadcrumb(section["label"]))

        crumbs.extend(view_crumbs)

        # Mark last item as active (no URL)
        if crumbs:
            last = crumbs[-1]
            last.url = None
            last.is_active = True

        return crumbs

    def _get_section(self) -> dict | None:
        """Determine the section for this view."""
        # Explicit section setting takes precedence
        if self.breadcrumb_section:
            return SECTIONS.get(self.breadcrumb_section)

        # Try to determine from model
        model = getattr(self, "model", None)
        if model is None:
            # Try to get from queryset
            queryset = getattr(self, "queryset", None)
            if queryset is not None:
                model = queryset.model

        if model:
            return get_section_for_model(model._meta.model_name)

        return None

    def _get_subsection(self) -> dict | None:
        """Determine the subsection for this view (model-level list page)."""
        model = getattr(self, "model", None)
        if model is None:
            queryset = getattr(self, "queryset", None)
            if queryset is not None:
                model = queryset.model

        if model:
            return get_subsection_for_model(model._meta.model_name)

        return None

    def _get_view_breadcrumbs(self) -> list[Breadcrumb]:
        """Generate view-type-specific breadcrumbs."""
        crumbs = []

        # DetailView: add object name
        if isinstance(self, DetailView):
            obj = getattr(self, "object", None)
            if obj is None:
                try:
                    obj = self.get_object()
                except Exception:
                    pass

            # Check for parent object (e.g., Sample -> SampleSeries)
            parent_crumbs = self._get_parent_breadcrumbs(obj)
            crumbs.extend(parent_crumbs)

            # Add the object itself
            if obj:
                label = self.breadcrumb_label or str(obj)
                crumbs.append(Breadcrumb(label))

        # ListView: usually just the section/subsection (already added)
        elif isinstance(self, ListView):
            # Custom label if provided
            if self.breadcrumb_label:
                crumbs.append(Breadcrumb(self.breadcrumb_label))

        # CreateView: add "Create {Model}"
        elif isinstance(self, CreateView):
            model = getattr(self, "model", None)
            if model:
                label = self.breadcrumb_label or f"Create {model._meta.verbose_name}"
                crumbs.append(Breadcrumb(label))

        # UpdateView: add object name + "Edit"
        elif isinstance(self, UpdateView):
            obj = getattr(self, "object", None)
            if obj is None:
                try:
                    obj = self.get_object()
                except Exception:
                    pass

            if obj:
                # Add link to detail view
                try:
                    detail_url = obj.get_absolute_url()
                    crumbs.append(Breadcrumb(str(obj), detail_url))
                except Exception:
                    crumbs.append(Breadcrumb(str(obj)))

                # Add "Edit" as final
                crumbs.append(Breadcrumb(self.breadcrumb_label or "Edit"))

        # Other views (TemplateView, etc.): add custom label if provided
        elif self.breadcrumb_label:
            crumbs.append(Breadcrumb(self.breadcrumb_label))

        return crumbs

    def _get_parent_breadcrumbs(self, obj) -> list[Breadcrumb]:
        """
        Get breadcrumbs for parent objects in the hierarchy.

        Override in subclass for custom parent relationships.
        """
        crumbs = []
        if obj is None:
            return crumbs

        # Common parent relationships
        parent_attrs = ["series", "sample", "catchment", "collection", "scenario"]

        for attr in parent_attrs:
            parent = getattr(obj, attr, None)
            if parent is not None:
                try:
                    parent_url = parent.get_absolute_url()
                    crumbs.append(Breadcrumb(str(parent), parent_url))
                except Exception:
                    crumbs.append(Breadcrumb(str(parent)))
                break  # Only use first parent found

        return crumbs

    def get_context_data(self, **kwargs):
        """Add breadcrumbs to template context."""
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = self.get_breadcrumbs()
        return context
