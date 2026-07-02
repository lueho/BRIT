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
    RunningTask,
    Scenario,
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
        cls.geodataset = GeoDataset.objects.create(name="AC Dataset", region=cls.region)
        algorithm = InventoryAlgorithm.objects.create(
            name="AC Algorithm", geodataset=cls.geodataset
        )
        algorithm.feedstocks.add(cls.target_material)
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
        cls.owner_a = User.objects.create_user(username="owner_a", password="pass")
        cls.owner_b = User.objects.create_user(username="owner_b", password="pass")
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

    def test_post_uses_url_pk_not_body_scenario(self):
        """post() must use the URL pk, ignoring any 'scenario' field in POST body."""
        from unittest.mock import patch

        self.client.force_login(self.owner_a)
        url = reverse(
            "scenario-add-configuration",
            kwargs={"pk": self.scenario_a.pk},
        )
        # Patch add_inventory_algorithm to capture which scenario it was called on
        with patch.object(Scenario, "add_inventory_algorithm") as mock_add:
            mock_add.return_value = None
            # Supply scenario_b in POST body, but the view should use scenario_a
            # from the URL pk. We need valid-looking POST data for feedstock/algo.
            from materials.models import SampleSeries

            with self.assertRaises(SampleSeries.DoesNotExist):
                self.client.post(url, {"scenario": self.scenario_b.pk})
            # add_inventory_algorithm should NOT have been called with scenario_b
            mock_add.assert_not_called()
