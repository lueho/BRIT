from maps.models import Catchment, Region
from utils.tests.testcases import AbstractTestCases

from ..models import Scenario

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
