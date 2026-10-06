import re
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.html import escapejs

from layer_manager.models import Layer
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material
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
    """apply_filters resolves the feedstock id as a Material id."""

    @classmethod
    def setUpTestData(cls):
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

    def test_apply_filters_uses_material_id(self):
        view = ScenarioGeoDataSetAutocompleteView()
        view.filter_by = f"feedstock_id='{self.target_material.id}'"
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
                "f": f"'feedstock__feedstock_id={self.target_material.id}'",
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
                "e": f"'feedstock__feedstock_id={self.target_material.id}'",
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


class GeoDatasetFunctionsAPITestCase(TestCase):
    """The functions API tells the add-inventory form which generic
    algorithms apply to the selected dataset's geometry."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="fn-user", password="pass")
        cls.region = Region.objects.create(
            name="FN Region", publication_status="published"
        )
        cls.point_dataset = GeoDataset.objects.create(
            name="Points",
            region=cls.region,
            model_name="NantesGreenhouses",
            publication_status="published",
        )
        cls.polygon_dataset = GeoDataset.objects.create(
            name="Parcels",
            region=cls.region,
            model_name="NutsRegion",
            publication_status="published",
        )

    def _get(self, dataset):
        self.client.force_login(self.user)
        return self.client.get(
            reverse("api-geodataset-functions", kwargs={"geodataset_pk": dataset.pk})
        )

    def test_point_dataset_offers_count_based(self):
        response = self._get(self.point_dataset)
        self.assertEqual(response.status_code, 200)
        names = [f["function_name"] for f in response.json()["functions"]]
        self.assertEqual(names, ["count_based_production"])

    def test_polygon_dataset_offers_area_based(self):
        response = self._get(self.polygon_dataset)
        self.assertEqual(response.status_code, 200)
        names = [f["function_name"] for f in response.json()["functions"]]
        self.assertEqual(names, ["area_based_production"])

    def test_response_includes_labels(self):
        response = self._get(self.point_dataset)
        functions = response.json()["functions"]
        self.assertEqual(functions[0]["name"], "Count-based production")

    def test_anonymous_is_denied(self):
        response = self.client.get(
            reverse(
                "api-geodataset-functions",
                kwargs={"geodataset_pk": self.point_dataset.pk},
            )
        )
        self.assertNotEqual(response.status_code, 200)

    def test_unknown_dataset_returns_404(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("api-geodataset-functions", kwargs={"geodataset_pk": 999999})
        )
        self.assertEqual(response.status_code, 404)


class ScenarioGeodatasetAutocompleteRegionScopeTestCase(TestCase):
    """In the generic flow the geodataset dropdown is driven by the
    scenario's region — a feedstock filter may optionally narrow it."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="ac-user", password="pass")
        cls.region = Region.objects.create(
            name="Scope Region", publication_status="published"
        )
        cls.other_region = Region.objects.create(
            name="Other Region", publication_status="published"
        )
        cls.scenario = Scenario.objects.create(name="Scope Scenario", region=cls.region)
        cls.dataset_in_region = GeoDataset.objects.create(
            name="In-region dataset",
            region=cls.region,
            publication_status="published",
        )
        cls.dataset_other_region = GeoDataset.objects.create(
            name="Other-region dataset",
            region=cls.other_region,
            publication_status="published",
        )

    def test_region_scoped_listing_without_feedstock(self):
        """With only the scenario filter the dropdown lists all datasets in
        the scenario's region, regardless of pre-registered algorithms."""
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("scenario-geodataset-autocomplete"),
            {"f": f"'scenario__scenario_id={self.scenario.id}'"},
        )
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["results"]]
        self.assertIn(self.dataset_in_region.id, ids)
        self.assertNotIn(self.dataset_other_region.id, ids)


