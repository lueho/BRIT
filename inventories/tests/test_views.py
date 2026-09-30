import re
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.html import escapejs

from maps.models import Catchment, GeoDataset, Region
from materials.models import Material, SampleSeries
from utils.object_management.models import User
from utils.object_management.views import (
    UserCreatedObjectAutocompleteView,
    get_tomselect_filter_pairs,
    get_tomselect_filter_value,
)
from utils.tests.testcases import AbstractTestCases

from ..models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    RunningTask,
    Scenario,
    ScenarioInventoryConfiguration,
    ScenarioStatus,
)
from ..views import (
    InventoryAlgorithmAutocompleteView,
    ScenarioGeoDataSetAutocompleteView,
    ScenarioInventoryAlgorithmAutocompleteView,
)

# ----------- Scenario CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False

    model = Scenario

    view_create_name = "scenario-create"
    view_published_list_name = "scenario-list"
    view_private_list_name = "scenario-list-owned"
    view_detail_name = "scenario-detail"
    view_update_name = "scenario-update"
    view_delete_name = "scenario-delete-modal"

    add_scope_query_param_to_list_urls = True
    allow_create_for_any_authenticated_user = True

    create_object_data = {"name": "Test Scenario"}
    update_object_data = {"name": "Updated Test Scenario"}

    @classmethod
    def create_related_objects(cls):
        region = Region.objects.create(
            name="Test Region", publication_status="published"
        )
        return {
            "region": region,
            "catchment": Catchment.objects.create(
                name="Test Catchment",
                region=region,
                parent_region=region,
                publication_status="published",
            ),
        }

    @patch("inventories.models.AsyncResult")
    def test_update_view_post_allows_edit_after_failed_inventory_run(
        self, mock_async_result
    ):
        self.client.force_login(self.owner_user)
        scenario = self.unpublished_object
        scenario.set_status(ScenarioStatus.Status.RUNNING)
        RunningTask.objects.create(scenario=scenario, uuid=uuid4())
        mock_async_result.return_value.state = "FAILURE"

        data = self.update_object_data.copy()
        data.update(self.related_objects_post_data())
        response = self.client.post(self.get_update_url(scenario.pk), data)

        scenario.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(scenario.name, self.update_object_data["name"])
        self.assertEqual(scenario.status, ScenarioStatus.Status.CHANGED)
        self.assertFalse(RunningTask.objects.filter(scenario=scenario).exists())

    def test_detail_view_offers_retry_after_failed_evaluation(self):
        self.client.force_login(self.owner_user)
        scenario = self.unpublished_object
        scenario.set_status(ScenarioStatus.Status.FAILED)

        response = self.client.get(self.get_detail_url(scenario.pk))

        self.assertContains(response, "The evaluation failed.")
        self.assertContains(response, "Retry evaluation")

    def test_result_view_shows_failed_evaluation(self):
        self.client.force_login(self.owner_user)
        scenario = self.unpublished_object
        scenario.set_status(ScenarioStatus.Status.FAILED)

        response = self.client.get(reverse("scenario-result", args=[scenario.pk]))

        self.assertContains(response, "The evaluation failed.")
        self.assertContains(response, "Return to scenario")


class InventoryAutocompleteInheritanceRegressionTests(SimpleTestCase):
    """Regression tests for tomselect subclass attribute inheritance."""

    def test_scenario_inventory_algorithm_view_inherits_search_and_value_fields(self):
        """Subclass keeps inherited search/value fields after class initialization."""
        self.assertEqual(
            ScenarioInventoryAlgorithmAutocompleteView.search_lookups,
            InventoryAlgorithmAutocompleteView.search_lookups,
        )
        self.assertEqual(
            ScenarioInventoryAlgorithmAutocompleteView.value_fields,
            InventoryAlgorithmAutocompleteView.value_fields,
        )
        self.assertEqual(
            ScenarioInventoryAlgorithmAutocompleteView.search_lookups,
            ["name__icontains"],
        )
        self.assertEqual(
            ScenarioInventoryAlgorithmAutocompleteView.value_fields,
            ["name"],
        )


class TomSelectFilterHelpersTests(SimpleTestCase):
    """Ensure helper parsing supports legacy and list-based TomSelect params."""

    def test_get_tomselect_filter_pairs_supports_single_filter_by(self):
        view = SimpleNamespace(filter_by="scope__name='published'", filters_by=[])

        self.assertEqual(
            get_tomselect_filter_pairs(view),
            [("scope__name", "published")],
        )
        self.assertEqual(get_tomselect_filter_value(view), "published")

    def test_get_tomselect_filter_pairs_supports_list_based_filters(self):
        view = SimpleNamespace(
            filter_by=None,
            filters_by=["scope__name='private'", "owner_id='12'"],
        )

        self.assertEqual(
            get_tomselect_filter_pairs(view),
            [("scope__name", "private"), ("owner_id", "12")],
        )
        self.assertEqual(get_tomselect_filter_value(view, lookup="owner_id"), "12")


