from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import FormView, ListView, RedirectView, TemplateView

from .forms import WasteAtlasMapConfigurationForm
from .map_selection import (
    MAP_SELECTION_YEARS,
    build_conflict_maps_context,
    build_map_selection_context,
    build_overview_directory_context,
    collection_detail_categories_for_theme,
    resolve_map_set,
)
from .models import WasteAtlasMapConfiguration
from .pages import MAP_PAGES, MAP_SET_LABELS
from .params import (
    parse_atlas_year,
    parse_country,
    parse_nuts_level,
    parse_nuts_prefix,
    parse_year,
)
from .viewsets import _effective_scope, is_maintainer


class AtlasShellTreeMixin:
    """Provide the registry-driven map tree for the atlas app shell."""

    atlas_tree_selected_region = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("atlas_active_theme", "")
        if "directory_region_groups" not in ctx:
            ctx.update(
                build_overview_directory_context(
                    reverse,
                    selected_region=self.atlas_tree_selected_region,
                )
            )
        return ctx


def resolve_map_page(map_set, theme):
    """Return the ``MAP_PAGES`` entry for a map set and theme, or raise 404."""
    for page in MAP_PAGES:
        if page["selector_set"] == map_set and page["theme"] == theme:
            return page
    raise Http404(f"No waste atlas map for {map_set}/{theme}")


def _previous_selection_year(year):
    year = str(year)
    if year in MAP_SELECTION_YEARS:
        index = MAP_SELECTION_YEARS.index(year)
        return MAP_SELECTION_YEARS[index - 1] if index else year
    try:
        return str(int(year) - 1)
    except ValueError:
        return year


class WasteAtlasStaffMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict configuration tools to authenticated staff users."""

    def test_func(self):
        return self.request.user.is_staff


def _configuration_map_pages(config_key):
    pages = []
    seen_urls = set()
    for page in MAP_PAGES:
        if page["config_key"] != config_key:
            continue
        url = reverse(page["name"])
        if url in seen_urls:
            continue
        seen_urls.add(url)
        pages.append(
            {
                "title": page["title"],
                "region": MAP_SET_LABELS.get(page["selector_set"], "Generic"),
                "url": url,
            }
        )
    return pages


def _configuration_return_paths(config_key):
    paths = {page["url"] for page in _configuration_map_pages(config_key)}
    for page in MAP_PAGES:
        if page["config_key"] != config_key or not page["selector_set"]:
            continue
        paths.add(
            reverse(
                "waste-atlas-change-map",
                args=[page["selector_set"], page["theme"]],
            )
        )
    return paths


class WasteAtlasMapConfigurationListView(
    WasteAtlasStaffMixin,
    AtlasShellTreeMixin,
    ListView,
):
    model = WasteAtlasMapConfiguration
    template_name = "waste_atlas/map_configuration_list.html"
    context_object_name = "map_configurations"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for configuration in ctx["map_configurations"]:
            configuration.map_pages = _configuration_map_pages(configuration.key)
            configuration.category_count = len(
                configuration.configuration.get("categories", [])
            )
        return ctx


class WasteAtlasMapConfigurationUpdateView(
    WasteAtlasStaffMixin,
    AtlasShellTreeMixin,
    FormView,
):
    form_class = WasteAtlasMapConfigurationForm
    template_name = "waste_atlas/map_configuration_form.html"

    def get_object(self):
        if not hasattr(self, "object"):
            self.object = get_object_or_404(
                WasteAtlasMapConfiguration,
                key=self.kwargs["key"],
            )
        return self.object

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        configuration = self.get_object()
        ctx["map_configuration"] = configuration
        ctx["preview_pages"] = _configuration_map_pages(configuration.key)
        ctx["return_to"] = self.get_return_url()
        return ctx

    def get_return_url(self):
        candidate = self.request.POST.get("return_to") or self.request.GET.get(
            "return_to"
        )
        if candidate:
            parsed = urlsplit(candidate)
            allowed_paths = _configuration_return_paths(self.get_object().key)
            if not parsed.scheme and not parsed.netloc and parsed.path in allowed_paths:
                return candidate

        preview_pages = _configuration_map_pages(self.get_object().key)
        if preview_pages:
            return preview_pages[0]["url"]
        return reverse("waste-atlas-map-configuration-list")

    def form_valid(self, form):
        configuration = form.save()
        messages.success(
            self.request,
            f'Map configuration "{configuration.key}" was updated.',
        )
        return super().form_valid(form)

    def get_success_url(self):
        return_to = urlsplit(self.get_return_url())
        query = [
            (key, value)
            for key, value in parse_qsl(return_to.query, keep_blank_values=True)
            if key != "config_updated"
        ]
        query.append(
            (
                "config_updated",
                str(int(self.get_object().updated_at.timestamp() * 1_000_000)),
            )
        )
        return urlunsplit(return_to._replace(query=urlencode(query)))


@method_decorator(never_cache, name="dispatch")
class AtlasMapView(TemplateView):
    """Generic choropleth map page driven by a ``MAP_PAGES`` entry.

    The page entry (see ``pages.py``) provides the URL, title, region scope,
    selector theme, and the key of the database-backed JS map configuration.
    ``year`` can always be overridden via query string;
    ``country``/``nuts_*`` only when the page is not locked to a region.
    """

    template_name = "waste_atlas/map.html"
    page = None

    def get_template_names(self):
        return [self.page.get("template", self.template_name)]

    def _get_param(self, key, default, parse):
        if self.page["lock"]:
            return default
        return parse(self.request.GET.get(key), default)

    def get_country(self):
        return self._get_param("country", self.page["country"], parse_country)

    def get_nuts_prefix(self):
        return self._get_param(
            "nuts_prefix", self.page.get("nuts_prefix", ""), parse_nuts_prefix
        )

    def get_nuts_level(self):
        return self._get_param(
            "nuts_level", self.page.get("nuts_level", ""), parse_nuts_level
        )

    def get_selected_map_set(self):
        if self.page["selector_set"]:
            return self.page["selector_set"]
        return resolve_map_set(
            self.get_country(),
            self.get_nuts_prefix(),
            self.get_nuts_level(),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = self.page
        selected_map_set = self.get_selected_map_set()
        ctx["country"] = self.get_country()
        ctx["year"] = str(parse_year(self.request.GET.get("year"), page["year"]))
        ctx["atlas_scope"] = _effective_scope(
            self.request.user, self.request.GET.get("scope", "published")
        )[0]
        ctx["can_review_collections"] = is_maintainer(self.request.user)
        ctx["nuts_prefix"] = self.get_nuts_prefix()
        ctx["nuts_level"] = self.get_nuts_level()
        ctx["map_title"] = page["title"]
        ctx["map_overview_label"] = "Map overview"
        ctx["map_overview_url"] = "waste-atlas-overview"
        region_label = MAP_SET_LABELS.get(selected_map_set, "")
        overview_href = reverse("waste-atlas-overview")
        ctx["atlas_map_set"] = selected_map_set
        ctx["atlas_page_selector_set"] = page.get("selector_set")
        ctx["breadcrumb_module_label"] = "Waste Atlas"
        ctx["breadcrumb_module_url"] = overview_href
        if region_label:
            ctx["breadcrumb_section_label"] = region_label
            ctx["breadcrumb_section_url"] = f"{overview_href}?region={selected_map_set}"
        ctx["breadcrumb_object_label"] = page["title"]
        ctx["map_config_key"] = page["config_key"]
        edit_url = reverse(
            "waste-atlas-map-configuration-update",
            args=[page["config_key"]],
        )
        ctx["map_configuration_edit_url"] = (
            f"{edit_url}?{urlencode({'return_to': self.request.get_full_path()})}"
        )
        ctx["map_config_overrides"] = page.get("overrides")
        # Composite themes contribute several categories; the API takes them as
        # one comma-separated parameter.
        ctx["collection_detail_category"] = (
            ",".join(collection_detail_categories_for_theme(page["theme"])) or None
        )
        ctx["atlas_active_theme"] = page["theme"]
        ctx.update(
            build_overview_directory_context(reverse, selected_region=selected_map_set)
        )
        ctx.update(
            build_map_selection_context(
                reverse,
                selected_map_set=selected_map_set,
                selected_theme=page["theme"],
            )
        )
        selected_theme_option = next(
            (
                theme
                for theme in ctx["map_selection_themes_by_map_set"].get(
                    selected_map_set, []
                )
                if theme["value"] == page["theme"]
            ),
            None,
        )
        ctx["is_change_map"] = False
        change_url = (
            selected_theme_option["change_url"] if selected_theme_option else ""
        )
        ctx["map_toggle_url"] = (
            f"{change_url}?{urlencode({'from_year': _previous_selection_year(ctx['year']), 'to_year': ctx['year'], 'scope': ctx['atlas_scope']})}"
            if change_url
            else ""
        )
        ctx["map_toggle_label"] = "View changes for this map"
        ctx.update(self.get_permalink_context(ctx["year"]))
        return ctx

    def shows_registered_region(self):
        """Whether the rendered region is the one the page is registered for.

        Unlocked pages accept region overrides in the query string, but a
        permalink only names the page's own region, so it must not stand in
        for another one.
        """
        page = self.page
        return (
            self.get_country() == page["country"]
            and self.get_nuts_prefix() == page.get("nuts_prefix", "")
            and str(self.get_nuts_level()) == str(page.get("nuts_level", ""))
        )

    def get_permalink_context(self, year):
        """Permanent link of a region-set map, plus what the renderer needs to
        keep it in step with in-place year reloads."""
        page = self.page
        if not page["selector_set"]:
            return {"atlas_permalink_url": ""}
        # The year is the last path segment; reverse with a placeholder year
        # and drop it to get the stable per-map base.
        placeholder = reverse(
            "waste-atlas-permalink", args=[page["selector_set"], page["theme"], 0]
        )
        base = self.request.build_absolute_uri(placeholder.removesuffix("0/"))
        return {
            "atlas_permalink_url": f"{base}{year}/"
            if year in MAP_SELECTION_YEARS and self.shows_registered_region()
            else "",
            "atlas_permalink_base": base,
            "atlas_permalink_country": page["country"],
            "atlas_permalink_nuts_prefix": page.get("nuts_prefix", ""),
            "atlas_permalink_nuts_level": page.get("nuts_level", ""),
            "atlas_permalink_years": ",".join(MAP_SELECTION_YEARS),
        }


class AtlasChangeMapView(AtlasMapView):
    """Generic change map comparing a map theme between two years.

    The page entry is resolved from the ``map_set``/``theme`` URL kwargs.
    The client fetches the theme's data endpoint for both years. Numeric
    themes are classified by value difference; categorical themes are
    classified as no-change/changed/new/removed.
    Supports ``from_year`` and ``to_year`` query params.
    """

    template_name = "waste_atlas/change_map.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.page = resolve_map_page(kwargs["map_set"], kwargs["theme"])

    def get_template_names(self):
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["map_overview_url"] = "waste-atlas-change-map-overview"
        ctx["from_year"] = str(
            parse_atlas_year(self.request.GET.get("from_year"), 2024)
        )
        ctx["to_year"] = str(parse_atlas_year(self.request.GET.get("to_year"), 2024))
        ctx["year"] = ctx["to_year"]
        ctx["default_from_year"] = ctx["from_year"]
        ctx["default_to_year"] = ctx["to_year"]
        ctx["map_title"] = f"{self.page['title']} — changes"
        ctx["breadcrumb_object_label"] = ctx["map_title"]
        ctx["is_change_map"] = True
        ctx["map_toggle_url"] = (
            f"{reverse(self.page['name'])}?{urlencode({'year': ctx['year'], 'scope': ctx['atlas_scope']})}"
        )
        ctx["map_toggle_label"] = "View current map"
        return ctx

    def get_permalink_context(self, year):
        """Change maps compare two years; a permalink names a single year."""
        return {"atlas_permalink_url": ""}


class AtlasPermalinkView(RedirectView):
    """Resolve a citable map permalink to the map's current page.

    Permalinks name a map by region set, theme and year instead of by page
    path, so they keep working when page paths or the mount point change. They
    always resolve to the published scope and show the data as published when
    opened.
    """

    permanent = False

    def get_redirect_url(self, *args, map_set, theme, year, **kwargs):
        if str(year) not in MAP_SELECTION_YEARS:
            raise Http404(f"No waste atlas map for year {year}")
        page = resolve_map_page(map_set.upper(), theme)
        return f"{reverse(page['name'])}?{urlencode({'year': year})}"


class WasteAtlasOverviewView(TemplateView):
    """Overview page linking to all waste atlas maps."""

    template_name = "waste_atlas/overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["selected_required_bin_capacity_reference"] = self.request.GET.get(
            "required_bin_capacity_reference",
            "person",
        )
        ctx.update(
            build_overview_directory_context(
                reverse,
                selected_region=self.request.GET.get("region"),
            )
        )
        ctx["directory_selected_category"] = self.request.GET.get("category", "")
        ctx["directory_query"] = self.request.GET.get("q", "")
        ctx["atlas_tree_overview_active"] = True
        return ctx


class WasteAtlasChangeMapOverviewView(AtlasShellTreeMixin, TemplateView):
    """Overview page for change maps — compare two versions of a waste atlas map."""

    template_name = "waste_atlas/change_map_overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["atlas_scope"] = _effective_scope(
            self.request.user, self.request.GET.get("scope", "published")
        )[0]
        ctx["can_review_collections"] = is_maintainer(self.request.user)
        selection_ctx = build_map_selection_context(reverse)
        years = list(selection_ctx["map_selection_years"])
        ctx.update(selection_ctx)
        default_year = years[-1] if years else "2024"
        ctx["default_from_year"] = str(
            parse_atlas_year(self.request.GET.get("from_year"), default_year)
        )
        ctx["default_to_year"] = str(
            parse_atlas_year(self.request.GET.get("to_year"), default_year)
        )
        return ctx


class WasteAtlasDataConflictsOverviewView(
    WasteAtlasStaffMixin, AtlasShellTreeMixin, TemplateView
):
    """Overview page listing maps with the maintainer conflict-overlay aid.

    Surfaces every choropleth map whose stored configuration opts into the
    conflict overlay (``conflictUrl``) so data maintainers can find maps that
    highlight catchments where the dataset holds conflicting theme values.
    """

    template_name = "waste_atlas/data_conflicts_overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_conflict_maps_context(reverse))
        return ctx


class EuropeDataCoverageContextMixin:
    """Provide shared context for the Europe coverage map page variants."""

    template_name = "waste_atlas/karte0_europe_data_coverage.html"
    base_template = "base.html"
    iframe_mode = False

    def get_context_data(self, **kwargs):
        """Provide page title, layout mode, and overview label context."""
        ctx = super().get_context_data(**kwargs)
        ctx["map_title"] = "Waste collection data coverage in Europe"
        ctx["map_overview_label"] = "Map overview"
        ctx["base_template"] = self.base_template
        ctx["iframe_mode"] = self.iframe_mode
        return ctx


class EuropeDataCoverageMapView(EuropeDataCoverageContextMixin, TemplateView):
    """Map 0 — Waste collection data coverage in Europe."""


@method_decorator(xframe_options_exempt, name="dispatch")
class EuropeDataCoverageMapIframeView(EuropeDataCoverageContextMixin, TemplateView):
    """Iframe-friendly Europe coverage map for third-party embedding."""

    template_name = "waste_atlas/karte0_europe_data_coverage_iframe.html"
    base_template = "base_iframe.html"
    iframe_mode = True


class EuropeBiowasteCollectionAmountMapView(TemplateView):
    template_name = "waste_atlas/karte41_europe_biowaste_collection_amount.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["map_title"] = (
            "Regional average amount of separately collected biowaste in Europe"
        )
        ctx["map_overview_label"] = "Map overview"
        ctx["year"] = "2024"
        return ctx
