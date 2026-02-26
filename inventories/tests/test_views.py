from types import SimpleNamespace

from django.test import SimpleTestCase

from maps.models import Catchment, Region
from utils.object_management.views import (
    get_tomselect_filter_pairs,
    get_tomselect_filter_value,
)
from utils.tests.testcases import AbstractTestCases

from ..models import Scenario
from ..views import (
    InventoryAlgorithmAutocompleteView,
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