class UserCreatedObjectAutocompleteViewFilterTests(SimpleTestCase):
    def setUp(self):
        self.view = UserCreatedObjectAutocompleteView()
        self.view.request = SimpleNamespace(user=AnonymousUser())

    def test_invalid_language_code_filter_fails_closed(self):
        queryset = Mock()
        empty_queryset = Mock()
        queryset.none.return_value = empty_queryset

        with patch(
            "utils.object_management.views.get_tomselect_filter_pairs",
            return_value=[("owner_id", "en-us")],
        ):
            result = self.view.apply_filters(queryset)

        self.assertIs(result, empty_queryset)

    def test_filter_exception_fails_closed(self):
        queryset = Mock()
        empty_queryset = Mock()
        queryset.none.return_value = empty_queryset
        queryset.filter.side_effect = Exception("bad lookup")

        with patch(
            "utils.object_management.views.get_tomselect_filter_pairs",
            return_value=[("parent__invalid", "123")],
        ):
            result = self.view.apply_filters(queryset)

        self.assertIs(result, empty_queryset)

    @patch("utils.object_management.views.apply_scope_filter")
    def test_scope_filter_defaults_to_published_only_for_scope_lookup(
        self, mock_apply_scope_filter
    ):
        queryset = Mock()
        scoped_queryset = Mock()
        mock_apply_scope_filter.return_value = scoped_queryset

        with patch(
            "utils.object_management.views.get_tomselect_filter_pairs",
            return_value=[("scope__name", "")],
        ):
            result = self.view.apply_filters(queryset)

        self.assertIs(result, scoped_queryset)
        mock_apply_scope_filter.assert_called_once_with(
            queryset,
            "published",
            user=self.view.request.user,
        )


class ScenarioGeoDataSetAutocompleteFilterTestCase(TestCase):
    """#213: apply_filters must use SampleSeries.material_id, not SampleSeries.id."""

    @classmethod
    def setUpTestData(cls):
        # Create spacer materials so Material PKs get ahead of SampleSeries PKs
        for i in range(5):
            Material.objects.create(name=f"Spacer Material {i}")
        cls.target_material = Material.objects.create(name="Autocomplete Target")
        cls.region = Region.objects.create(name="AC Region")
        cls.scenario = Scenario.objects.create(name="AC Scenario", region=cls.region)
        cls.geodataset = GeoDataset.objects.create(
            name="AC Dataset", region=cls.region, publication_status="published"
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="AC Algorithm", geodataset=cls.geodataset
        )
        cls.algorithm.feedstocks.add(cls.target_material)
        cls.series = SampleSeries.objects.create(
            name="AC Series", material=cls.target_material
        )

    def test_apply_filters_uses_material_id_not_series_id(self):
        self.assertNotEqual(
            self.series.id,
            self.target_material.id,
            "Test requires SampleSeries.id != Material.id to catch the bug",
        )
        view = ScenarioGeoDataSetAutocompleteView()
        view.filter_by = f"feedstock_id='{self.series.id}'"
        view.filters_by = []
        view.exclude_by = f"scenario_id='{self.scenario.id}'"
        view.excludes_by = []

        result_qs = view.apply_filters(GeoDataset.objects.all())
        self.assertIn(self.geodataset, result_qs)

    def test_widget_wire_format_returns_geodataset(self):
        """The widget sends '<source>__<lookup>=<value>' params; the lookup name
        must be extracted so the geodataset dropdown is not always empty."""
        response = self.client.get(
            reverse("scenario-geodataset-autocomplete"),
            {
                "f": f"'feedstock__feedstock_id={self.series.id}'",
                "e": f"'scenario__scenario_id={self.scenario.id}'",
            },
        )

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["results"]]
        self.assertIn(self.geodataset.id, ids)

    def test_widget_wire_format_returns_inventory_algorithm(self):
        """Same wire format applies to the algorithm dropdown
        (geodataset via filter_by, feedstock via exclude_by)."""
        response = self.client.get(
            reverse("scenario-inventoryalgorithm-autocomplete"),
            {
                "f": f"'geodataset__geodataset_id={self.geodataset.id}'",
                "e": f"'feedstock__feedstock_id={self.series.id}'",
            },
        )

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["results"]]
        self.assertIn(self.algorithm.id, ids)


class ScenarioResultCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    dashboard_view = False
    create_view = False
    public_list_view = False
    private_list_view = False
    delete_view = False

    update_view = False

    model = Scenario
    view_detail_name = "scenario-result"

    create_object_data = {"name": "Test Scenario"}

    @classmethod
    def create_related_objects(cls):
        region = Region.objects.create(
            name="Test Region", publication_status="published"
        )
        return {
            "region": region,
            "catchment": Catchment.objects.create(
                name="Test Catchment",
                region=region,
                parent_region=region,
                publication_status="published",
            ),
        }


