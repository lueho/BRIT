from distributions.models import TemporalDistribution, Timestep
from utils.tests.testcases import AbstractTestCases


class AuthorCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False
    public_list_view = False
    private_list_view = False
    create_view = False
    detail_view = False
    modal_detail_view = True
    update_view = False
    delete_view = False

    model = Timestep

    view_modal_detail_name = 'timestep-detail-modal'

    @classmethod
    def create_published_object(cls):
        data = {
            'name': 'Published Test Timestep',
            'order': 1,
            'publication_status': 'published',
        }
        data.update(cls.related_objects)
        return cls.model.objects.create(owner=cls.owner_user, **data)

    @classmethod
    def create_unpublished_object(cls):
        data = {
            'name': 'Private Test Timestep',
            'order': 1,
            'publication_status': 'private',
        }
        data.update(cls.related_objects)
        return cls.model.objects.create(owner=cls.owner_user, **data)

    @classmethod
    def create_related_objects(cls):
        return {
            'distribution': TemporalDistribution.objects.create(name='Test Temporal Distribution'),
        }
