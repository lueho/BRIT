"""Per-map controls live in one tabbed panel, not scattered around the map.

The map page used to spread controls over four places: navigation buttons in the
context header, zoom on the canvas, option toggles in a bare div hanging below
the panel, and export buttons below a canvas taller than the viewport. They now
share the right-hand panel, using the same ``sidebar-tabs`` pattern as
``maps/templates/filtered_map.html`` so the atlas matches the rest of BRIT.
"""

from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

WASTE_ATLAS_DIR = Path(__file__).resolve().parents[1] / "waste_atlas"
CHOROPLETH_SCRIPT = WASTE_ATLAS_DIR / "static" / "js" / "waste_atlas_choropleth.js"
ATLAS_STYLESHEET = WASTE_ATLAS_DIR / "static" / "css" / "waste_atlas.css"

MAP_ROUTE = "waste-atlas-germany-collection-system-map"


class MapPageChromeTests(TestCase):
    """Everything but the map is reachable from one panel, without scrolling."""

    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name="waste_atlas")
        cls.user = User.objects.create_user(username="layout-user", password="secret")
        cls.user.groups.add(group)
        cls.staff = User.objects.create_user(
            username="layout-staff", password="secret", is_staff=True
        )
        cls.staff.groups.add(group)

    def setUp(self):
        self.client.force_login(self.user)

    def _content(self):
        response = self.client.get(reverse(MAP_ROUTE))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _section(self, content, start, end):
        return content.split(start)[1].split(end)[0]

    # ---- context header ---------------------------------------------------

    def test_header_holds_the_title_and_nothing_else(self):
        content = self._content()
        header = self._section(content, '<header class="atlas-context"', "</header>")

        self.assertIn("atlas-context-title", header)
        self.assertNotIn("atlas-context-actions", header)
        self.assertNotIn("<button", header)
        self.assertNotIn("btn", header)

    def test_header_does_not_repeat_the_breadcrumb_location(self):
        """The breadcrumb rail above already names the region."""
        content = self._content()
        header = self._section(content, '<header class="atlas-context"', "</header>")

        self.assertNotIn("atlas-eyebrow", header)

    def test_no_controls_are_buried_below_the_canvas(self):
        content = self._content()

        self.assertNotIn('id="export-buttons"', content)
        canvas_end = content.index("</svg>")
        panel_start = content.index('id="atlas-side"')
        self.assertLess(canvas_end, panel_start)
        self.assertNotIn("<button", content[canvas_end:panel_start])

    # ---- panel ------------------------------------------------------------

    def test_panel_uses_the_shared_sidebar_tabs_pattern(self):
        content = self._content()

        self.assertIn("sidebar-tabs", content)
        self.assertIn('data-bs-toggle="tab"', content)
        for element_id in (
            "atlas-map-tab",
            "atlas-options-tab",
            "atlas-map-pane",
            "atlas-options-pane",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', content)

    def test_panel_has_exactly_two_tabs(self):
        content = self._content()
        tabs = self._section(content, 'id="atlas-panel-tabs"', "</ul>")

        self.assertEqual(tabs.count('data-bs-toggle="tab"'), 2)

    def test_map_tab_holds_the_selector_the_view_switch_and_the_map_toggles(self):
        content = self._content()
        pane = self._section(content, 'id="atlas-map-pane"', 'id="atlas-options-pane"')

        self.assertIn("atlas-selector-form", pane)
        self.assertIn("atlas-mode-toggle", pane)
        # The renderer mounts quartile/conflict toggles here; they belong in the
        # Map pane so they are visible without switching to Options.
        self.assertIn('id="atlas-map-tools"', pane)

    def test_map_pane_wraps_display_toggles_in_a_side_group(self):
        """The quartile/conflict toggles sit in a titled group like View."""
        content = self._content()
        pane = self._section(content, 'id="atlas-map-pane"', 'id="atlas-options-pane"')
        tools_pos = pane.index('id="atlas-map-tools"')
        group_pos = pane.rfind("atlas-side-group", 0, tools_pos)
        self.assertGreater(tools_pos, group_pos)
        title_pos = pane.rfind("atlas-side-group-title", 0, tools_pos)
        self.assertGreater(tools_pos, title_pos)

    def test_options_pane_groups_actions_under_side_group_titles(self):
        """Export and administration actions each carry a group title."""
        self.client.force_login(self.staff)
        content = self._content()
        pane = self._section(
            content, 'id="atlas-options-pane"', "</div>\n        </div>"
        )
        self.assertIn("atlas-side-group", pane)
        self.assertGreaterEqual(pane.count("atlas-side-group-title"), 2)

    def test_options_tab_holds_the_export_trigger_and_config_link(self):
        content = self._content()
        pane = self._section(
            content, 'id="atlas-options-pane"', "</div>\n        </div>"
        )

        self.assertNotIn('id="atlas-map-tools"', pane)
        self.assertIn('data-bs-target="#atlas-export-modal"', pane)

    def test_export_trigger_uses_side_link_styling(self):
        """The export button matches the side-link style, not a Bootstrap button."""
        content = self._content()
        pane = self._section(
            content, 'id="atlas-options-pane"', "</div>\n        </div>"
        )
        self.assertIn("atlas-side-link", pane)
        self.assertNotIn("btn-outline-secondary", pane)
        self.assertNotIn("atlas-side-action", pane)

    # ---- export modal -----------------------------------------------------

    def test_export_opens_a_modal_offering_each_format(self):
        content = self._content()

        self.assertIn('id="atlas-export-modal"', content)
        modal = self._section(content, 'id="atlas-export-modal"', "</div>\n</div>")
        self.assertIn('id="btn-export-svg"', modal)
        self.assertIn('id="btn-export-png"', modal)

    def test_export_labels_are_short_with_descriptive_tooltips(self):
        content = self._content()

        self.assertIn("PNG (300 DPI)", content)
        self.assertNotIn("Download PNG (Word-ready, 300 DPI)", content)
        self.assertIn('title="Download a PNG at 300 DPI, ready for Word"', content)
        self.assertIn('title="Download a vector SVG"', content)

    # ---- shell toolbar (removed) -----------------------------------------

    def test_toolbar_drops_the_brand_the_breadcrumb_already_shows(self):
        content = self._content()

        self.assertNotIn("atlas-shell-brand", content)
        self.assertIn("page-breadcrumb-rail", content)

    def test_shell_has_no_toolbar_card_or_tools_dropdown(self):
        """The empty toolbar card and the Tools dropdown are gone."""
        content = self._content()

        self.assertNotIn("atlas-shell-toolbar", content)
        self.assertNotIn("atlas-shell-toolbar-actions", content)
        self.assertNotIn("atlas-hero-tools", content)
        self.assertNotIn('id="atlas-tools-menu"', content)
        # The atlas shell no longer carries its own feedback button; the
        # core sidebar still renders the shared "Contact / Feedback" link.
        shell = self._section(content, 'id="atlas-shell"', "</main>")
        self.assertNotIn("atlas-feedback-link", shell)
        self.assertNotIn("Waste%20Atlas%20feedback", shell)

    def test_mobile_maps_toggle_survives_outside_the_toolbar(self):
        """The tree toggle moves to the workspace but keeps its wiring id."""
        content = self._content()

        self.assertIn('id="atlas-tree-toggle"', content)
        self.assertIn('aria-controls="atlas-tree"', content)

    def test_edit_configuration_lives_in_the_options_pane_for_staff(self):
        self.client.force_login(self.staff)
        content = self._content()

        header = self._section(content, '<header class="atlas-context"', "</header>")
        self.assertNotIn("Edit configuration", header)
        pane = self._section(
            content, 'id="atlas-options-pane"', "</div>\n        </div>"
        )
        self.assertIn("Edit configuration", pane)
        self.assertIn("/configurations/", pane)

    def test_non_staff_see_no_configuration_entry(self):
        content = self._content()

        self.assertNotIn("Edit configuration", content)


class MapPageChromeAssetTests(SimpleTestCase):
    """The stylesheet and renderer follow the panel restructure."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = CHOROPLETH_SCRIPT.read_text()
        cls.stylesheet = ATLAS_STYLESHEET.read_text()

    def test_orphaned_toolbar_styles_are_gone(self):
        for selector in (
            ".atlas-shell-brand",
            ".atlas-shell-toolbar",
            ".atlas-shell-toolbar-actions",
            ".atlas-feedback-link",
            ".atlas-hero-link",
            ".atlas-hero-tools",
        ):
            with self.subTest(selector=selector):
                self.assertNotIn(selector, self.stylesheet)

    def test_toggles_are_flattened_inside_the_panel(self):
        """The toggle bar carries its own frame; nested boxes look wrong."""
        self.assertIn(".atlas-side .atlas-map-toggles", self.stylesheet)

    def test_export_actions_are_laid_out_for_the_modal(self):
        self.assertIn(".atlas-export-actions", self.stylesheet)

    def test_side_action_class_is_gone(self):
        """The Bootstrap button wrapper is replaced by atlas-side-link."""
        self.assertNotIn(".atlas-side-action", self.stylesheet)

    def test_side_link_resets_button_styles(self):
        """A <button> styled as side-link must shed Bootstrap button chrome."""
        self.assertIn("button.atlas-side-link", self.stylesheet)

    def test_first_side_group_drops_the_top_divider(self):
        """The first group in a pane needs no separator border."""
        self.assertIn(".atlas-side-group:first-child", self.stylesheet)

    def test_conflict_toggle_is_not_red(self):
        """The conflict label uses the same ink colour as the other toggles."""
        self.assertNotIn("atlas-map-toggle--conflict", self.stylesheet)

    def test_empty_display_group_is_hidden(self):
        """The Display group collapses when no toggles are mounted into it."""
        self.assertIn(".atlas-side-group:has(#atlas-map-tools:empty)", self.stylesheet)

    def test_renderer_no_longer_adds_conflict_color_class(self):
        """The conflict toggle drops the red modifier class."""
        self.assertNotIn("atlas-map-toggle--conflict", self.script)

    def test_renderer_no_longer_reveals_a_separate_options_card(self):
        """Export lives in the Options tab, so the tab is always present."""
        self.assertNotIn("atlas-map-options", self.script)

    def test_legacy_europe_pages_keep_their_own_export_row(self):
        """karte0/karte41 have short canvases and no controls panel."""
        self.assertIn("#export-buttons", self.stylesheet)


class CatchmentFocusRingTests(SimpleTestCase):
    """Clicking a catchment must not leave a rectangle over the map.

    Catchment paths carry ``tabindex`` so they can be reached by keyboard, and a
    user-agent focus ring on an SVG path is drawn around its *bounding box*
    rather than its outline, which shows up as a stray rectangle.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stylesheet = ATLAS_STYLESHEET.read_text()

    def test_pointer_focus_draws_no_bounding_box_ring(self):
        self.assertIn("#atlas-svg .layer-catchments path:focus {", self.stylesheet)
        rule = self.stylesheet.split("#atlas-svg .layer-catchments path:focus {")[1]
        self.assertIn("outline: none", rule.split("}")[0])

    def test_keyboard_focus_keeps_a_visible_indicator(self):
        """Suppressing the ring must not leave keyboard users guessing."""
        self.assertIn(
            "#atlas-svg .layer-catchments path:focus-visible {", self.stylesheet
        )
        rule = self.stylesheet.split(
            "#atlas-svg .layer-catchments path:focus-visible {"
        )[1].split("}")[0]
        # A stroke follows the catchment outline; an outline would box it again.
        self.assertIn("stroke", rule)
        self.assertIn("outline: none", rule)
