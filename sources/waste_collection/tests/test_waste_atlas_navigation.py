"""Tests for the Waste Atlas navigation template tags."""

from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings
from django.urls import include, path
from django.utils.safestring import SafeString

from sources.waste_collection.waste_atlas.templatetags.atlas_navigation import (
    atlas_shell_tree,
    atlas_theme_options,
)

# Doubles as a ROOT_URLCONF for the mounted-prefix regression test.
urlpatterns = [
    path("mounted/atlas/", include("sources.waste_collection.waste_atlas.urls")),
]


def _theme(value, **overrides):
    option = {
        "value": value,
        "theme_group": "amounts",
        "waste_category": "bio",
        "label": f"Label {value}",
        "url": f"/atlas/{value}/",
        "change_url": f"/atlas/change/{value}/",
    }
    option.update(overrides)
    return option


class AtlasThemeOptionsTagTests(SimpleTestCase):
    def test_renders_option_markup(self):
        themes = {
            "DE": [
                _theme("amount"),
                _theme("fees", theme_group="policy", change_url=""),
            ]
        }

        html = atlas_theme_options(themes, "DE", "amount")

        self.assertIsInstance(html, SafeString)
        self.assertHTMLEqual(
            html,
            '<option value="amount" data-map-set="DE" data-theme-group="amounts" '
            'data-waste-category="bio" '
            'data-search="label amount amount amounts" '
            'data-url="/atlas/amount/" '
            'data-change-url="/atlas/change/amount/" selected>'
            "Label amount</option>"
            '<option value="fees" data-map-set="DE" data-theme-group="policy" '
            'data-waste-category="bio" data-search="label fees fees policy" '
            'data-url="/atlas/fees/">Label fees</option>',
        )

    def test_only_matching_map_set_and_theme_is_selected(self):
        themes = {
            "DE": [_theme("amount")],
            "EU": [_theme("amount", url="/atlas/eu-amount/")],
        }

        html = atlas_theme_options(themes, "EU", "amount")

        self.assertHTMLEqual(
            html,
            '<option value="amount" data-map-set="DE" data-theme-group="amounts" '
            'data-waste-category="bio" '
            'data-search="label amount amount amounts" '
            'data-url="/atlas/amount/" '
            'data-change-url="/atlas/change/amount/">Label amount</option>'
            '<option value="amount" data-map-set="EU" data-theme-group="amounts" '
            'data-waste-category="bio" '
            'data-search="label amount amount amounts" '
            'data-url="/atlas/eu-amount/" '
            'data-change-url="/atlas/change/amount/" selected>'
            "Label amount</option>",
        )

    def test_empty_registry_renders_nothing(self):
        self.assertEqual(str(atlas_theme_options({}, "DE", "amount")), "")

    def test_escapes_labels_values_and_urls(self):
        themes = {
            'M"<x>': [
                _theme(
                    'v"<bad>',
                    theme_group="g&",
                    label='Label <b>&"q"',
                    url="/u/?a=1&b=<2>",
                    change_url='/c/?x="<y>"',
                )
            ]
        }

        html = str(atlas_theme_options(themes, "none", "none"))

        self.assertIn('data-map-set="M&quot;&lt;x&gt;"', html)
        self.assertIn('value="v&quot;&lt;bad&gt;"', html)
        self.assertIn('data-theme-group="g&amp;"', html)
        self.assertIn("Label &lt;b&gt;&amp;&quot;q&quot;", html)
        self.assertIn('data-url="/u/?a=1&amp;b=&lt;2&gt;"', html)
        self.assertIn('data-change-url="/c/?x=&quot;&lt;y&gt;&quot;"', html)
        self.assertNotIn("<bad>", html)
        self.assertNotIn("<b>", html)


