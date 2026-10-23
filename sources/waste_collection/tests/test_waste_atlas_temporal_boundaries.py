"""Browser contract for effective-dated Waste Atlas catchment boundaries.

The change-geometry endpoints are covered behaviorally in ``test_viewsets.py``;
the assertions below pin the *wiring* on the browser side: in change mode the
choropleth script must request the change endpoints with both year parameters
and must feed the overlay features into the change classification, which keys
on the provenance fields the API returns.
"""

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

    def _function_body(self, name):
        body = self.script.split(f"function {name}(", 1)[1]
        return body.split("\n  }", 1)[0]

    def test_change_maps_request_server_side_temporal_overlay_geometry(self):
        url_builder = self._function_body("_changeCatchmentUrl")
        self.assertIn("collection-change-geojson", url_builder)
        self.assertIn("collector-change-geojson", url_builder)

        # In change mode, both years must be attached to the change URL in the
        # same expression — not merely present elsewhere in the script.
        catch_url = self.script.split("var catchUrl =", 1)[1].split(";", 1)[0]
        self.assertIn("cfg.changeMode", catch_url)
        self.assertIn("_changeCatchmentUrl(", catch_url)
        self.assertIn("from_year", catch_url)
        self.assertIn("to_year", catch_url)

    def test_change_classification_is_keyed_by_overlay_feature_provenance(self):
        call_args = self.script.split("thematicData: _changeRecords(", 1)[1].split(
            ")", 1
        )[0]
        self.assertIn("data.catchments.features", call_args)

        classifier = self._function_body("_spatialChangeRecords")
        self.assertIn("properties.from_catchment_id", classifier)
        self.assertIn("properties.to_catchment_id", classifier)
        self.assertIn("properties.spatial_change", classifier)
        self.assertIn("spatialChange === 'transferred'", classifier)
        self.assertIn("change = 'boundary_changed'", classifier)

    def test_transferred_territory_has_an_explicit_legend_category(self):
        legend_entries = [
            line
            for line in self.script.splitlines()
            if "value: 'boundary_changed'" in line
        ]
        self.assertTrue(legend_entries)
        for line in legend_entries:
            self.assertIn("label: 'Catchment reassigned'", line)
            self.assertIn("colors.boundaryChanged", line)
