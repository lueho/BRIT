"""Responsive sizing and manual zoom for the Waste Atlas choropleth maps.

The renderer used to bake ``container.clientWidth`` and a fixed 1.17 aspect
ratio into the SVG once, so the map neither followed the canvas width when the
window changed nor offered any manual sizing.
"""

import re
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import RequestFactory, TestCase

WASTE_ATLAS_DIR = Path(__file__).resolve().parents[1] / "waste_atlas"
CHOROPLETH_SCRIPT = WASTE_ATLAS_DIR / "static" / "js" / "waste_atlas_choropleth.js"
ATLAS_STYLESHEET = WASTE_ATLAS_DIR / "static" / "css" / "waste_atlas.css"
SHELL_TEMPLATE = WASTE_ATLAS_DIR / "templates" / "waste_atlas" / "shell_base.html"


class WasteAtlasResponsiveMapScriptTests(TestCase):
    """The renderer must fit the canvas width and expose a zoom transform."""

    @classmethod
    def setUpTestData(cls):
        cls.script = CHOROPLETH_SCRIPT.read_text()
        cls.stylesheet = ATLAS_STYLESHEET.read_text()

    def test_screen_height_is_derived_from_projected_geometry(self):
        self.assertIn("function _geometryAspect(", self.script)
        self.assertIn("function _geographicBounds(", self.script)
        self.assertIn("function _mercatorY(", self.script)
        self.assertNotIn("width * 1.17", self.script)

    def test_geometry_aspect_does_not_depend_on_ring_winding(self):
        """Regression: d3's spherical clipping is winding-sensitive.

        Measuring the aspect with ``geoMercator().fitWidth()`` +
        ``geoPath().bounds()`` reports the whole (square) Mercator world for
        rings wound the RFC 7946 way, which collapsed every map to aspect 1.0.
        The aspect is therefore measured from the geographic bounding box.
        """
        aspect_body = self.script.split("function _geometryAspect(fitData)")[1]
        aspect_body = aspect_body.split("function _screenLayout(")[0]
        self.assertIn("_geographicBounds(fitData)", aspect_body)
        self.assertNotIn("fitWidth(", aspect_body)
        self.assertNotIn("geoPath(", aspect_body)

    def test_screen_layout_keeps_a_fallback_aspect_without_geometry(self):
        self.assertIn("SCREEN_FALLBACK_ASPECT", self.script)
        self.assertIn("SCREEN_MIN_ASPECT", self.script)
        self.assertIn("SCREEN_MAX_ASPECT", self.script)

    def test_fit_data_selection_is_shared_between_layout_and_render(self):
        self.assertIn("function _fitGeometry(", self.script)

    def test_map_is_rerendered_when_the_container_width_changes(self):
        self.assertIn("ResizeObserver", self.script)
        self.assertIn("function _observeContainerResize(", self.script)

    def test_geographic_layers_live_in_a_zoomable_root_group(self):
        self.assertIn("layer-map-root", self.script)
        for layer in (
            "layer-country-fill",
            "layer-catchments-all",
            "layer-catchments",
            "layer-bundeslaender",
            "layer-country-border",
        ):
            with self.subTest(layer=layer):
                self.assertIn(
                    f"mapRoot.append('g').attr('class', '{layer}')", self.script
                )
                self.assertNotIn(
                    f"_svg.append('g').attr('class', '{layer}')", self.script
                )

    def test_zoom_can_shrink_the_map_below_the_fitted_size(self):
        """Zooming out to 20% brings a tall map back onto a single screen."""
        self.assertIn("var ZOOM_MIN = 0.2;", self.script)

    def test_zoom_behaviour_is_wired_to_handles_wheel_and_drag(self):
        self.assertIn("d3.zoom()", self.script)
        self.assertIn("scaleExtent([ZOOM_MIN, ZOOM_MAX])", self.script)
        self.assertIn("function _setupZoom(", self.script)
        self.assertIn("btn-map-zoom-in", self.script)
        self.assertIn("btn-map-zoom-out", self.script)
        self.assertIn("btn-map-zoom-reset", self.script)
        self.assertIn("atlas-map-zoom-level", self.script)

    def test_zoom_is_reset_when_a_new_selection_is_loaded(self):
        self.assertIn("function _resetZoom(", self.script)

    def test_exports_take_their_page_geometry_from_the_database_defaults(self):
        """Page width and the height ladder come from the stored export defaults."""
        self.assertIn("return _exportPx(_exportDefaults().widthMm);", self.script)
        self.assertIn("var preferred = _exportDefaults().heightMm;", self.script)
        self.assertIn("var maximum = _exportDefaults().maxHeightMm;", self.script)
        self.assertIn(
            "_exportHeightCandidatesMm().forEach(function (heightMm)",
            self.script,
        )

    def test_aggregated_value_metadata_is_derived_once_from_the_raw_record(self):
        """Every transform would otherwise have to copy the ACPV flag along."""
        for transform_name in (
            "biowasteCollectionAmount",
            "residualCollectionAmount",
        ):
            with self.subTest(transform=transform_name):
                transform_body = self.script.split(f"{transform_name}: function")[1]
                transform_body = transform_body.split("    },", 1)[0]
                self.assertNotIn("_has_acpv_overlay", transform_body)

        annotate_body = self.script.split("function _annotateFeatures(data, cfg)")[1]
        annotate_body = annotate_body.split("function _acpvOverlayFlag", 1)[0]
        self.assertIn("_acpvOverlayFlag(", annotate_body)

    def test_the_hatch_and_the_group_outline_share_one_resolved_style(self):
        pattern_body = self.script.split(
            "function _defineOverlayPattern(cfg, mapWidth)"
        )[1]
        pattern_body = pattern_body.split("// ---- data fetching", 1)[0]
        self.assertIn("_acpvStyle(cfg, mapWidth)", pattern_body)
        self.assertIn(".attr('stroke', style.hatchColor)", pattern_body)
        self.assertIn(".attr('stroke-opacity', style.hatchOpacity)", pattern_body)

        style_body = self.script.split("function _acpvStyle(cfg, mapWidth)")[1]
        style_body = style_body.split("\n  }", 1)[0]
        # Colors are configurable atlas-wide and per map; the geometry scales
        # with the drawn map so screen and export look the same.
        self.assertIn("cfg.acpvHatchColor", style_body)
        self.assertIn("defaults.hatchColor", style_body)
        self.assertIn("cfg.acpvOutlineColor", style_body)
        self.assertIn("scale", style_body)

    def test_the_markers_are_sized_against_the_drawn_map_not_the_canvas(self):
        """An export page has its own aspect ratio and reserves legend space."""
        render_body = self.script.split("function _render(data, cfg, options)")[1]
        render_body = render_body.split("function _drawExportLegendItem")[0]

        self.assertIn("var projectedBounds = path.bounds(fitData);", render_body)
        self.assertIn(
            "_acpvStyle(cfg, projectedBounds[1][0] - projectedBounds[0][0])",
            render_body,
        )

    def test_exports_are_rendered_without_the_screen_zoom_transform(self):
        render_body = self.script.split("function _render(data, cfg, options)")[1]
        render_body = render_body.split("function _drawExportLegendItem")[0]

        # The zoom transform and the shared _mapRoot handle are screen-only.
        self.assertIn("if (!layout.exportMode) _mapRoot = mapRoot;", render_body)
        self.assertIn(
            "if (_zoomTransform) mapRoot.attr('transform', _zoomTransform);",
            render_body,
        )
        transform_index = render_body.index(
            "if (_zoomTransform) mapRoot.attr('transform', _zoomTransform);"
        )
        guard_index = render_body.rindex("if (!layout.exportMode)", 0, transform_index)
        self.assertLess(guard_index, transform_index)

    def test_a_click_survives_slight_pointer_movement(self):
        """Regression: catchments became completely unclickable.

        ``d3.zoom`` defaults ``clickDistance`` to 0, so a single pixel of mouse
        jitter between mousedown and mouseup marks the gesture as a drag. d3
        then swallows the following click with a capturing window listener, so
        the catchment's own click handler never ran and no collection opened.
        """
        self.assertIn("clickDistance(", self.script)
        self.assertIn("ZOOM_CLICK_DISTANCE", self.script)

    def test_drag_suppression_is_left_to_d3_zoom(self):
        """d3-zoom already cancels the click that terminates a real drag.

        The hand-rolled guard duplicated that and misfired: d3's mousedown
        handler calls ``stopImmediatePropagation()``, so the listener meant to
        clear the flag never ran and the next genuine click was eaten.
        """
        self.assertNotIn("_pannedRecently", self.script)
        self.assertNotIn("mousedown.atlaspan", self.script)

    def test_screen_legend_is_anchored_to_the_top_of_the_canvas(self):
        """The canvas is taller than the viewport, so a bottom legend loads
        below the fold and readers never see it without scrolling."""
        layout_body = self.script.split("function _screenLayout(container, fitData)")[1]
        layout_body = layout_body.split("function _measureTextWidth(")[0]
        self.assertIn("legendAtTop: true", layout_body)
        self.assertIn("layout.legendAtTop", self.script)

        # The reserved vertical band has to follow the legend to the top.
        self.assertIn("var SCREEN_PADDING_TOP = 100;", self.script)
        self.assertIn("var SCREEN_PADDING_BOTTOM = 40;", self.script)

    def test_top_legend_does_not_affect_exports(self):
        """Exports pick their own placement and must return before the
        screen-only anchoring runs."""
        legend_body = self.script.split(
            "function _drawLegend(width, height, cfg, layout)"
        )[1]
        export_branch = legend_body.index("if (layout.exportMode)")
        screen_anchor = legend_body.index("layout.legendAtTop")
        self.assertLess(export_branch, screen_anchor)
        self.assertIn("return;", legend_body[export_branch:screen_anchor])

    def test_stylesheet_lets_the_svg_fill_the_container_width(self):
        self.assertIn("#map-container svg", self.stylesheet)
        self.assertNotIn("#map-container svg { display: block; }", self.stylesheet)
        svg_rule = self.stylesheet.split("#map-container svg")[1].split("}")[0]
        self.assertIn("width: 100%", svg_rule)
        self.assertIn("height: auto", svg_rule)

    def test_stylesheet_styles_the_zoom_handles(self):
        self.assertIn(".atlas-map-zoom", self.stylesheet)
        self.assertIn(".atlas-map-zoom-btn", self.stylesheet)


