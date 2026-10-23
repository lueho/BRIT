"""DOM bindings for middle-click "open in new tab" on Waste Atlas catchments.

The functions themselves (``_suppressAutoscroll``, ``_openCollectionInNewTab``,
``_openCollectionChoice``) are covered behaviorally by
``waste_atlas_choropleth.new_tab.test.mjs``. The assertions here pin the
*bindings* unit tests cannot reach: which d3 event handler calls them.
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


class MiddleClickBindingsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = CHOROPLETH_SCRIPT.read_text()

    def test_autoscroll_suppression_is_bound_to_mousedown(self):
        """Suppression must happen on mousedown — that is where the browser
        decides to start autoscroll."""
        self.assertIn("_suppressAutoscroll", self.script)
        bound = [
            line for line in self.script.splitlines() if "_suppressAutoscroll" in line
        ]
        self.assertTrue(
            any("mousedown" in line and ".on(" in line for line in bound),
            "_suppressAutoscroll must be bound via .on('mousedown...')",
        )

    def test_auxclick_routes_single_and_multi_collection_catchments(self):
        """The auxclick handler gates on the middle button, suppresses the
        default, and offers the collection picker when there is no single
        destination."""
        aux = self.script.split(".on('auxclick'", 1)[1]
        aux = aux.split("\n          })", 1)[0]
        self.assertIn("event.button !== 1", aux)
        self.assertIn("preventDefault()", aux)
        self.assertIn("_openCollectionInNewTab", aux)
        self.assertIn("_openCollectionChoice", aux)

    def test_zoom_behaviour_ignores_non_primary_buttons(self):
        """A middle click must not start a pan gesture."""
        zoom_filter = self.script.split("function _setupZoom(")[1]
        zoom_filter = zoom_filter.split("_zoomTarget")[1]
        self.assertIn("!event.button", zoom_filter)
