from cookie_consent.models import Cookie, CookieGroup
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
