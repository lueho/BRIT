"""Browser contract for effective-dated Waste Atlas catchment boundaries."""

from pathlib import Path

from django.test import SimpleTestCase

CHOROPLETH_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "waste_atlas"
    / "static"
    / "js"
    / "waste_atlas_choropleth.js"
)


class WasteAtlasTemporalBoundaryScriptTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = CHOROPLETH_SCRIPT.read_text()

    def test_change_maps_request_server_side_temporal_overlay_geometry(self):
        self.assertIn("function _changeCatchmentUrl(", self.script)
        self.assertIn("collection-change-geojson", self.script)
        self.assertIn("collector-change-geojson", self.script)
        self.assertIn("'&from_year=' + cfg.fromYear", self.script)
        self.assertIn("'&to_year=' + cfg.year", self.script)

    def test_change_classification_is_keyed_by_overlay_feature_provenance(self):
        self.assertIn(
            "function _changeRecords(cfg, fromRaw, toRaw, changeFeatures)",
            self.script,
        )
        self.assertIn("properties.from_catchment_id", self.script)
        self.assertIn("properties.to_catchment_id", self.script)
        self.assertIn("properties.spatial_change", self.script)
        self.assertRegex(
            self.script,
            r"_changeRecords\([\s\S]*data\.catchments\.features\s*\)",
        )

    def test_transferred_territory_has_an_explicit_legend_category(self):
        self.assertIn("value: 'boundary_changed'", self.script)
        self.assertIn("label: 'Catchment reassigned'", self.script)