class GenericAlgorithmAddViewTestCase(TestCase):
    """POSTing a generic_function + kwarg rows materializes the algorithm
    record, its parameters and the configuration entries."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="gen-owner", password="pass")
        change_perm = Permission.objects.get(codename="change_scenario")
        cls.owner.user_permissions.add(change_perm)
        cls.region = Region.objects.create(
            name="Gen Region", publication_status="published"
        )
        catchment = Catchment.objects.create(
            name="Gen Catchment",
            region=cls.region,
            parent_region=cls.region,
            publication_status="published",
        )
        cls.scenario = Scenario.objects.create(
            name="Gen Scenario",
            owner=cls.owner,
            region=cls.region,
            catchment=catchment,
        )
        cls.material = Material.objects.create(name="Gen Material")
        cls.feedstock = cls.material
        cls.point_dataset = GeoDataset.objects.create(
            name="Gen Points",
            region=cls.region,
            model_name="NantesGreenhouses",
            publication_status="published",
        )
        cls.other_region_dataset = GeoDataset.objects.create(
            name="Foreign dataset",
            region=Region.objects.create(
                name="Foreign region", publication_status="published"
            ),
            model_name="NantesGreenhouses",
            publication_status="published",
        )

    def _url(self):
        return reverse("scenario-add-configuration", kwargs={"pk": self.scenario.pk})

    def _post(self, **overrides):
        data = {
            "feedstock": self.feedstock.pk,
            "geodataset": self.point_dataset.pk,
            "generic_function": "count_based_production",
        }
        data.update(overrides)
        self.client.force_login(self.owner)
        return self.client.post(self._url(), data)

    def test_creates_algorithm_config_and_parameters(self):
        response = self._post(
            kwarg_name=["point_yield", "availability"],
            kwarg_value=["12.5", "0.8"],
            kwarg_unit=["kg / year", ""],
        )
        self.assertEqual(response.status_code, 302)

        algorithm = InventoryAlgorithm.objects.get(
            geodataset=self.point_dataset,
            function_name="count_based_production",
        )
        self.assertEqual(algorithm.source_module, "inventories.algorithms")
        self.assertIn(self.material, algorithm.feedstocks.all())

        configs = ScenarioInventoryConfiguration.objects.filter(
            scenario=self.scenario, inventory_algorithm=algorithm
        )
        self.assertEqual(configs.count(), 2)
        param_names = set(
            configs.values_list("inventory_parameter__short_name", flat=True)
        )
        self.assertEqual(param_names, {"point_yield", "availability"})

        plan = self.scenario.inventory_execution_plan()
        kwargs = plan[0]["kwargs"]
        self.assertEqual(kwargs["point_yield"]["value"], 12.5)
        self.assertEqual(kwargs["point_yield"]["unit"], "kg / year")
        self.assertEqual(kwargs["availability"]["value"], 0.8)

    def test_reusing_algorithm_on_second_post(self):
        self._post(kwarg_name=["f1"], kwarg_value=["1.0"], kwarg_unit=[""])
        response = self._post(kwarg_name=["f1"], kwarg_value=["2.0"], kwarg_unit=["kg"])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            InventoryAlgorithm.objects.filter(
                geodataset=self.point_dataset,
                function_name="count_based_production",
            ).count(),
            1,
        )

    def test_no_kwargs_still_configures_algorithm(self):
        response = self._post()
        self.assertEqual(response.status_code, 302)
        algorithm = InventoryAlgorithm.objects.get(
            geodataset=self.point_dataset,
            function_name="count_based_production",
        )
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario, inventory_algorithm=algorithm
            ).exists()
        )

    def test_geometry_mismatch_returns_400(self):
        response = self._post(generic_function="area_based_production")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            InventoryAlgorithm.objects.filter(
                geodataset=self.point_dataset,
                function_name="area_based_production",
            ).exists()
        )

    def test_dataset_outside_region_returns_400(self):
        response = self._post(geodataset=self.other_region_dataset.pk)
        self.assertIn(response.status_code, [400, 404])
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario
            ).exists()
        )

    def test_invalid_kwarg_name_returns_400(self):
        response = self._post(
            kwarg_name=["not a valid name!"],
            kwarg_value=["1.0"],
            kwarg_unit=[""],
        )
        self.assertEqual(response.status_code, 400)

    def test_non_numeric_kwarg_value_returns_400(self):
        response = self._post(
            kwarg_name=["yield"],
            kwarg_value=["banana"],
            kwarg_unit=["kg"],
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario
            ).exists()
        )

    def test_unknown_function_returns_400(self):
        response = self._post(generic_function="definitely_not_a_function")
        self.assertEqual(response.status_code, 400)

    def test_feature_filter_creates_selection_parameter(self):
        response = self._post(
            filter_column="culture_1",
            filter_value="Tomato",
            kwarg_name=["yield"],
            kwarg_value=["10"],
            kwarg_unit=["kg"],
        )
        self.assertEqual(response.status_code, 302)
        algorithm = InventoryAlgorithm.objects.get(
            geodataset=self.point_dataset,
            function_name="count_based_production",
        )
        param = InventoryAlgorithmParameter.objects.get(
            inventory_algorithm=algorithm, short_name="feature_filter"
        )
        value = param.inventoryalgorithmparametervalue_set.get()
        self.assertEqual(
            value.type, InventoryAlgorithmParameterValue.ValueType.SELECTION
        )
        self.assertEqual(value.name, "culture_1=Tomato")
        plan = self.scenario.inventory_execution_plan()
        self.assertEqual(
            plan[0]["kwargs"]["feature_filter"]["selection"], "culture_1=Tomato"
        )

    def test_feature_filter_rejects_unknown_column(self):
        response = self._post(
            filter_column="not_a_column",
            filter_value="x",
        )
        self.assertEqual(response.status_code, 400)

    def test_functions_api_lists_filter_columns(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "api-geodataset-functions",
                kwargs={"geodataset_pk": self.point_dataset.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        columns = {c["name"]: c["values"] for c in response.json()["columns"]}
        self.assertIn("culture_1", columns)
        self.assertNotIn("geom", columns)

    def test_update_config_includes_feature_filter_for_preselection(self):
        """The update form builds its preselection map from
        inventory_algorithm_config and the parameters API exposes the
        scenario's custom values — together they preselect the filter."""
        self._post(
            filter_column="culture_1",
            filter_value="Tomato",
            kwarg_name=["yield"],
            kwarg_value=["10"],
            kwarg_unit=["kg"],
        )
        algorithm = InventoryAlgorithm.objects.get(
            geodataset=self.point_dataset,
            function_name="count_based_production",
        )
        config = self.scenario.inventory_algorithm_config(algorithm, self.feedstock)
        preselected = {}
        for entry in config["parameters"]:
            preselected.update(entry)
        self.assertIn("feature_filter", preselected)
        filter_value_id = preselected["feature_filter"]

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "api-inventoryalgorithm-parameters",
                kwargs={"algorithm_pk": algorithm.pk},
            )
            + f"?scenario={self.scenario.pk}"
        )
        self.assertEqual(response.status_code, 200)
        params = {p["short_name"]: p for p in response.json()}
        # The stored custom selection is offered so the select can preselect it.
        filter_value_ids = [v["id"] for v in params["feature_filter"]["values"]]
        self.assertIn(filter_value_id, filter_value_ids)
        # The custom factor value is exposed too, so its select can preselect.
        self.assertIn(
            preselected["yield"], [v["id"] for v in params["yield"]["values"]]
        )

    def test_functions_api_includes_factor_presets(self):
        """After a dataset+function has been configured once, its factors
        are offered as presets for the next configuration."""
        self._post(
            kwarg_name=["yield"],
            kwarg_value=["10"],
            kwarg_unit=["kg"],
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "api-geodataset-functions",
                kwargs={"geodataset_pk": self.point_dataset.pk},
            )
            + f"?scenario={self.scenario.pk}"
        )
        self.assertEqual(response.status_code, 200)
        function = response.json()["functions"][0]
        presets = {p["short_name"]: p for p in function["parameters"]}
        self.assertIn("yield", presets)
        self.assertEqual(presets["yield"]["values"][0]["value"], 10.0)

    def test_functions_api_presets_exclude_feature_filter(self):
        self._post(filter_column="culture_1", filter_value="Tomato")
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "api-geodataset-functions",
                kwargs={"geodataset_pk": self.point_dataset.pk},
            )
            + f"?scenario={self.scenario.pk}"
        )
        function = response.json()["functions"][0]
        names = [p["short_name"] for p in function["parameters"]]
        self.assertNotIn("feature_filter", names)

    def test_preset_value_reused_on_post(self):
        """Picking a preset in the factor editor posts kwarg_preset with the
        existing value id — the config reuses it instead of duplicating."""
        self._post(kwarg_name=["yield"], kwarg_value=["10"], kwarg_unit=["kg"])
        preset_value = InventoryAlgorithmParameterValue.objects.get(
            parameter__short_name="yield", value=10.0
        )
        # Configure a second feedstock on the same dataset, reusing the preset.
        other_feedstock = Material.objects.create(name="Other Material")
        response = self._post(
            feedstock=other_feedstock.pk,
            kwarg_name=["yield"],
            kwarg_value=["10"],
            kwarg_preset=[str(preset_value.pk)],
        )
        self.assertEqual(response.status_code, 302)
        config_row = ScenarioInventoryConfiguration.objects.get(
            scenario=self.scenario,
            feedstock=other_feedstock,
            inventory_parameter__short_name="yield",
        )
        self.assertEqual(config_row.inventory_value_id, preset_value.pk)

    def test_conflicting_factor_unit_rejected(self):
        """A shared factor parameter keeps its unit; posting the same factor
        name with a different unit is rejected instead of silently
        reinterpreting existing values."""
        self._post(kwarg_name=["yield"], kwarg_value=["10"], kwarg_unit=["kg / year"])
        response = self._post(
            kwarg_name=["yield"], kwarg_value=["10"], kwarg_unit=["g / year"]
        )
        self.assertEqual(response.status_code, 400)
        parameter = InventoryAlgorithmParameter.objects.get(short_name="yield")
        self.assertEqual(parameter.unit, "kg / year")

    def test_missing_unit_can_be_filled_later(self):
        """A parameter whose unit was never set can receive one later —
        that does not reinterpret existing values."""
        self._post(kwarg_name=["yield"], kwarg_value=["10"], kwarg_unit=[""])
        response = self._post(
            kwarg_name=["yield"], kwarg_value=["10"], kwarg_unit=["kg / year"]
        )
        self.assertEqual(response.status_code, 302)
        parameter = InventoryAlgorithmParameter.objects.get(short_name="yield")
        self.assertEqual(parameter.unit, "kg / year")

    def test_feedstock_without_registered_algorithm_is_selectable(self):
        """The add form must offer materials that no algorithm references
        yet — the generic flow is how they get their first algorithm."""
        new_material = Material.objects.create(name="Brand New Material")
        self.client.force_login(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            new_material, response.context["form"].fields["feedstock"].queryset
        )

    def test_private_geodataset_rejected_on_generic_post(self):
        """A private dataset of another user must not be configurable —
        generic execution would read and republish its features."""
        stranger = User.objects.create_user(username="stranger", password="p")
        private_dataset = GeoDataset.objects.create(
            name="Private dataset",
            owner=stranger,
            region=self.region,
            model_name="NantesGreenhouses",
            publication_status="private",
        )
        response = self._post(
            geodataset=private_dataset.pk,
            kwarg_name=["yield"],
            kwarg_value=["10"],
            kwarg_unit=["kg"],
        )
        self.assertIn(response.status_code, [400, 404])
        self.assertFalse(
            InventoryAlgorithm.objects.filter(geodataset=private_dataset).exists()
        )
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario
            ).exists()
        )

    def test_posted_lookup_does_not_fall_back_on_empty_queryset(self):
        """An empty visibility queryset must stay empty — falling back to
        the unfiltered manager would re-open private-object access."""
        from django.http import Http404

        from ..views import _get_posted_object_or_404

        stranger = User.objects.create_user(username="stranger", password="p")
        private_dataset = GeoDataset.objects.create(
            name="Private dataset",
            owner=stranger,
            region=self.region,
            model_name="NantesGreenhouses",
            publication_status="private",
        )
        with self.assertRaises(Http404):
            _get_posted_object_or_404(
                GeoDataset,
                private_dataset.pk,
                queryset=GeoDataset.objects.none(),
            )

    def test_functions_api_hides_private_dataset(self):
        """The functions API must not leak sampled values of private
        datasets to unrelated users."""
        stranger = User.objects.create_user(username="stranger", password="p")
        private_dataset = GeoDataset.objects.create(
            name="Private dataset",
            owner=stranger,
            region=self.region,
            model_name="NantesGreenhouses",
            publication_status="private",
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "api-geodataset-functions",
                kwargs={"geodataset_pk": private_dataset.pk},
            )
        )
        self.assertEqual(response.status_code, 404)


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
        # get_for_model() is fed from a process-global cache that parallel test
        # workers inherit from their parent — query the row directly so the
        # permission is attached to the correct content type.
        ct = ContentType.objects.get(app_label="inventories", model="scenario")
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
        # get_for_model() is fed from a process-global cache that parallel test
        # workers inherit from their parent — query the row directly so the
        # permission is attached to the correct content type.
        ct = ContentType.objects.get(app_label="inventories", model="scenario")
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
        cls.feedstock = Material.objects.create(name="M", owner=cls.owner_a)
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
        cls.feedstock = material
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

    def test_update_view_heading_describes_update(self):
        self.scenario.add_inventory_algorithm(
            self.feedstock, self.algorithm, {self.parameter: [self.preset]}
        )
        self.client.force_login(self.owner)
        response = self.client.get(self._update_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Add an algorithm")
        self.assertContains(response, "Change the algorithm configuration")

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
        for malformed in ("not-a-pk", "\u00b2", "\u0663"):
            response = self.client.get(url, {"scenario": malformed})
            self.assertEqual(response.status_code, 200, malformed)

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


class ScenarioInventoryEditLinkTests(TestCase):
    """The per-inventory "Edit" link follows policy.can_edit: staff see it
    even on published scenarios, owners only on unpublished ones."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="pass")
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_scenario")
        )
        cls.staff = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        region = Region.objects.create(name="R", publication_status="published")
        catchment = Catchment.objects.create(
            name="C",
            region=region,
            parent_region=region,
            publication_status="published",
        )
        cls.published_scenario = Scenario.objects.create(
            name="Published",
            owner=cls.owner,
            region=region,
            catchment=catchment,
            publication_status="published",
        )
        cls.private_scenario = Scenario.objects.create(
            name="Private", owner=cls.owner, region=region, catchment=catchment
        )
        feedstock = Material.objects.create(name="M", owner=cls.owner)
        geodataset = GeoDataset.objects.create(name="G", owner=cls.owner, region=region)
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="A", geodataset=geodataset
        )
        cls.algorithm.feedstocks.add(feedstock)
        cls.feedstock = feedstock
        for scenario in (cls.published_scenario, cls.private_scenario):
            ScenarioInventoryConfiguration.objects.create(
                scenario=scenario,
                feedstock=feedstock,
                geodataset=geodataset,
                inventory_algorithm=cls.algorithm,
            )

    def edit_url(self, scenario):
        return reverse(
            "scenario-update-config",
            kwargs={
                "scenario_pk": scenario.pk,
                "feedstock_pk": self.feedstock.pk,
                "algorithm_pk": self.algorithm.pk,
            },
        )

    def detail(self, scenario):
        return self.client.get(reverse("scenario-detail", kwargs={"pk": scenario.pk}))

    def test_staff_sees_edit_link_on_published_scenario(self):
        self.client.force_login(self.staff)

        response = self.detail(self.published_scenario)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.edit_url(self.published_scenario))

    def test_owner_does_not_see_edit_link_on_published_scenario(self):
        self.client.force_login(self.owner)

        response = self.detail(self.published_scenario)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.edit_url(self.published_scenario))

    def test_owner_sees_edit_link_on_private_scenario(self):
        self.client.force_login(self.owner)

        response = self.detail(self.private_scenario)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.edit_url(self.private_scenario))


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
        cls.feedstock = cls.material
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
        unavailable_feedstock = Material.objects.create(
            name="Unusable", owner=self.owner
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
        unavailable_feedstock = Material.objects.create(
            name="Unusable", owner=self.owner
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


class ScenarioResultMapTestCase(TestCase):
    """The result map and its GeoJSON endpoints show the stored result layer
    to everyone who may read the scenario, and to nobody else."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.other_user = User.objects.create_user(username="other")
        cls.region = Region.objects.create(
            name="Result Region", publication_status="published"
        )
        cls.catchment = Catchment.objects.create(
            name="Result Catchment",
            region=cls.region,
            parent_region=cls.region,
            publication_status="published",
        )
        cls.feedstock = Material.objects.create(
            name="Result Feedstock", publication_status="published"
        )
        geodataset = GeoDataset.objects.create(
            name="Result Dataset", region=cls.region, publication_status="published"
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="Result Algorithm", geodataset=geodataset
        )
        cls.published_scenario = Scenario.objects.create(
            name="Published Result Scenario",
            owner=cls.owner,
            region=cls.region,
            catchment=cls.catchment,
            publication_status="published",
        )
        cls.private_scenario = Scenario.objects.create(
            name="Private Result Scenario",
            owner=cls.owner,
            region=cls.region,
            catchment=cls.catchment,
        )

    def setUp(self):
        self.published_layer = self.create_layer(self.published_scenario)
        self.private_layer = self.create_layer(self.private_scenario)

    def create_layer(self, scenario, total=100.0):
        layer, _ = Layer.objects.create_or_replace(
            name="Result layer",
            scenario=scenario,
            feedstock=self.feedstock,
            algorithm=self.algorithm,
            results={
                "features": [
                    {
                        "geom": MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (0, 0)))),
                        "yield": 12.5,
                    }
                ],
                "aggregated_values": [
                    {"name": "Total production", "value": total, "unit": "Mg/a"}
                ],
            },
        )
        return layer

    def map_url(self, scenario):
        return reverse(
            "scenario-result-map",
            kwargs={
                "pk": scenario.pk,
                "algorithm_pk": self.algorithm.pk,
                "feedstock_pk": self.feedstock.pk,
            },
        )

    def geojson_url(self, layer):
        return reverse("data-result-layer", kwargs={"layer_name": layer.table_name})

    def version_url(self, layer):
        return reverse(
            "data-result-layer-version", kwargs={"layer_name": layer.table_name}
        )

    def test_result_map_of_private_scenario_is_hidden_from_other_users(self):
        response = self.client.get(self.map_url(self.private_scenario))
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.other_user)
        response = self.client.get(self.map_url(self.private_scenario))
        self.assertEqual(response.status_code, 404)

    def test_owner_sees_result_map_of_private_scenario(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.map_url(self.private_scenario))
        self.assertEqual(response.status_code, 200)

    def test_result_map_loads_result_layer_features(self):
        response = self.client.get(self.map_url(self.published_scenario))

        self.assertEqual(response.status_code, 200)
        map_config = response.context["map_config"]
        self.assertTrue(map_config["loadFeatures"])
        self.assertEqual(
            map_config["featuresLayerGeometriesUrl"],
            self.geojson_url(self.published_layer),
        )

    def test_result_map_breadcrumbs_lead_back_to_scenario_results(self):
        response = self.client.get(self.map_url(self.published_scenario))

        self.assertEqual(response.context["breadcrumb_module_label"], "Inventories")
        self.assertEqual(response.context["breadcrumb_section_label"], "Scenarios")
        self.assertEqual(
            response.context["breadcrumb_object_label"], self.published_scenario.name
        )
        self.assertEqual(
            response.context["breadcrumb_object_url"],
            reverse("scenario-result", kwargs={"pk": self.published_scenario.pk}),
        )
        self.assertEqual(response.context["breadcrumb_action_label"], "Result map")

    def test_anonymous_user_gets_geojson_of_published_result_layer(self):
        response = self.client.get(self.geojson_url(self.published_layer))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), 1)
        self.assertEqual(data["features"][0]["properties"]["yield"], 12.5)
        self.assertTrue(response.headers.get("X-Data-Version"))

    def test_geojson_of_private_result_layer_is_hidden_from_other_users(self):
        for url in (
            self.geojson_url(self.private_layer),
            self.version_url(self.private_layer),
        ):
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.other_user)
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_owner_gets_geojson_of_private_result_layer(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.geojson_url(self.private_layer))
        self.assertEqual(response.status_code, 200)

    def test_unknown_result_layer_returns_404(self):
        response = self.client.get(
            reverse("data-result-layer", kwargs={"layer_name": "missing"})
        )
        self.assertEqual(response.status_code, 404)

    def test_version_changes_when_results_are_recomputed(self):
        geojson_response = self.client.get(self.geojson_url(self.published_layer))
        version = self.client.get(self.version_url(self.published_layer)).json()[
            "version"
        ]
        self.assertEqual(version, geojson_response.headers["X-Data-Version"])

        self.create_layer(self.published_scenario, total=200.0)

        new_version = self.client.get(self.version_url(self.published_layer)).json()[
            "version"
        ]
        self.assertNotEqual(new_version, version)

    def test_result_page_links_to_result_map(self):
        self.published_scenario.set_status(ScenarioStatus.Status.FINISHED)

        response = self.client.get(
            reverse("scenario-result", kwargs={"pk": self.published_scenario.pk})
        )

        self.assertContains(response, self.map_url(self.published_scenario))

    def test_result_page_omits_seasonal_chart_without_seasonal_data(self):
        self.published_scenario.set_status(ScenarioStatus.Status.FINISHED)

        response = self.client.get(
            reverse("scenario-result", kwargs={"pk": self.published_scenario.pk})
        )

        self.assertIn("productionPerFeedstockBarChart", response.context["charts"])
        self.assertNotIn("seasonalFeedstockBarChart", response.context["charts"])
        self.assertNotContains(response, "Seasonal distribution of feedstocks")


