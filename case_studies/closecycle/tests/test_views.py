from maps.models import Region
from utils.tests.testcases import AbstractTestCases

from ..models import Showcase


class ShowCaseCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Showcase
    view_detail_name = 'showcase-detail'
    view_update_name = 'showcase-update'
    view_delete_name = 'showcase-delete-modal'

    create_object_data = {'name': 'Test Showcase'}
    update_object_data = {'name': 'Updated Test Showcase'}

    @classmethod
    def create_related_objects(cls):
        return {'region': Region.objects.create(name='Test Region')}
