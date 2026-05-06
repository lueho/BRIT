from pathlib import Path

from cookie_consent.models import Cookie, CookieGroup
from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from brit.sitemap_items import SITEMAP_ITEMS


class SitemapItemsTestCase(SimpleTestCase):
    def test_sources_explorer_is_canonical_sitemap_entry(self):
        self.assertIn("/sources/explorer/", SITEMAP_ITEMS)
        self.assertNotIn("/sources/list/", SITEMAP_ITEMS)

    def test_source_plugin_sitemap_entries_are_composed_dynamically(self):
        self.assertIn("/maps/nantes/greenhouses/export/", SITEMAP_ITEMS)
        self.assertIn("/waste_collection/collections/", SITEMAP_ITEMS)

    def test_stale_nantes_roadside_tree_sitemap_entries_are_absent(self):
        self.assertNotIn("/maps/nantes/roadside_trees/export/", SITEMAP_ITEMS)
        self.assertNotIn("/case_studies/nantes/roadside_trees/export/", SITEMAP_ITEMS)


class CookieConsentTemplateHardeningTests(TestCase):
    """Regression tests for cookie-consent template compatibility and behavior."""

    def setUp(self):
        self.factory = RequestFactory()
        self.cookie_group = CookieGroup.objects.create(
            varname="analytics",
            name="Analytics",
            description="Analytics cookies",
            is_required=False,
        )
        Cookie.objects.create(
            cookiegroup=self.cookie_group,
            name="_ga",
            description="Google Analytics",
            domain="example.org",
        )

    def _render_cookie_group_partial(self):
        request = self.factory.get("/cookies/")
        return render_to_string(
            "cookie_consent/_cookie_group.html",
            {"request": request, "cookie_group": self.cookie_group},
        )

    @override_settings(ROOT_URLCONF="brit.tests.urls_cookie_consent_witharg")
    def test_cookie_group_actions_use_varname_urls_when_available(self):
        """Template uses varname route when that signature exists."""
        html = self._render_cookie_group_partial()

        self.assertIn('action="/accept/analytics/"', html)
        self.assertIn('action="/decline/analytics/"', html)

    @override_settings(ROOT_URLCONF="brit.tests.urls_cookie_consent_noarg")
    def test_cookie_group_actions_fallback_to_noarg_urls(self):
        """Template falls back to no-arg routes when varname route is unavailable."""
        html = self._render_cookie_group_partial()

        self.assertIn('action="/accept/"', html)
        self.assertIn('action="/decline/"', html)
        self.assertIn('name="cookie_groups" value="analytics"', html)

    def test_cookie_group_list_view_renders_successfully(self):
        """The /cookies/ page renders without reverse errors."""
        response = self.client.get(reverse("cookie_consent_cookie_group_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'action="/cookies/accept/"', html=False)
        self.assertContains(response, 'action="/cookies/decline/"', html=False)
        self.assertContains(
            response, 'name="cookie_groups" value="analytics"', html=False
        )

    @override_settings(COOKIE_CONSENT_ENABLED=True)
    def test_cookie_bar_uses_module_api_not_legacy_script(self):
        """Cookie bar template renders module-based API usage."""
        request = self.factory.get("/")

        html = render_to_string("partials/_cookie_bar.html", {"request": request})

        self.assertIn("cookiebar.module.js", html)
        self.assertIn("showCookieBar({", html)
        self.assertNotIn("legacyShowCookieBar", html)
        self.assertNotIn("cookiebar.js", html)


class BreadcrumbModuleLandingTests(TestCase):
    def test_bibliography_explorer_uses_module_label_in_title_and_breadcrumb(self):
        response = self.client.get(reverse("bibliography-explorer"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BRIT | Bibliography")
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Bibliography</li>',
            html=True,
        )
        self.assertNotContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Bibliography Explorer</li>',
            html=True,
        )

    def test_waste_collection_explorer_uses_sources_module_parent(self):
        response = self.client.get(reverse("wastecollection-explorer"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BRIT | Waste Collection")
        self.assertContains(
            response,
            f'<a href="{reverse("sources-explorer")}">Sources</a>',
            html=True,
        )
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Waste Collection</li>',
            html=True,
        )
        self.assertNotContains(
            response,
            f'<a href="{reverse("sources-explorer")}">Sources Explorer</a>',
            html=True,
        )

    def test_utils_dashboard_uses_utilities_label(self):
        response = self.client.get(reverse("utils-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BRIT | Utilities")
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Utilities</li>',
            html=True,
        )
        self.assertContains(response, '<h5 class="mb-0">Utilities</h5>', html=True)


class BreadcrumbStaticPageTests(TestCase):
    def test_home_page_renders_default_title_without_extra_breadcrumb(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BRIT | Bioresource Information Tool")

    def test_home_page_suppresses_breadcrumb_rail(self):
        """Home page deliberately suppresses the sticky breadcrumb rail."""
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "page-breadcrumb-rail")

    def test_home_page_displays_full_name_in_intro_card(self):
        """Introduction card header shows full name, not just 'Introduction'."""
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<h5 class="mb-0">Bioresource Information Tool</h5>',
            html=True,
        )
        self.assertNotContains(
            response,
            '<h5 class="mb-0">Introduction</h5>',
            html=True,
        )

    def test_about_page_uses_breadcrumb_contract(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BRIT | About")
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">About</li>',
            html=True,
        )

    def test_learning_page_uses_breadcrumb_contract(self):
        response = self.client.get(reverse("learning"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BRIT | Learning")
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Learning</li>',
            html=True,
        )

    def test_privacy_policy_uses_human_breadcrumb_label(self):
        response = self.client.get(reverse("privacypolicy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BRIT | Privacy Policy")
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Privacy Policy</li>',
            html=True,
        )
        self.assertNotContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Privacypolicy</li>',
            html=True,
        )


class BreadcrumbNestedSourcesDomainTests(TestCase):
    """Regression tests for the nested Sources > Waste Collection breadcrumb path.

    Ensures source-domain plugins surface ``BRIT > Sources > Waste Collection > ...``
    instead of the flat ``BRIT > Waste Collection > ...``, so the nested hierarchy
    stays consistent across landing, list, and detail pages.
    """

    @classmethod
    def setUpTestData(cls):
        from sources.waste_collection.models import Collection, CollectionCatchment

        cls.collection = Collection.objects.create(
            name="Phase 3 Test Collection",
            catchment=CollectionCatchment.objects.create(name="Phase 3 Test Catchment"),
            publication_status="published",
        )

    def test_collection_list_renders_nested_sources_crumb(self):
        response = self.client.get(reverse("collection-list"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("sources-explorer")}">Sources</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{reverse("wastecollection-explorer")}">Waste Collection</a>',
            html=True,
        )
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Collections</li>',
            html=True,
        )

    def test_collection_detail_renders_full_nested_path(self):
        response = self.client.get(
            reverse("collection-detail", kwargs={"pk": self.collection.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("sources-explorer")}">Sources</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{reverse("wastecollection-explorer")}">Waste Collection</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<li aria-current="page" class="breadcrumb-item active">'
            f"{self.collection.get_breadcrumb_object_label()}</li>",
            html=True,
        )

    def test_greenhouses_plugin_list_renders_sources_parent_crumb(self):
        """Plugin-mounted source-domain lists also nest under Sources."""
        response = self.client.get(reverse("culture-list"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("sources-explorer")}">Sources</a>',
            html=True,
        )
        # No dashboard exists for the greenhouses plugin yet, so the module
        # crumb is rendered as plain text (not linked) but still visible.
        self.assertContains(response, "Greenhouses")

    def test_greenhouses_plugin_second_entity_list_renders_parent_crumb(self):
        """A second entity type in the same plugin surfaces the same parent."""
        response = self.client.get(reverse("greenhouse-list"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("sources-explorer")}">Sources</a>',
            html=True,
        )
        self.assertContains(response, "Greenhouses")

    def test_greenhouses_plugin_detail_renders_full_nested_path(self):
        """Plugin-mounted detail pages surface the full Sources > <Plugin> path."""
        from sources.greenhouses.models import Culture

        culture = Culture.objects.create(
            name="Phase5 Test Culture",
            publication_status="published",
        )
        response = self.client.get(reverse("culture-detail", kwargs={"pk": culture.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("sources-explorer")}">Sources</a>',
            html=True,
        )
        self.assertContains(response, "Greenhouses")
        self.assertContains(
            response,
            f'<li aria-current="page" class="breadcrumb-item active">'
            f"{culture.get_breadcrumb_object_label()}</li>",
            html=True,
        )

    def test_collection_create_form_renders_nested_parent_crumb(self):
        """Create forms under a nested source-domain parent expose the full path."""
        from utils.object_management.models import User

        staff = User.objects.create(username="phase5_staff", is_staff=True)
        self.client.force_login(staff)

        response = self.client.get(reverse("collection-create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("sources-explorer")}">Sources</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{reverse("wastecollection-explorer")}">Waste Collection</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{reverse("collection-list")}">Collections</a>',
            html=True,
        )
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Create</li>',
            html=True,
        )

    def test_collection_update_form_renders_nested_parent_crumb(self):
        """Update forms expose the full nested path down to the current object."""
        from utils.object_management.models import User

        staff = User.objects.create(username="phase5_staff_update", is_staff=True)
        self.client.force_login(staff)

        response = self.client.get(
            reverse("collection-update", kwargs={"pk": self.collection.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("sources-explorer")}">Sources</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{reverse("wastecollection-explorer")}">Waste Collection</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{reverse("collection-list")}">Collections</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{self.collection.detail_url}">'
            f"{self.collection.get_breadcrumb_object_label()}</a>",
            html=True,
        )
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Update</li>',
            html=True,
        )


class SampleDetailV2BreadcrumbHarmonizationTests(TestCase):
    """Regression tests for the Phase 3 closeout of ``sample_detail_v2.html``.

    The custom sample-detail v2 experience used to suppress the shared
    sticky breadcrumb rail and render its own ``sdv2-crumbs`` breadcrumb
    trail. Phase 3 harmonizes it so the template now participates in the
    shared breadcrumb contract: ``BRIT > Materials > Samples > <Sample>``
    is rendered by the shared rail, and the custom rail keeps only the
    sample-specific action controls.
    """

    @classmethod
    def setUpTestData(cls):
        from materials.models import Material, Sample

        cls.material = Material.objects.create(
            name="Phase 3 Close Out Material",
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            name="Phase 3 Close Out Sample",
            material=cls.material,
            publication_status="published",
        )

    def test_v2_renders_shared_breadcrumb_rail(self):
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk}) + "?experience=v2"
        )

        self.assertEqual(response.status_code, 200)
        # Shared sticky rail is now present.
        self.assertContains(response, 'class="page-breadcrumb-rail"')
        # Module and section crumbs are linked through the contract.
        self.assertContains(
            response,
            f'<a href="{reverse("materials-explorer")}">Materials</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{reverse("sample-list")}">Samples</a>',
            html=True,
        )
        # The sample itself is the active crumb.
        self.assertContains(
            response,
            f'<li aria-current="page" class="breadcrumb-item active">'
            f"{self.sample.get_breadcrumb_object_label()}</li>",
            html=True,
        )

    def test_v2_drops_duplicate_sdv2_crumbs_block(self):
        """The legacy custom breadcrumb trail must no longer render."""
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk}) + "?experience=v2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="sdv2-crumbs"')
        self.assertNotContains(response, "sdv2-crumb-current")

    def test_v2_preserves_sample_action_rail(self):
        """The sample-specific action rail (status pill, mode toggle,
        palette, classic-view link) must remain intact."""
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk}) + "?experience=v2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sdv2-rail"')
        self.assertContains(response, "sdv2-rail-actions")
        self.assertContains(response, "sdv2-status-pill")
        self.assertContains(response, "sdv2-mode-toggle")
        self.assertContains(response, "sdv2-classic-link")