def _groups():
    return [
        {
            "id": "europe",
            "label": "Europe",
            "europe_maps": [
                {"title": "Europe Coverage", "url": "/atlas/europe/coverage/"}
            ],
            "regions": [
                {
                    "value": "EU",
                    "label": "European Union",
                    "sections": [
                        {
                            "label": "Amounts",
                            "maps": [
                                {
                                    "title": "EU Amount",
                                    "url": "/atlas/eu/amount/",
                                    "theme": "amount",
                                },
                                {
                                    "title": "EU Fees",
                                    "url": "/atlas/eu/fees/",
                                    "theme": "fees",
                                },
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "id": "germany",
            "label": "Germany",
            "europe_maps": [],
            "regions": [
                {
                    "value": "DE",
                    "label": "Germany",
                    "sections": [
                        {
                            "label": "Amounts",
                            "maps": [
                                {
                                    "title": "DE Amount",
                                    "url": "/atlas/de/amount/",
                                    "theme": "amount",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    ]


class AtlasShellTreeTagTests(SimpleTestCase):
    def _tree(self, **context):
        base = {
            "directory_region_groups": _groups(),
            "atlas_tree_overview_active": False,
            "directory_selected_region": "germany",
            "atlas_map_set": "DE",
            "atlas_active_theme": "amount",
        }
        base.update(context)
        return atlas_shell_tree(base)

    def test_marks_only_matching_mapset_and_theme_active(self):
        html = self._tree()

        self.assertHTMLEqual(
            html,
            '<a class="atlas-tree-overview-link" '
            'href="/waste_collection/waste-atlas/map/">'
            '<i class="fas fa-th-list"></i> All maps</a>'
            '<details class="atlas-tree-region" data-region="europe">'
            '<summary class="atlas-tree-region-summary">Europe</summary>'
            '<div class="atlas-tree-section">'
            '<a class="atlas-tree-link" href="/atlas/europe/coverage/" '
            'data-search="europe coverage">Europe Coverage</a>'
            "</div>"
            '<div class="atlas-tree-region-block" data-map-set="EU">'
            '<div class="atlas-tree-region-title">European Union</div>'
            '<div class="atlas-tree-section">'
            '<div class="atlas-tree-section-title">Amounts</div>'
            '<a class="atlas-tree-link" href="/atlas/eu/amount/" '
            'data-search="eu amount european union amount">EU Amount</a>'
            '<a class="atlas-tree-link" href="/atlas/eu/fees/" '
            'data-search="eu fees european union fees">EU Fees</a>'
            "</div>"
            "</div>"
            "</details>"
            '<details class="atlas-tree-region" data-region="germany" open>'
            '<summary class="atlas-tree-region-summary">Germany</summary>'
            '<div class="atlas-tree-region-block" data-map-set="DE">'
            '<div class="atlas-tree-region-title">Germany</div>'
            '<div class="atlas-tree-section">'
            '<div class="atlas-tree-section-title">Amounts</div>'
            '<a class="atlas-tree-link atlas-tree-link--active" '
            'aria-current="page" href="/atlas/de/amount/" '
            'data-search="de amount germany amount">DE Amount</a>'
            "</div>"
            "</div>"
            "</details>",
        )

    def test_overview_active_marks_link_and_suppresses_open_regions(self):
        html = self._tree(
            atlas_tree_overview_active=True,
            directory_selected_region="germany",
            atlas_map_set=None,
            atlas_active_theme=None,
        )

        self.assertIn('class="atlas-tree-overview-link atlas-tree-link--active"', html)
        self.assertNotIn("open>", html)
        self.assertNotIn('atlas-tree-link--active" aria', html)

    def test_no_selection_renders_plain_tree(self):
        html = self._tree(
            directory_selected_region=None,
            atlas_map_set=None,
            atlas_active_theme=None,
        )

        self.assertNotIn("open>", html)
        self.assertNotIn("atlas-tree-link--active", html)
        self.assertNotIn("aria-current", html)

    def test_empty_tree_renders_only_overview_link(self):
        html = atlas_shell_tree({})
        self.assertIn("atlas-tree-overview-link", html)
        self.assertNotIn("<details", html)

    @override_settings(
        ROOT_URLCONF="sources.waste_collection.tests.test_waste_atlas_navigation"
    )
    def test_overview_link_follows_active_urlconf(self):
        html = str(atlas_shell_tree({}))
        self.assertIn('href="/mounted/atlas/map/"', html)

    def test_escapes_labels_titles_and_urls(self):
        groups = [
            {
                "id": 'g"<x>',
                "label": 'G<label>&"',
                "europe_maps": [
                    {"title": "E<e>", "url": '/e/?a=1&b="<2>"'},
                ],
                "regions": [
                    {
                        "value": 'R"<r>',
                        "label": 'R<label>&"',
                        "sections": [
                            {
                                "label": "S<label>",
                                "maps": [
                                    {
                                        "title": 'T<t>&"',
                                        "url": '/m/?x="<y>"',
                                        "theme": 'th"<t>',
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        html = str(atlas_shell_tree({"directory_region_groups": groups}))

        self.assertIn('data-region="g&quot;&lt;x&gt;"', html)
        self.assertIn("G&lt;label&gt;&amp;&quot;", html)
        self.assertIn("E&lt;e&gt;", html)
        self.assertIn('data-search="e&lt;e&gt;"', html)
        self.assertIn('href="/e/?a=1&amp;b=&quot;&lt;2&gt;&quot;"', html)
        self.assertIn('data-map-set="R&quot;&lt;r&gt;"', html)
        self.assertIn("S&lt;label&gt;", html)
        self.assertIn("T&lt;t&gt;&amp;&quot;", html)
        self.assertIn('href="/m/?x=&quot;&lt;y&gt;&quot;"', html)
        self.assertIn(
            'data-search="t&lt;t&gt;&amp;&quot; r&lt;label&gt;&amp;&quot; '
            'th&quot;&lt;t&gt;"',
            html,
        )
        self.assertNotIn("<label>", html)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "brit-atlas-navigation-tests",
        }
    }
)
class AtlasNavigationTemplateWiringTests(SimpleTestCase):
    """The include templates keep their cache blocks and delegate to the tags."""

    selector_context = {
        "map_selection_map_sets": [
            {
                "value": "DE",
                "label": "Germany",
                "country": "DE",
                "nuts_prefix": "DE",
                "nuts_level": "1",
                "selected": True,
            }
        ],
        "map_selection_waste_categories": {"bio": "Biowaste"},
        "map_selection_themes_by_map_set": {"DE": [_theme("amount")]},
        "map_selection_years": ["2024"],
        "selected_map_set": "DE",
        "selected_map_theme": "amount",
        "selected_waste_category": "bio",
        "atlas_urlconf": "brit.urls",
        "year": "2024",
        "default_from_year": "2023",
        "default_to_year": "2024",
    }

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def test_map_selector_renders_tag_output_inside_cache_block(self):
        html = render_to_string(
            "waste_atlas/includes/map_selector.html", self.selector_context
        )
        self.assertIn('data-map-set="DE"', html)
        self.assertIn('data-url="/atlas/amount/"', html)
        self.assertIn("Label amount", html)
        self.assertIn("selected", html)

    def test_change_map_selector_renders_tag_output_inside_cache_block(self):
        html = render_to_string(
            "waste_atlas/includes/change_map_selector.html",
            self.selector_context,
        )
        self.assertIn('data-map-set="DE"', html)
        self.assertIn('data-change-url="/atlas/change/amount/"', html)
        self.assertIn("Label amount", html)

    def test_shell_tree_renders_tag_output_inside_cache_block(self):
        context = {
            "directory_region_groups": _groups(),
            "atlas_tree_overview_active": False,
            "directory_selected_region": "germany",
            "atlas_map_set": "DE",
            "atlas_active_theme": "amount",
            "atlas_urlconf": "brit.urls",
        }
        html = render_to_string("waste_atlas/includes/shell_tree.html", context)
        self.assertIn("atlas-tree-overview-link", html)
        self.assertIn('data-region="germany" open', html.replace("\n", " "))
        self.assertIn("atlas-tree-link--active", html)
        self.assertIn('aria-current="page"', html)
        self.assertIn("Europe Coverage", html)