class WasteAtlasZoomControlMarkupTests(TestCase):
    """Every choropleth map page ships the zoom handles inside the canvas."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="responsive-atlas-user", password="secret"
        )
        waste_atlas_group, _ = Group.objects.get_or_create(name="waste_atlas")
        cls.user.groups.add(waste_atlas_group)

    def _render_generic(self, config_key="orga_level"):
        from sources.waste_collection.waste_atlas.views import AtlasMapView

        request = RequestFactory().get("/")
        request.user = self.user
        page = {
            "region": "generic",
            "theme": "orga_level",
            "title": "Test map",
            "path": "map/test/",
            "name": "waste-atlas-test-map",
            "config_key": config_key,
            "selector_set": None,
            "country": "DE",
            "year": "2024",
            "lock": False,
        }
        return AtlasMapView.as_view(page=page)(request).render().content.decode("utf-8")

    def test_zoom_handles_are_rendered_inside_the_map_container(self):
        content = self._render_generic()

        self.assertIn('id="atlas-map-zoom"', content)
        self.assertIn('id="btn-map-zoom-in"', content)
        self.assertIn('id="btn-map-zoom-out"', content)
        self.assertIn('id="btn-map-zoom-reset"', content)
        self.assertIn('id="atlas-map-zoom-level"', content)

        container_markup = content.split('id="map-container"')[1].split(
            '<svg id="atlas-svg"'
        )[0]
        self.assertIn('id="atlas-map-zoom"', container_markup)

    def test_static_assets_carry_a_bumped_cache_buster(self):
        """Regression: the renderer changed behaviour but kept its ?v= marker.

        Browsers keep serving the cached stylesheet/script for an unchanged
        URL, so deployed readers would never receive the responsive canvas —
        and locally it looked like a fix simply had no effect.
        """
        template = SHELL_TEMPLATE.read_text()
        versions = re.findall(
            r"\.min\.(?:css|js)' %\}\?v=([\w-]+)",
            template,
        )

        self.assertEqual(len(versions), 2, "both the CSS and the JS need a ?v=")
        self.assertEqual(len(set(versions)), 1, "both assets should share one ?v=")
        self.assertNotEqual(
            versions[0],
            "20260724-2",
            "bump the cache buster when the atlas CSS/JS behaviour changes",
        )

    def test_zoom_handles_are_labelled_for_assistive_technology(self):
        content = self._render_generic()

        self.assertIn('aria-label="Zoom in"', content)
        self.assertIn('aria-label="Zoom out"', content)
        self.assertIn('aria-label="Reset zoom"', content)
