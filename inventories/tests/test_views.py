from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from maps.models import Catchment, GeoDataset, Region
from materials.models import Material, Sample, SampleSeries
from utils.object_management.models import User
from utils.object_management.views import (
    UserCreatedObjectAutocompleteView,
    get_tomselect_filter_pairs,
    get_tomselect_filter_value,
)
from utils.tests.testcases import AbstractTestCases

from ..models import (
    InventoryAlgorithm,
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
        cls.user = User.objects.create_user(username="ac_user")
        cls.region = Region.objects.create(name="AC Region")
        cls.scenario = Scenario.objects.create(name="AC Scenario", region=cls.region)
        cls.geodataset = GeoDataset.objects.create(name="AC Dataset", region=cls.region)
        algorithm = InventoryAlgorithm.objects.create(
            name="AC Algorithm", geodataset=cls.geodataset
        )
        algorithm.feedstocks.add(cls.target_material)
        cls.series = SampleSeries.objects.create(
            name="AC Series", material=cls.target_material, owner=cls.user
        )

    def test_apply_filters_uses_material_id_not_series_id(self):
        self.assertNotEqual(
            self.series.id,
            self.target_material.id,
            "Test requires SampleSeries.id != Material.id to catch the bug",
        )
        view = ScenarioGeoDataSetAutocompleteView()
        view.request = SimpleNamespace(user=self.user)
        view.filter_by = f"feedstock_id='{self.series.inventory_input.id}'"
        view.filters_by = []
        view.exclude_by = f"scenario_id='{self.scenario.id}'"
        view.excludes_by = []

        result_qs = view.apply_filters(GeoDataset.objects.all())
        self.assertIn(self.geodataset, result_qs)

    def test_apply_filters_rejects_inaccessible_private_input(self):
        other = User.objects.create_user(username="ac_other")
        private_series = SampleSeries.objects.create(
            name="AC Private", material=self.target_material, owner=other
        )
        view = ScenarioGeoDataSetAutocompleteView()
        view.request = SimpleNamespace(user=self.user)
        view.filter_by = f"feedstock_id='{private_series.inventory_input.id}'"
        view.filters_by = []
        view.exclude_by = f"scenario_id='{self.scenario.id}'"
        view.excludes_by = []

        result_qs = view.apply_filters(GeoDataset.objects.all())
        self.assertFalse(result_qs.exists())


class ScenarioInventoryAlgorithmAutocompleteAccessTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="alg_ac_user")
        cls.other = User.objects.create_user(username="alg_ac_other")
        cls.material = Material.objects.create(name="Alg AC Material")
        cls.region = Region.objects.create(name="Alg AC Region")
        cls.geodataset = GeoDataset.objects.create(
            name="Alg AC Dataset", region=cls.region
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="Alg AC Algorithm", geodataset=cls.geodataset
        )
        cls.algorithm.feedstocks.add(cls.material)
        cls.own_series = SampleSeries.objects.create(
            name="Alg AC Own", material=cls.material, owner=cls.user
        )
        cls.private_series = SampleSeries.objects.create(
            name="Alg AC Private", material=cls.material, owner=cls.other
        )

    def make_view(self, feedstock_id):
        view = ScenarioInventoryAlgorithmAutocompleteView()
        view.request = SimpleNamespace(user=self.user)
        view.filter_by = f"geodataset_id='{self.geodataset.id}'"
        view.filters_by = []
        view.exclude_by = f"feedstock_id='{feedstock_id}'"
        view.excludes_by = []
        return view

    def test_own_input_returns_matching_algorithms(self):
        view = self.make_view(self.own_series.inventory_input.id)
        result_qs = view.apply_filters(InventoryAlgorithm.objects.all())
        self.assertIn(self.algorithm, result_qs)

    def test_other_users_private_input_returns_none(self):
        view = self.make_view(self.private_series.inventory_input.id)
        result_qs = view.apply_filters(InventoryAlgorithm.objects.all())
        self.assertFalse(result_qs.exists())


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
        cls.algorithm.feedstocks.add(material)

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
                    "feedstock": self.feedstock.inventory_input.pk,
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


class InventoryInputAutocompleteTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="ii_ac_owner", password="pw")
        cls.other = User.objects.create_user(username="ii_ac_other", password="pw")
        cls.material = Material.objects.create(
            owner=cls.owner, name="II AC Material", publication_status="published"
        )
        cls.series = SampleSeries.objects.create(
            owner=cls.owner,
            name="II AC Series",
            material=cls.material,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner,
            name="II AC Sample",
            material=cls.material,
            standalone=True,
            publication_status="published",
        )
        cls.private_series = SampleSeries.objects.create(
            owner=cls.other,
            name="II AC Other Private",
            material=cls.material,
            publication_status="private",
        )
        cls.url = reverse("inventoryinput-autocomplete")

    def result_ids(self, response):
        self.assertEqual(response.status_code, 200)
        return {item["id"] for item in response.json()["results"]}

    def test_anonymous_sees_only_published_inputs(self):
        ids = self.result_ids(self.client.get(self.url))
        self.assertIn(self.series.inventory_input.pk, ids)
        self.assertIn(self.sample.inventory_input.pk, ids)
        self.assertNotIn(self.private_series.inventory_input.pk, ids)

    def test_owner_sees_own_inputs_but_not_other_private(self):
        self.client.force_login(self.owner)
        ids = self.result_ids(self.client.get(self.url))
        self.assertIn(self.series.inventory_input.pk, ids)
        self.assertNotIn(self.private_series.inventory_input.pk, ids)

    def test_other_user_sees_own_private_input(self):
        self.client.force_login(self.other)
        ids = self.result_ids(self.client.get(self.url))
        self.assertIn(self.private_series.inventory_input.pk, ids)

    def test_search_matches_sample_series_and_material_names(self):
        ids = self.result_ids(self.client.get(self.url, {"q": "II AC Series"}))
        self.assertIn(self.series.inventory_input.pk, ids)
        ids = self.result_ids(self.client.get(self.url, {"q": "II AC Sample"}))
        self.assertIn(self.sample.inventory_input.pk, ids)
        ids = self.result_ids(self.client.get(self.url, {"q": "II AC Material"}))
        self.assertIn(self.series.inventory_input.pk, ids)
        self.assertIn(self.sample.inventory_input.pk, ids)

    def test_labels_distinguish_kinds(self):
        response = self.client.get(self.url)
        labels = {item["id"]: item["name"] for item in response.json()["results"]}
        self.assertTrue(labels[self.series.inventory_input.pk].startswith("Series:"))
        self.assertTrue(labels[self.sample.inventory_input.pk].startswith("Sample:"))

    def test_scenario_context_limits_to_eligible_inputs(self):
        region = Region.objects.create(name="II AC Eligible Region")
        scenario = Scenario.objects.create(
            name="II AC Eligible Scenario", region=region
        )
        geodataset = GeoDataset.objects.create(
            name="II AC Eligible Dataset", region=region
        )
        algorithm = InventoryAlgorithm.objects.create(
            name="II AC Eligible Algorithm", geodataset=geodataset
        )
        algorithm.feedstocks.add(self.material)

        ids = self.result_ids(
            self.client.get(self.url, {"f": f"scenario_id='{scenario.pk}'"})
        )
        self.assertIn(self.series.inventory_input.pk, ids)
        self.assertNotIn(self.sample.inventory_input.pk, ids)

        empty_scenario = Scenario.objects.create(
            name="II AC Empty Scenario",
            region=Region.objects.create(name="II AC Empty Region"),
        )
        ids = self.result_ids(
            self.client.get(self.url, {"f": f"scenario_id='{empty_scenario.pk}'"})
        )
        self.assertEqual(ids, set())


class ScenarioConfigurationInventoryInputTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="config_owner", password="pw")
        cls.other = User.objects.create_user(username="config_other", password="pw")
        change_perm = Permission.objects.get(codename="change_scenario")
        cls.owner.user_permissions.add(change_perm)
        region = Region.objects.create(
            name="Config Region", publication_status="published"
        )
        catchment = Catchment.objects.create(
            name="Config Catchment",
            region=region,
            parent_region=region,
            publication_status="published",
        )
        cls.scenario = Scenario.objects.create(
            name="Config Scenario",
            owner=cls.owner,
            region=region,
            catchment=catchment,
        )
        cls.material = Material.objects.create(
            owner=cls.owner, name="Config Material", publication_status="published"
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner,
            name="Config Sample",
            material=cls.material,
            standalone=True,
            publication_status="published",
        )
        cls.other_private_sample = Sample.objects.create(
            owner=cls.other,
            name="Config Other Private Sample",
            material=cls.material,
            standalone=True,
        )
        geodataset = GeoDataset.objects.create(
            name="Config Dataset", owner=cls.owner, region=region
        )
        cls.static_algorithm = InventoryAlgorithm.objects.create(
            name="Config Static Algorithm",
            geodataset=geodataset,
            supports_standalone_samples=True,
        )
        cls.static_algorithm.feedstocks.add(cls.material)
        cls.series_algorithm = InventoryAlgorithm.objects.create(
            name="Config Series Algorithm", geodataset=geodataset
        )
        cls.series_algorithm.feedstocks.add(cls.material)

    def test_post_add_configuration_with_sample_input(self):
        self.client.force_login(self.owner)
        url = reverse("scenario-add-configuration", kwargs={"pk": self.scenario.pk})
        response = self.client.post(
            url,
            {
                "feedstock": self.sample.inventory_input.pk,
                "inventory_algorithm": self.static_algorithm.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario,
                feedstock=self.sample.inventory_input,
                inventory_algorithm=self.static_algorithm,
            ).exists()
        )

    def test_post_rejects_other_users_private_input(self):
        self.client.force_login(self.owner)
        url = reverse("scenario-add-configuration", kwargs={"pk": self.scenario.pk})
        response = self.client.post(
            url,
            {
                "feedstock": self.other_private_sample.inventory_input.pk,
                "inventory_algorithm": self.static_algorithm.pk,
            },
        )
        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario,
                feedstock=self.other_private_sample.inventory_input,
            ).exists()
        )


class ScenarioAlgorithmConfigurationUpdateViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="update_owner", password="pw")
        cls.other = User.objects.create_user(username="update_other", password="pw")
        change_perm = Permission.objects.get(codename="change_scenario")
        cls.owner.user_permissions.add(change_perm)
        region = Region.objects.create(
            name="Update Region", publication_status="published"
        )
        catchment = Catchment.objects.create(
            name="Update Catchment",
            region=region,
            parent_region=region,
            publication_status="published",
        )
        cls.scenario = Scenario.objects.create(
            name="Update Scenario",
            owner=cls.owner,
            region=region,
            catchment=catchment,
        )
        cls.material = Material.objects.create(
            owner=cls.owner, name="Update Material", publication_status="published"
        )
        cls.series = SampleSeries.objects.create(
            owner=cls.owner,
            name="Update Series",
            material=cls.material,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner,
            name="Update Sample",
            material=cls.material,
            standalone=True,
            publication_status="published",
        )
        cls.other_private_sample = Sample.objects.create(
            owner=cls.other,
            name="Update Other Private",
            material=cls.material,
            standalone=True,
        )
        cls.geodataset = GeoDataset.objects.create(
            name="Update Dataset", owner=cls.owner, region=region
        )
        cls.series_algorithm = InventoryAlgorithm.objects.create(
            name="Update Series Algorithm", geodataset=cls.geodataset
        )
        cls.series_algorithm.feedstocks.add(cls.material)
        cls.static_algorithm = InventoryAlgorithm.objects.create(
            name="Update Static Algorithm",
            geodataset=cls.geodataset,
            supports_standalone_samples=True,
        )
        cls.static_algorithm.feedstocks.add(cls.material)

    def setUp(self):
        ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=self.series.inventory_input,
            geodataset=self.geodataset,
            inventory_algorithm=self.series_algorithm,
        )
        self.url = reverse(
            "scenario-update-config",
            kwargs={
                "scenario_pk": self.scenario.pk,
                "feedstock_pk": self.series.inventory_input.pk,
                "algorithm_pk": self.series_algorithm.pk,
            },
        )

    def current_config_exists(self):
        return ScenarioInventoryConfiguration.objects.filter(
            scenario=self.scenario,
            feedstock=self.series.inventory_input,
            inventory_algorithm=self.series_algorithm,
        ).exists()

    def test_rejects_inaccessible_replacement_and_keeps_config(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "feedstock": self.other_private_sample.inventory_input.pk,
                "inventory_algorithm": self.static_algorithm.pk,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.current_config_exists())

    def test_rejects_unsupported_replacement_and_keeps_config(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "feedstock": self.sample.inventory_input.pk,
                "inventory_algorithm": self.series_algorithm.pk,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.current_config_exists())

    def test_valid_replacement_swaps_config(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {
                "feedstock": self.sample.inventory_input.pk,
                "inventory_algorithm": self.static_algorithm.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.current_config_exists())
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario,
                feedstock=self.sample.inventory_input,
                inventory_algorithm=self.static_algorithm,
            ).exists()
        )
