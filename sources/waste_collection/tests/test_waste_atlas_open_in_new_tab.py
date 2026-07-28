"""Middle-clicking a catchment opens its collection in a new tab.

The browser's default middle-click action is autoscroll, which is useless on a
map that pans by dragging, so the renderer suppresses it and treats the click
as "open in a new tab" instead.
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

MIDDLE_BUTTON = "event.button !== 1"


class MiddleClickOpensNewTabTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = CHOROPLETH_SCRIPT.read_text()

    def test_autoscroll_is_suppressed_on_the_canvas(self):
        """Autoscroll is the default action of the middle mousedown."""
        self.assertIn("function _suppressAutoscroll(", self.script)
        suppress = self.script.split("function _suppressAutoscroll(")[1]
        suppress = suppress.split("\n  }")[0]
        self.assertIn("button", suppress)
        self.assertIn("preventDefault()", suppress)

    def test_middle_click_opens_the_collection_in_a_new_tab(self):
        self.assertIn("'auxclick'", self.script)
        self.assertIn("function _openCollectionInNewTab(", self.script)
        opener = self.script.split("function _openCollectionInNewTab(")[1]
        opener = opener.split("\n  }")[0]
        self.assertIn("window.open(", opener)
        self.assertIn("'_blank'", opener)
        # Drop the opener reference so the new tab cannot reach back.
        self.assertIn("opener", opener)

    def test_left_click_still_navigates_in_the_same_tab(self):
        """The primary click must keep its existing behaviour."""
        self.assertIn("window.location.assign(detailUrl)", self.script)

    def test_middle_click_on_a_multi_collection_catchment_offers_the_choice(self):
        """There is no single destination, so the picker opens instead.

        Its entries are real anchors, so middle-clicking one of those opens a
        new tab through the browser's own handling.
        """
        aux = self.script.split("'auxclick'")[1].split("})")[0]
        self.assertIn("_openCollectionChoice", aux)

    def test_zoom_behaviour_ignores_non_primary_buttons(self):
        """A middle click must not start a pan gesture."""
        zoom_filter = self.script.split("function _setupZoom(")[1]
        zoom_filter = zoom_filter.split("_zoomTarget")[1]
        self.assertIn("!event.button", zoom_filter)