class BreadcrumbContractFallbackPrecedenceTests(SimpleTestCase):
    """Regression tests for the precedence between contract slots and
    the legacy ``object``/``header``/``title``/``breadcrumb_page_title``
    fallback chain in ``base.html``.

    The fallback chain is retained as a safety net for pages that do not
    yet adopt the shared contract. Once any contract slot is populated,
    the fallback chain must be skipped entirely so weak labels such as a
    route-name-derived ``title`` cannot leak into the rail.
    """

    def _render_base_breadcrumbs(self, context):
        from django.template import Context, Template

        template = Template(
            '{% extends "base.html" %}{% block content %}{% endblock %}'
        )
        return template.render(Context(context))

    def _extract_breadcrumb_rail(self, html):
        """Slice out the breadcrumb rail so negative assertions don't
        accidentally catch the browser ``<title>`` or navbar labels."""
        start_marker = '<ol class="breadcrumb page-breadcrumbs mb-0">'
        end_marker = "</ol>"
        start = html.index(start_marker)
        end = html.index(end_marker, start) + len(end_marker)
        return html[start:end]

    def test_contract_module_label_wins_over_legacy_title_fallback(self):
        rail = self._extract_breadcrumb_rail(
            self._render_base_breadcrumbs(
                {
                    "breadcrumb_module_label": "Bibliography",
                    "breadcrumb_module_url": "/bibliography/",
                    "title": "Should Not Appear In Breadcrumb",
                }
            )
        )

        self.assertInHTML(
            '<li class="breadcrumb-item active" aria-current="page">Bibliography</li>',
            rail,
        )
        self.assertNotIn("Should Not Appear In Breadcrumb", rail)

    def test_contract_action_label_wins_over_legacy_header_fallback(self):
        rail = self._extract_breadcrumb_rail(
            self._render_base_breadcrumbs(
                {
                    "breadcrumb_module_label": "Bibliography",
                    "breadcrumb_section_label": "Authors",
                    "breadcrumb_action_label": "Create",
                    "header": "Legacy Header Should Not Leak",
                    "title": "Legacy Title Should Not Leak",
                }
            )
        )

        self.assertInHTML(
            '<li class="breadcrumb-item active" aria-current="page">Create</li>',
            rail,
        )
        self.assertNotIn("Legacy Header Should Not Leak", rail)
        self.assertNotIn("Legacy Title Should Not Leak", rail)

    def test_legacy_title_fallback_still_works_without_contract(self):
        """The safety-net fallback is intentionally preserved for pages
        that have not yet adopted the shared contract."""
        rail = self._extract_breadcrumb_rail(
            self._render_base_breadcrumbs({"title": "Legacy Page"})
        )

        self.assertInHTML(
            '<li class="breadcrumb-item active" aria-current="page">Legacy Page</li>',
            rail,
        )


