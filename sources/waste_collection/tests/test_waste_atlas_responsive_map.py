"""Responsive sizing and manual zoom for the Waste Atlas choropleth maps.

The renderer used to bake ``container.clientWidth`` and a fixed 1.17 aspect
ratio into the SVG once, so the map neither followed the canvas width when the
window changed nor offered any manual sizing.
"""

from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import RequestFactory, TestCase

WASTE_ATLAS_DIR = Path(__file__).resolve().parents[1] / "waste_atlas"
CHOROPLETH_SCRIPT = WASTE_ATLAS_DIR / "static" / "js" / "waste_atlas_choropleth.js"
ATLAS_STYLESHEET = WASTE_ATLAS_DIR / "static" / "css" / "waste_atlas.css"


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

    def test_zoom_handles_are_labelled_for_assistive_technology(self):
        content = self._render_generic()

        self.assertIn('aria-label="Zoom in"', content)
        self.assertIn('aria-label="Zoom out"', content)
        self.assertIn('aria-label="Reset zoom"', content)
