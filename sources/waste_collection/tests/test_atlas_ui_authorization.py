"""Atlas HTML surface authorization.

The rendered map and change-map pages, their scope selector, maintainer
links and the coarse map-configuration views must all derive from the
shared policy context: public historical default for every actor,
active-only ``published`` on request, literal workspace and lifecycle
scopes for active users, administrator-only ``all`` and configuration
editing, and fail-closed unknown scopes that are preserved raw instead of
silently widening.
"""

import io
import json
import re
from copy import deepcopy

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from sources.waste_collection.models import Collection
from sources.waste_collection.tests.atlas_fixtures import (
    seed_atlas_map_configurations,
)
from sources.waste_collection.waste_atlas.models import (
    WasteAtlasMapConfiguration,
)
from utils.tests.testcases import ensure_test_default_owner


def _map_config(response):
    match = re.search(
        r'<script id="atlas-config" type="application/json">(.*?)</script>',
        response.content.decode(),
        re.S,
    )
    assert match, "no atlas-config JSON found in response"
    return json.loads(match.group(1))


class AtlasUiAuthorizationTests(TestCase):
    MAP_URL_NAME = "waste-atlas-germany-collection-system-map"

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        seed_atlas_map_configurations()
        cls._role_output = io.StringIO()
        call_command("sync_roles", "--apply", stdout=cls._role_output)

        cls.owner = User.objects.create_user("ui-owner")
        cls.admin = User.objects.create_user("ui-admin")
        cls.admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        cls.moderator = User.objects.create_user("ui-moderator")
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        cls.staff_only = User.objects.create_user("ui-staff", is_staff=True)
        cls.stranger = User.objects.create_user("ui-stranger")

    def _map_config(self, *args, **kwargs):
        response = self.client.get(*args, **kwargs)
        self.assertEqual(response.status_code, 200)
        return response, _map_config(response)

    def _map_page(self, **params):
        return self._map_config(reverse(self.MAP_URL_NAME), params)

    def _change_map(self, **params):
        return self._map_config(
            reverse(
                "waste-atlas-change-map",
                args=["DE", "collection_system"],
            ),
            params,
        )

    # -- default and explicit public scopes -------------------------------

    def test_anonymous_map_defaults_to_historical(self):
        _response, config = self._map_page()
        self.assertEqual(config["scope"], "historical")

    def test_owner_map_defaults_to_historical_not_workspace(self):
        self.client.force_login(self.owner)
        _response, config = self._map_page()
        self.assertEqual(config["scope"], "historical")

    def test_admin_map_defaults_to_historical_not_all(self):
        self.client.force_login(self.admin)
        _response, config = self._map_page()
        self.assertEqual(config["scope"], "historical")

    def test_staff_only_map_defaults_to_historical(self):
        self.client.force_login(self.staff_only)
        _response, config = self._map_page()
        self.assertEqual(config["scope"], "historical")

    def test_change_map_defaults_to_historical(self):
        _response, config = self._change_map()
        self.assertEqual(config["scope"], "historical")

    def test_explicit_published_scope_stays_active_only(self):
        _response, config = self._map_page(scope="published")
        self.assertEqual(config["scope"], "published")

    # -- selector options ---------------------------------------------------

    def test_owner_selector_offers_workspace_and_lifecycle_options(self):
        self.client.force_login(self.owner)
        response, _config = self._map_page()
        for option in (
            'value="private"',
            'value="owned"',
            'value="shared"',
            'value="review"',
            'value="declined"',
        ):
            self.assertContains(response, option)
        self.assertNotContains(response, 'value="all"')

    def test_admin_selector_offers_all(self):
        self.client.force_login(self.admin)
        response, _config = self._map_page()
        self.assertContains(response, 'value="all"')

    def test_staff_only_selector_offers_no_extra_options(self):
        # A Django staff flag alone adds nothing: the selector shows the
        # same workspace and lifecycle options as for any active user, but
        # never the administrator-only ``all`` scope.
        self.client.force_login(self.staff_only)
        response, _config = self._map_page()
        self.assertContains(response, 'value="private"')
        self.assertContains(response, 'value="review"')
        self.assertNotContains(response, 'value="all"')

    def test_anonymous_selector_is_not_rendered(self):
        response, _config = self._map_page()
        self.assertNotContains(response, 'id="sel-scope"')

    # -- maintainer surfaces -------------------------------------------------

    def test_moderator_gets_conflict_url_and_overview(self):
        self.client.force_login(self.moderator)
        _response, config = self._map_page()
        self.assertIn("conflictUrl", config)
        overview = self.client.get(reverse("waste-atlas-data-conflicts-overview"))
        self.assertEqual(overview.status_code, 200)

    def test_admin_gets_conflict_url_and_overview(self):
        self.client.force_login(self.admin)
        _response, config = self._map_page()
        self.assertIn("conflictUrl", config)
        overview = self.client.get(reverse("waste-atlas-data-conflicts-overview"))
        self.assertEqual(overview.status_code, 200)

    def test_staff_only_gets_no_conflict_surface(self):
        self.client.force_login(self.staff_only)
        _response, config = self._map_page()
        self.assertNotIn("conflictUrl", config)
        self.assertEqual(
            self.client.get(reverse("waste-atlas-data-conflicts-overview")).status_code,
            403,
        )

    def test_stranger_gets_no_conflict_surface(self):
        self.client.force_login(self.stranger)
        _response, config = self._map_page()
        self.assertNotIn("conflictUrl", config)

    # -- configuration views --------------------------------------------------

    def _config_url(self):
        return reverse(
            "waste-atlas-map-configuration-update",
            args=["collection_system"],
        )

    def test_admin_can_open_and_edit_configuration(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self._config_url()).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("waste-atlas-map-configuration-list")).status_code,
            200,
        )
        response, _config = self._map_page()
        self.assertContains(response, "Edit configuration")

    def test_moderator_cannot_open_or_post_configuration(self):
        self.client.force_login(self.moderator)
        url = self._config_url()
        self.assertEqual(self.client.get(url).status_code, 403)
        snapshot = deepcopy(
            WasteAtlasMapConfiguration.objects.get(
                key="collection_system"
            ).configuration
        )
        response = self.client.post(url, {"legend_title": "tampered"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            WasteAtlasMapConfiguration.objects.get(
                key="collection_system"
            ).configuration,
            snapshot,
        )

    def test_staff_only_cannot_open_or_post_configuration(self):
        self.client.force_login(self.staff_only)
        url = self._config_url()
        self.assertEqual(self.client.get(url).status_code, 403)
        snapshot = deepcopy(
            WasteAtlasMapConfiguration.objects.get(
                key="collection_system"
            ).configuration
        )
        response = self.client.post(url, {"legend_title": "tampered"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            WasteAtlasMapConfiguration.objects.get(
                key="collection_system"
            ).configuration,
            snapshot,
        )
        response, _config = self._map_page()
        self.assertNotContains(response, "Edit configuration")

    # -- unknown and legacy scopes --------------------------------------------

    def test_unknown_scope_is_preserved_and_disabled_for_active_user(self):
        self.client.force_login(self.owner)
        response, config = self._map_page(scope="bogus")
        self.assertEqual(config["scope"], "bogus")
        self.assertContains(response, "Unavailable scope")
        self.assertContains(response, 'value="bogus"')

    def test_unknown_scope_returns_empty_rows_for_active_user(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            "/waste_collection/waste-atlas/api/collection-system/",
            {"country": "DE", "year": 2024, "scope": "bogus"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_anonymous_unknown_scope_is_preserved_without_option(self):
        response, config = self._map_page(scope="bogus")
        self.assertEqual(config["scope"], "bogus")
        self.assertNotContains(response, "Unavailable scope")

    def test_mine_alias_normalizes_to_private(self):
        self.client.force_login(self.owner)
        _response, config = self._map_page(scope="mine")
        self.assertEqual(config["scope"], "private")

    def test_permalink_redirects_and_resolves_to_historical(self):
        response = self.client.get(
            reverse(
                "waste-atlas-permalink",
                args=["DE", "collection_system", 2024],
            ),
            {"scope": "all"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("scope", response["Location"])
        self.client.force_login(self.admin)
        final, config = self._map_config(response["Location"])
        self.assertEqual(config["scope"], "historical")
