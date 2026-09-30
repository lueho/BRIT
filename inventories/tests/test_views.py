from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

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
