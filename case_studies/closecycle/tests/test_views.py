from maps.models import Region
from utils.tests.testcases import AbstractTestCases

from ..models import Showcase


class ShowCaseCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False

    model = Showcase

    view_create_name = 'showcase-create'
    view_published_list_name = 'showcase-list'
    view_private_list_name = 'showcase-list-owned'
    view_detail_name = 'showcase-detail'
    view_update_name = 'showcase-update'
    view_delete_name = 'showcase-delete-modal'

    create_object_data = {'name': 'Test Showcase'}
    update_object_data = {'name': 'Updated Test Showcase'}

    @classmethod
    def create_related_objects(cls):
        return {'region': Region.objects.create(name='Test Region')}