class BreadcrumbNonNameDetailObjectTests(TestCase):
    """Regression tests for detail breadcrumbs on models without a `name` field.

    Shared detail pages must render the current-item crumb via
    ``object.get_breadcrumb_object_label()`` (which defaults to ``str(self)``
    on ``CRUDUrlsMixin``) rather than assuming ``object.name`` exists. The
    previous implementation coerced ``None`` into the breadcrumb for models
    like ``Author`` and ``Source`` whose display field is not ``name``.
    """

    @classmethod
    def setUpTestData(cls):
        from bibliography.models import Author

        cls.author = Author.objects.create(
            first_names="Ada",
            last_names="Lovelace",
            publication_status="published",
        )

    def test_author_detail_uses_str_based_breadcrumb_label(self):
        response = self.client.get(
            reverse("author-detail", kwargs={"pk": self.author.pk})
        )

        self.assertEqual(response.status_code, 200)
        expected_label = str(self.author)
        self.assertContains(
            response,
            f'<li aria-current="page" class="breadcrumb-item active">'
            f"{expected_label}</li>",
            html=True,
        )
        # And the module crumb (Bibliography) is present and linked.
        self.assertContains(
            response,
            f'<a href="{reverse("bibliography-explorer")}">Bibliography</a>',
            html=True,
        )
        # The detail rail must not leak the raw class name or an empty crumb.
        self.assertNotContains(response, "None</li>")