class ScenarioCatchmentSelectorTestCase(TestCase):
    """The scenario form's catchment selector offers the catchments of the
    region chosen in the region selector."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username="owner")
        cls.region = Region.objects.create(
            name="Selected Region", publication_status="published"
        )
        other_region = Region.objects.create(
            name="Other Region", publication_status="published"
        )
        cls.region_catchment = Catchment.objects.create(
            name="Region Catchment",
            region=cls.region,
            publication_status="published",
        )
        cls.drawn_catchment = Catchment.objects.create(
            name="Drawn Catchment",
            owner=cls.owner,
            region=Region.objects.create(name="Drawn Catchment"),
            parent_region=cls.region,
        )
        cls.unrelated_catchment = Catchment.objects.create(
            name="Unrelated Catchment",
            region=other_region,
            parent_region=other_region,
            publication_status="published",
        )

    def get_selector_options(self):
        from ..forms import ScenarioModelForm

        source, lookup = ScenarioModelForm.base_fields["catchment"].config.filter_by
        response = self.client.get(
            reverse("catchment-autocomplete"),
            {"f": f"'{source}__{lookup}={self.region.pk}'"},
        )
        self.assertEqual(response.status_code, 200)
        return {item["name"] for item in response.json()["results"]}

    def test_offers_catchment_of_selected_region(self):
        self.assertIn("Region Catchment", self.get_selector_options())

    def test_offers_own_catchment_drawn_inside_selected_region(self):
        self.client.force_login(self.owner)
        self.assertIn("Drawn Catchment", self.get_selector_options())

    def test_excludes_catchments_of_other_regions(self):
        self.client.force_login(self.owner)
        self.assertNotIn("Unrelated Catchment", self.get_selector_options())

    def test_direct_relational_filter_still_targets_related_field(self):
        response = self.client.get(
            reverse("catchment-autocomplete"),
            {"f": "'region__name=Selected Region'"},
        )
        self.assertEqual(response.status_code, 200)
        names = {item["name"] for item in response.json()["results"]}
        self.assertEqual(names, {"Region Catchment"})