# ----------- Issue #204: Unauthenticated endpoint tests --------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioDownloadSummaryAuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="pass")
        cls.other_user = User.objects.create_user(username="other", password="pass")
        region = Region.objects.create(name="R", publication_status="published")
        catchment = Catchment.objects.create(
            name="C",
            region=region,
            parent_region=region,
            publication_status="published",
        )
        cls.scenario = Scenario.objects.create(
            name="S", owner=cls.owner, region=region, catchment=catchment
        )

    def test_anonymous_is_denied(self):
        url = reverse(
            "scenario-download-summary", kwargs={"scenario_pk": self.scenario.pk}
        )
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 200)

    def test_non_owner_non_staff_is_denied(self):
        self.client.force_login(self.other_user)
        url = reverse(
            "scenario-download-summary", kwargs={"scenario_pk": self.scenario.pk}
        )
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

    def test_owner_can_download(self):
        self.client.force_login(self.owner)
        url = reverse(
            "scenario-download-summary", kwargs={"scenario_pk": self.scenario.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_moderator_can_download(self):
        moderator = User.objects.create_user(username="mod", password="pass")
        ct = ContentType.objects.get_for_model(Scenario)
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_scenario",
            content_type=ct,
            defaults={"name": "Can moderate scenario"},
        )
        moderator.user_permissions.add(perm)
        self.client.force_login(moderator)
        url = reverse(
            "scenario-download-summary", kwargs={"scenario_pk": self.scenario.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class ScenarioDownloadResultSummaryAuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="pass")
        cls.other_user = User.objects.create_user(username="other", password="pass")
        region = Region.objects.create(name="R", publication_status="published")
        catchment = Catchment.objects.create(
            name="C",
            region=region,
            parent_region=region,
            publication_status="published",
        )
        cls.scenario = Scenario.objects.create(
            name="S", owner=cls.owner, region=region, catchment=catchment
        )

    def test_anonymous_is_denied(self):
        url = reverse(
            "scenario-download-result-summary",
            kwargs={"scenario_pk": self.scenario.pk},
        )
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 200)

    def test_non_owner_non_staff_is_denied(self):
        self.client.force_login(self.other_user)
        url = reverse(
            "scenario-download-result-summary",
            kwargs={"scenario_pk": self.scenario.pk},
        )
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

    def test_owner_can_download(self):
        self.client.force_login(self.owner)
        url = reverse(
            "scenario-download-result-summary",
            kwargs={"scenario_pk": self.scenario.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_moderator_can_download(self):
        moderator = User.objects.create_user(username="mod", password="pass")
        ct = ContentType.objects.get_for_model(Scenario)
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_scenario",
            content_type=ct,
            defaults={"name": "Can moderate scenario"},
        )
        moderator.user_permissions.add(perm)
        self.client.force_login(moderator)
        url = reverse(
            "scenario-download-result-summary",
            kwargs={"scenario_pk": self.scenario.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class EvaluationStatusAuthTests(TestCase):
    @patch("inventories.views.AsyncResult")
    def test_anonymous_is_denied(self, mock_async):
        mock_async.return_value.status = "PENDING"
        mock_async.return_value.result = None
        mock_async.return_value.info = None
        url = reverse("scenario-evaluation-status", kwargs={"task_id": "fake-task-id"})
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 200)

    @patch("inventories.views.AsyncResult")
    def test_authenticated_can_access(self, mock_async):
        mock_async.return_value.status = "PENDING"
        mock_async.return_value.result = None
        mock_async.return_value.info = None
        user = User.objects.create_user(username="u", password="pass")
        self.client.force_login(user)
        url = reverse("scenario-evaluation-status", kwargs={"task_id": "fake-task-id"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# ----------- Issue #205: Authorization bypass test --------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioAddAlgorithmAuthBypassTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission

        cls.owner_a = User.objects.create_user(username="owner_a", password="pass")
        cls.owner_b = User.objects.create_user(username="owner_b", password="pass")
        # Grant change permission so the owner passes UserPassesTestMixin for
        # editing their own private scenario (mirrors the standard test setup).
        change_perm = Permission.objects.get(codename="change_scenario")
        cls.owner_a.user_permissions.add(change_perm)
        region = Region.objects.create(name="R", publication_status="published")
        catchment = Catchment.objects.create(
            name="C",
            region=region,
            parent_region=region,
            publication_status="published",
        )
        cls.scenario_a = Scenario.objects.create(
            name="A", owner=cls.owner_a, region=region, catchment=catchment
        )
        cls.scenario_b = Scenario.objects.create(
            name="B", owner=cls.owner_b, region=region, catchment=catchment
        )
        # Minimal valid fixtures so post() can complete without raising.
        material = Material.objects.create(name="M", owner=cls.owner_a)
        cls.feedstock = SampleSeries.objects.create(
            name="F", owner=cls.owner_a, material=material
        )
        geodataset = GeoDataset.objects.create(
            name="G", owner=cls.owner_a, region=region
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="A", geodataset=geodataset
        )

    def test_post_uses_url_pk_not_body_scenario(self):
        """post() must use the URL pk, ignoring any 'scenario' field in POST body."""
        from unittest.mock import patch

        self.client.force_login(self.owner_a)
        url = reverse(
            "scenario-add-configuration",
            kwargs={"pk": self.scenario_a.pk},
        )
        # Patch add_inventory_algorithm so no real side effects occur.
        with patch.object(Scenario, "add_inventory_algorithm") as mock_add:
            mock_add.return_value = None
            # Supply scenario_b in POST body; the view must use scenario_a
            # from the URL pk. Provide valid feedstock/algorithm so post()
            # completes and redirects rather than raising.
            response = self.client.post(
                url,
                {
                    "scenario": self.scenario_b.pk,
                    "feedstock": self.feedstock.pk,
                    "inventory_algorithm": self.algorithm.pk,
                },
            )
        # post() completed and redirected to scenario_a's detail page,
        # proving the URL pk (scenario_a) was used, not the body value.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("scenario-detail", kwargs={"pk": self.scenario_a.pk}),
        )
        mock_add.assert_called_once()


# ----------- Custom parameter values (user assumptions) --------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioCustomParameterValueTests(TestCase):
    """Users pick a preset parameter value or provide their own assumption."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="pass")
        change_perm = Permission.objects.get(codename="change_scenario")
        cls.owner.user_permissions.add(change_perm)

        region = Region.objects.create(name="R", publication_status="published")
        catchment = Catchment.objects.create(
            name="C",
            region=region,
            parent_region=region,
            publication_status="published",
        )
        cls.scenario = Scenario.objects.create(
            name="S", owner=cls.owner, region=region, catchment=catchment
        )
        cls.other_scenario = Scenario.objects.create(
            name="S2", owner=cls.owner, region=region, catchment=catchment
        )
        material = Material.objects.create(name="M", owner=cls.owner)
        cls.feedstock = SampleSeries.objects.create(
            name="F", owner=cls.owner, material=material
        )
        cls.geodataset = GeoDataset.objects.create(
            name="G", owner=cls.owner, region=region
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="A", geodataset=cls.geodataset
        )
        cls.algorithm.feedstocks.add(material)

        cls.parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Yield", short_name="yield", is_required=True
        )
        cls.parameter.inventory_algorithm.add(cls.algorithm)
        cls.preset = InventoryAlgorithmParameterValue.objects.create(
            name="Preset",
            parameter=cls.parameter,
            value=1.0,
            source="Literature",
            default=True,
        )

    def _post_data(self, **overrides):
        data = {
            "scenario": self.scenario.pk,
            "feedstock": self.feedstock.pk,
            "inventory_algorithm": self.algorithm.pk,
            f"parameter_{self.parameter.pk}": str(self.preset.pk),
        }
        data.update(overrides)
        return data

    def _add_url(self, scenario=None):
        return reverse(
            "scenario-add-configuration",
            kwargs={"pk": (scenario or self.scenario).pk},
        )

    def test_post_preset_value_uses_existing_value(self):
        self.client.force_login(self.owner)
        response = self.client.post(self._add_url(), self._post_data())
        self.assertEqual(response.status_code, 302)
        config = ScenarioInventoryConfiguration.objects.get(scenario=self.scenario)
        self.assertEqual(config.inventory_value, self.preset)

    def test_post_custom_value_creates_assumption_value(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self._add_url(),
            self._post_data(
                **{
                    f"parameter_{self.parameter.pk}": "custom",
                    f"parameter_{self.parameter.pk}_custom_value": "3.5",
                    f"parameter_{self.parameter.pk}_custom_standard_deviation": "0.2",
                    f"parameter_{self.parameter.pk}_custom_source": "My estimate",
                }
            ),
        )
        self.assertEqual(response.status_code, 302)
        value = InventoryAlgorithmParameterValue.objects.get(
            parameter=self.parameter, is_custom=True
        )
        self.assertEqual(value.value, 3.5)
        self.assertEqual(value.standard_deviation, 0.2)
        self.assertEqual(value.source, "My estimate")
        self.assertFalse(value.default)
        config = ScenarioInventoryConfiguration.objects.get(scenario=self.scenario)
        self.assertEqual(config.inventory_value, value)

    def test_post_custom_value_defaults_source(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self._add_url(),
            self._post_data(
                **{
                    f"parameter_{self.parameter.pk}": "custom",
                    f"parameter_{self.parameter.pk}_custom_value": "7.0",
                }
            ),
        )
        self.assertEqual(response.status_code, 302)
        value = InventoryAlgorithmParameterValue.objects.get(
            parameter=self.parameter, is_custom=True
        )
        self.assertEqual(value.source, "User assumption")
        self.assertIsNone(value.standard_deviation)

    def test_post_custom_value_invalid_returns_400(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self._add_url(),
            self._post_data(
                **{
                    f"parameter_{self.parameter.pk}": "custom",
                    f"parameter_{self.parameter.pk}_custom_value": "not-a-number",
                }
            ),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario
            ).exists()
        )
        self.assertFalse(
            InventoryAlgorithmParameterValue.objects.filter(is_custom=True).exists()
        )

    def test_post_custom_value_rejected_for_selection_parameter(self):
        selection_parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Method", short_name="method"
        )
        selection_parameter.inventory_algorithm.add(self.algorithm)
        InventoryAlgorithmParameterValue.objects.create(
            name="Option A",
            parameter=selection_parameter,
            value=1.0,
            type=InventoryAlgorithmParameterValue.ValueType.SELECTION,
            default=True,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            self._add_url(),
            self._post_data(
                **{
                    f"parameter_{selection_parameter.pk}": "custom",
                    f"parameter_{selection_parameter.pk}_custom_value": "5.0",
                }
            ),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            InventoryAlgorithmParameterValue.objects.filter(
                parameter=selection_parameter, is_custom=True
            ).exists()
        )

    def test_update_view_accepts_custom_value(self):
        self.scenario.add_inventory_algorithm(
            self.feedstock, self.algorithm, {self.parameter: [self.preset]}
        )
        self.client.force_login(self.owner)
        url = reverse(
            "scenario-update-config",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )
        response = self.client.post(
            url,
            self._post_data(
                **{
                    f"parameter_{self.parameter.pk}": "custom",
                    f"parameter_{self.parameter.pk}_custom_value": "8.25",
                    f"parameter_{self.parameter.pk}_custom_source": "Site visit",
                }
            ),
        )
        self.assertEqual(response.status_code, 302)
        config = ScenarioInventoryConfiguration.objects.get(scenario=self.scenario)
        self.assertEqual(config.inventory_value.value, 8.25)
        self.assertTrue(config.inventory_value.is_custom)
        self.assertEqual(config.inventory_value.source, "Site visit")

    def test_custom_values_do_not_become_algorithm_defaults(self):
        custom = InventoryAlgorithmParameterValue.objects.create(
            name="",
            parameter=self.parameter,
            value=9.9,
            is_custom=True,
            default=False,
        )
        defaults = self.algorithm.default_values()[self.parameter]
        self.assertNotIn(custom, defaults)
        self.assertIn(self.preset, defaults)

    def test_parameters_api_returns_source_and_hides_custom_values(self):
        custom = InventoryAlgorithmParameterValue.objects.create(
            name="",
            parameter=self.parameter,
            value=9.9,
            is_custom=True,
            default=False,
        )
        self.client.force_login(self.owner)
        url = reverse(
            "api-inventoryalgorithm-parameters",
            kwargs={"algorithm_pk": self.algorithm.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        target = next(p for p in response.json() if p["id"] == self.parameter.pk)
        value_ids = [v["id"] for v in target["values"]]
        self.assertIn(self.preset.id, value_ids)
        self.assertNotIn(custom.id, value_ids)
        preset_payload = next(v for v in target["values"] if v["id"] == self.preset.id)
        self.assertEqual(preset_payload["source"], "Literature")
        self.assertIn("type", preset_payload)
        self.assertIn("is_custom", preset_payload)

    def test_parameters_api_includes_custom_values_configured_in_scenario(self):
        custom = InventoryAlgorithmParameterValue.objects.create(
            name="",
            parameter=self.parameter,
            value=9.9,
            is_custom=True,
            default=False,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=self.feedstock,
            geodataset=self.geodataset,
            inventory_algorithm=self.algorithm,
            inventory_parameter=self.parameter,
            inventory_value=custom,
        )
        self.client.force_login(self.owner)
        url = reverse(
            "api-inventoryalgorithm-parameters",
            kwargs={"algorithm_pk": self.algorithm.pk},
        )

        response = self.client.get(url, {"scenario": self.scenario.pk})
        target = next(p for p in response.json() if p["id"] == self.parameter.pk)
        value_ids = [v["id"] for v in target["values"]]
        self.assertIn(custom.id, value_ids)

        response = self.client.get(url, {"scenario": self.other_scenario.pk})
        target = next(p for p in response.json() if p["id"] == self.parameter.pk)
        value_ids = [v["id"] for v in target["values"]]
        self.assertNotIn(custom.id, value_ids)

    def _update_url(self):
        return reverse(
            "scenario-update-config",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )

    def test_update_view_renders_form_media_and_selected_options(self):
        self.scenario.add_inventory_algorithm(
            self.feedstock, self.algorithm, {self.parameter: [self.preset]}
        )
        self.client.force_login(self.owner)
        response = self.client.get(self._update_url())
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for js in response.context["form"].media._js:
            self.assertIn(js, content)
        for element_id in re.findall(r'getElementById\("([^"]+)"\)', content):
            self.assertIn(f'id="{element_id}"', content)
        for obj in (self.feedstock, self.geodataset, self.algorithm):
            self.assertRegex(
                content,
                rf"allOptions\['{obj.pk}'\] = \{{\s*'id': '{obj.pk}',\s*"
                rf"'name': '{re.escape(escapejs(obj.name))}'",
            )

    def _other_users_custom_value(self):
        stranger = User.objects.create_user(username="stranger", password="pass")
        foreign_scenario = Scenario.objects.create(
            name="Foreign",
            owner=stranger,
            region=self.scenario.region,
            catchment=self.scenario.catchment,
        )
        custom = InventoryAlgorithmParameterValue.objects.create(
            name="",
            parameter=self.parameter,
            value=42.0,
            source="Private note",
            is_custom=True,
        )
        ScenarioInventoryConfiguration.objects.create(
            scenario=foreign_scenario,
            feedstock=self.feedstock,
            geodataset=self.geodataset,
            inventory_algorithm=self.algorithm,
            inventory_parameter=self.parameter,
            inventory_value=custom,
        )
        return foreign_scenario, custom

    def test_update_view_invalid_custom_value_keeps_existing_configuration(self):
        self.scenario.add_inventory_algorithm(
            self.feedstock, self.algorithm, {self.parameter: [self.preset]}
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            self._update_url(),
            self._post_data(
                **{
                    f"parameter_{self.parameter.pk}": "custom",
                    f"parameter_{self.parameter.pk}_custom_value": "not-a-number",
                }
            ),
        )
        self.assertEqual(response.status_code, 400)
        config = ScenarioInventoryConfiguration.objects.get(scenario=self.scenario)
        self.assertEqual(config.inventory_value, self.preset)
        self.assertFalse(
            InventoryAlgorithmParameterValue.objects.filter(is_custom=True).exists()
        )

    def test_update_view_keeps_previously_configured_custom_value(self):
        custom = InventoryAlgorithmParameterValue.objects.create(
            name="", parameter=self.parameter, value=9.9, is_custom=True
        )
        self.scenario.add_inventory_algorithm(
            self.feedstock, self.algorithm, {self.parameter: [custom]}
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            self._update_url(),
            self._post_data(**{f"parameter_{self.parameter.pk}": str(custom.pk)}),
        )
        self.assertEqual(response.status_code, 302)
        config = ScenarioInventoryConfiguration.objects.get(scenario=self.scenario)
        self.assertEqual(config.inventory_value, custom)

    def test_add_view_parameter_script_targets_rendered_elements(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._add_url())
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for element_id in re.findall(r'getElementById\("([^"]+)"\)', content):
            self.assertIn(f'id="{element_id}"', content)

    def test_post_rejects_custom_value_of_other_scenario(self):
        _, foreign_custom = self._other_users_custom_value()
        self.client.force_login(self.owner)
        response = self.client.post(
            self._add_url(),
            self._post_data(
                **{f"parameter_{self.parameter.pk}": str(foreign_custom.pk)}
            ),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario
            ).exists()
        )

    def test_parameters_api_hides_custom_values_of_inaccessible_scenario(self):
        foreign_scenario, foreign_custom = self._other_users_custom_value()
        url = reverse(
            "api-inventoryalgorithm-parameters",
            kwargs={"algorithm_pk": self.algorithm.pk},
        )
        self.client.force_login(self.owner)
        response = self.client.get(url, {"scenario": foreign_scenario.pk})
        self.assertEqual(response.status_code, 200)
        target = next(p for p in response.json() if p["id"] == self.parameter.pk)
        self.assertNotIn(foreign_custom.id, [v["id"] for v in target["values"]])

    def test_parameters_api_ignores_malformed_scenario_parameter(self):
        url = reverse(
            "api-inventoryalgorithm-parameters",
            kwargs={"algorithm_pk": self.algorithm.pk},
        )
        self.client.force_login(self.owner)
        response = self.client.get(url, {"scenario": "not-a-pk"})
        self.assertEqual(response.status_code, 200)

    def test_custom_value_is_never_default(self):
        custom = InventoryAlgorithmParameterValue.objects.create(
            name="", parameter=self.parameter, value=3.5, is_custom=True, default=True
        )
        custom.refresh_from_db()
        self.preset.refresh_from_db()
        self.assertFalse(custom.default)
        self.assertTrue(self.preset.default)
        self.assertIn(self.preset, self.algorithm.default_values()[self.parameter])


class ScenarioDetailViewRunTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create(username="scenario-run-owner")
        self.owner.user_permissions.add(
            Permission.objects.get(codename="change_scenario")
        )
        self.scenario = Scenario.objects.create(
            name="Run Scenario",
            owner=self.owner,
            region=Region.objects.create(name="Run Region"),
        )
        self.client.force_login(self.owner)

    @patch("inventories.views.start_inventory_run")
    def test_post_starts_run_through_serialized_entry_point(self, start_run):
        response = self.client.post(
            reverse("scenario-detail", kwargs={"pk": self.scenario.pk})
        )

        self.assertRedirects(
            response,
            reverse("scenario-result", args=[self.scenario.pk]),
            fetch_redirect_response=False,
        )
        start_run.assert_called_once_with(self.scenario.pk)

    @patch("inventories.tasks.run_inventory")
    def test_post_does_not_enqueue_second_run_while_running(self, run_inventory_task):
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("scenario-detail", kwargs={"pk": self.scenario.pk})
            )

        run_inventory_task.delay.assert_not_called()

    def test_progress_page_lists_only_algorithm_tasks(self):
        algorithm = InventoryAlgorithm.objects.create(
            name="Progress Algorithm",
            geodataset=GeoDataset.objects.create(
                name="Progress Dataset", region=self.scenario.region
            ),
        )
        self.scenario.set_status(ScenarioStatus.Status.RUNNING)
        RunningTask.objects.create(
            scenario=self.scenario, algorithm=algorithm, uuid=uuid4()
        )
        RunningTask.objects.create(scenario=self.scenario, uuid=uuid4())

        response = self.client.get(reverse("scenario-result", args=[self.scenario.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [task["algorithm_name"] for task in response.context["task_list"]["tasks"]],
            ["Progress Algorithm"],
        )


class ScenarioDetailRunAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="pass")
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_scenario")
        )
        cls.other_user = User.objects.create_user(username="other", password="pass")
        region = Region.objects.create(name="R", publication_status="published")
        catchment = Catchment.objects.create(
            name="C",
            region=region,
            parent_region=region,
            publication_status="published",
        )
        cls.private_scenario = Scenario.objects.create(
            name="Private", owner=cls.owner, region=region, catchment=catchment
        )
        cls.published_scenario = Scenario.objects.create(
            name="Published",
            owner=cls.owner,
            region=region,
            catchment=catchment,
            publication_status="published",
        )

    def detail_url(self, scenario):
        return reverse("scenario-detail", kwargs={"pk": scenario.pk})

    @patch("inventories.views.start_inventory_run")
    def test_anonymous_cannot_run_published_scenario(self, mock_run):
        response = self.client.post(self.detail_url(self.published_scenario))

        self.assertEqual(response.status_code, 403)
        mock_run.assert_not_called()
        self.published_scenario.scenariostatus.refresh_from_db()
        self.assertEqual(
            self.published_scenario.scenariostatus.status,
            ScenarioStatus.Status.CHANGED,
        )

    @patch("inventories.views.start_inventory_run")
    def test_non_owner_cannot_run_published_scenario(self, mock_run):
        self.client.force_login(self.other_user)

        response = self.client.post(self.detail_url(self.published_scenario))

        self.assertEqual(response.status_code, 403)
        mock_run.assert_not_called()

    @patch("inventories.views.start_inventory_run")
    def test_owner_can_run_private_scenario(self, mock_run):
        self.client.force_login(self.owner)

        response = self.client.post(self.detail_url(self.private_scenario))

        self.assertRedirects(
            response,
            reverse("scenario-result", kwargs={"pk": self.private_scenario.pk}),
            fetch_redirect_response=False,
        )
        mock_run.assert_called_once_with(self.private_scenario.pk)

    def test_anonymous_can_view_published_scenario_without_run_form(self):
        response = self.client.get(self.detail_url(self.published_scenario))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="run"')

    def test_owner_sees_run_form_on_private_scenario(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.detail_url(self.private_scenario))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="run"')


# ----------- Missing-object lookups must return 404, not 500 ----------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioConfigurationObjectLookupTests(TestCase):
    """User-controlled ids in the scenario configuration and result-map views
    must produce 404 instead of an unhandled DoesNotExist/ValueError (500)."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="pass")
        change_perm = Permission.objects.get(codename="change_scenario")
        cls.owner.user_permissions.add(change_perm)
        cls.region = Region.objects.create(name="R", publication_status="published")
        cls.catchment = Catchment.objects.create(
            name="C",
            region=cls.region,
            parent_region=cls.region,
            publication_status="published",
        )
        cls.scenario = Scenario.objects.create(
            name="S", owner=cls.owner, region=cls.region, catchment=cls.catchment
        )
        cls.material = Material.objects.create(name="M", owner=cls.owner)
        cls.feedstock = SampleSeries.objects.create(
            name="F", owner=cls.owner, material=cls.material
        )
        cls.geodataset = GeoDataset.objects.create(
            name="G", owner=cls.owner, region=cls.region
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="A", geodataset=cls.geodataset
        )
        cls.algorithm.feedstocks.add(cls.material)
        cls.parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="P", short_name="p"
        )
        cls.parameter.inventory_algorithm.add(cls.algorithm)
        cls.value = InventoryAlgorithmParameterValue.objects.create(
            name="V", parameter=cls.parameter, value=1.0
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def add_url(self):
        return reverse("scenario-add-configuration", kwargs={"pk": self.scenario.pk})

    def update_url(self):
        return reverse(
            "scenario-update-config",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )

    def remove_url(self):
        return reverse(
            "scenario-remove-algorithm",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )

    def result_map_url(self, scenario_pk=None, algorithm_pk=None, feedstock_pk=None):
        return reverse(
            "scenario-result-map",
            kwargs={
                "pk": scenario_pk or self.scenario.pk,
                "algorithm_pk": algorithm_pk or self.algorithm.pk,
                "feedstock_pk": feedstock_pk or self.feedstock.pk,
            },
        )

    # --- ScenarioAddInventoryAlgorithmView ---

    def test_add_view_missing_scenario_returns_404(self):
        url = reverse("scenario-add-configuration", kwargs={"pk": 999999})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {}).status_code, 404)

    def test_add_view_post_unknown_feedstock_returns_404(self):
        response = self.client.post(
            self.add_url(),
            {"feedstock": 999999, "inventory_algorithm": self.algorithm.pk},
        )
        self.assertEqual(response.status_code, 404)

    def test_add_view_post_unknown_algorithm_returns_404(self):
        response = self.client.post(
            self.add_url(),
            {"feedstock": self.feedstock.pk, "inventory_algorithm": 999999},
        )
        self.assertEqual(response.status_code, 404)

    def test_add_view_post_malformed_feedstock_returns_404(self):
        response = self.client.post(
            self.add_url(),
            {"feedstock": "not-a-number", "inventory_algorithm": self.algorithm.pk},
        )
        self.assertEqual(response.status_code, 404)

    def test_add_view_post_unknown_parameter_value_returns_404(self):
        response = self.client.post(
            self.add_url(),
            {
                "feedstock": self.feedstock.pk,
                "inventory_algorithm": self.algorithm.pk,
                f"parameter_{self.parameter.pk}": 999999,
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_add_view_post_unavailable_feedstock_returns_404(self):
        unavailable_material = Material.objects.create(
            name="Unusable", owner=self.owner
        )
        unavailable_feedstock = SampleSeries.objects.create(
            name="Unusable F", owner=self.owner, material=unavailable_material
        )
        response = self.client.post(
            self.add_url(),
            {
                "feedstock": unavailable_feedstock.pk,
                "inventory_algorithm": self.algorithm.pk,
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario
            ).exists()
        )

    # --- ScenarioAlgorithmConfigurationUpdateView ---

    def test_update_view_missing_scenario_returns_404(self):
        url = reverse(
            "scenario-update-config",
            kwargs={
                "scenario_pk": 999999,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {}).status_code, 404)

    def test_update_view_get_unknown_algorithm_returns_404(self):
        url = reverse(
            "scenario-update-config",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": 999999,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_update_view_post_unknown_feedstock_returns_404_without_mutation(self):
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=self.feedstock,
            geodataset=self.geodataset,
            inventory_algorithm=self.algorithm,
            inventory_parameter=self.parameter,
            inventory_value=self.value,
        )
        response = self.client.post(
            self.update_url(),
            {"feedstock": 999999, "inventory_algorithm": self.algorithm.pk},
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario,
                feedstock=self.feedstock,
                inventory_algorithm=self.algorithm,
            ).exists(),
            "existing configuration must survive a failed update POST",
        )

    def test_update_view_post_unknown_parameter_value_returns_404(self):
        response = self.client.post(
            self.update_url(),
            {
                "feedstock": self.feedstock.pk,
                "inventory_algorithm": self.algorithm.pk,
                f"parameter_{self.parameter.pk}": 999999,
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_update_view_failed_add_rolls_back_removed_configuration(self):
        """An existing but unavailable feedstock fails inside add_inventory_algorithm;
        the atomic block must roll back the removal of the old configuration."""
        config = ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=self.feedstock,
            geodataset=self.geodataset,
            inventory_algorithm=self.algorithm,
            inventory_parameter=self.parameter,
            inventory_value=self.value,
        )
        unavailable_material = Material.objects.create(
            name="Unusable", owner=self.owner
        )
        unavailable_feedstock = SampleSeries.objects.create(
            name="Unusable F", owner=self.owner, material=unavailable_material
        )
        response = self.client.post(
            self.update_url(),
            {
                "feedstock": unavailable_feedstock.pk,
                "inventory_algorithm": self.algorithm.pk,
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=config.pk).exists(),
            "failed update must roll back the removal of the old configuration",
        )

    # --- ScenarioRemoveInventoryAlgorithmView ---

    def test_remove_view_missing_scenario_returns_404(self):
        url = reverse(
            "scenario-remove-algorithm",
            kwargs={
                "scenario_pk": 999999,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_remove_view_unknown_algorithm_returns_404(self):
        url = reverse(
            "scenario-remove-algorithm",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": 999999,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # --- ScenarioResultDetailMapView ---

    def test_result_map_unknown_scenario_returns_404(self):
        self.client.logout()
        response = self.client.get(self.result_map_url(scenario_pk=999999))
        self.assertEqual(response.status_code, 404)

    def test_result_map_unknown_algorithm_returns_404(self):
        self.client.logout()
        response = self.client.get(self.result_map_url(algorithm_pk=999999))
        self.assertEqual(response.status_code, 404)

    def test_result_map_missing_layer_returns_404(self):
        self.client.logout()
        response = self.client.get(self.result_map_url())
        self.assertEqual(response.status_code, 404)