class ErrorPageBreadcrumbTests(SimpleTestCase):
    """Error pages should deliberately suppress the sticky breadcrumb rail.

    403/404/500 have their own centered error treatment and an in-content
    "← Back to Home" link, so the shared sticky rail adds no UX value and
    steals vertical space. Rendering any breadcrumb crumb on these pages
    must be intentional; by default the rail is suppressed.
    """

    def _render_error_template(self, template_name):
        return render_to_string(template_name)

    def test_403_template_suppresses_breadcrumb_rail(self):
        html = self._render_error_template("403.html")

        self.assertIn("BRIT | 403 - Forbidden", html)
        self.assertNotIn("page-breadcrumb-rail", html)

    def test_404_template_suppresses_breadcrumb_rail(self):
        html = self._render_error_template("404.html")

        self.assertIn("BRIT | 404 - Page Not Found", html)
        self.assertNotIn("page-breadcrumb-rail", html)

    def test_500_template_suppresses_breadcrumb_rail(self):
        html = self._render_error_template("500.html")

        self.assertIn("BRIT | 500 - Server Error", html)
        self.assertNotIn("page-breadcrumb-rail", html)

    def test_production_settings_do_not_propagate_500_exceptions(self):
        settings_path = Path(settings.BASE_DIR) / "brit" / "settings" / "heroku.py"

        self.assertNotIn(
            "DEBUG_PROPAGATE_EXCEPTIONS = True",
            settings_path.read_text(encoding="utf-8"),
        )


class StickyFilterOffsetAssetTests(SimpleTestCase):
    """Asset-level regression tests for the sticky sidebar/breadcrumb rail offset.

    Filter sidebars share the viewport with the sticky breadcrumb rail
    (`.page-breadcrumb-rail`, top: 56px, min-height: 3rem). Their sticky
    offset must account for both the topbar and the rail so they don't
    slide underneath the rail when scrolling.
    """

    def _read_asset(self, relative_path):
        base_dir = Path(settings.BASE_DIR) if hasattr(settings, "BASE_DIR") else None
        if base_dir is None:
            self.skipTest("settings.BASE_DIR is not configured")
        asset_path = base_dir / "brit" / "static" / relative_path
        self.assertTrue(
            asset_path.exists(),
            f"Expected static asset {asset_path} to exist",
        )
        return asset_path.read_text(encoding="utf-8")

    def test_filtered_list_css_defines_shared_sticky_offset_variables(self):
        css = self._read_asset("css/filtered-list.css")

        self.assertIn("--brit-topnav-height: 56px", css)
        self.assertIn("--brit-breadcrumb-rail-height: 3rem", css)
        self.assertIn(
            "--brit-sticky-offset: calc(var(--brit-topnav-height)"
            " + var(--brit-breadcrumb-rail-height) + 1rem)",
            css,
        )

    def test_filter_sticky_uses_shared_offset_and_not_topnav_alone(self):
        css = self._read_asset("css/filtered-list.css")

        self.assertIn("top: var(--brit-sticky-offset);", css)
        self.assertNotIn("top: calc(56px + 1rem);", css)

    def test_filtered_list_minified_css_mirrors_source(self):
        minified = self._read_asset("css/filtered-list.min.css")

        self.assertIn("--brit-sticky-offset:calc(var(--brit-topnav-height)", minified)
        self.assertIn(
            ".filter-sticky{position:sticky;top:var(--brit-sticky-offset)", minified
        )
        self.assertNotIn("top:calc(56px + 1rem)", minified)
