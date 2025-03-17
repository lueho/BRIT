from django.urls import reverse, reverse_lazy

from materials.models import Composition, Material, MaterialComponentGroup, Sample, SampleSeries
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase
from ..models import Culture, Greenhouse, GreenhouseGrowthCycle


class CultureListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_culture']
    url = reverse_lazy('culture-list')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.culture = Culture.objects.create(name='Test Culture', description='Test Description')

    def test_get_http_200_ok_for_anonymous_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class CultureCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Culture
    view_detail_name = 'culture-detail'
    view_update_name = 'culture-update'
    view_delete_name = 'culture-delete-modal'

    create_object_data = {
        'name': 'Test Culture',
        'description': 'Test Description',
    }
    update_object_data = {
        'name': 'Updated Test Culture',
        'description': 'Updated Description',
    }

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(name='Test Material')
        return {
            'residue': SampleSeries.objects.create(name='Test Residue', material=material),
        }


class GreenhouseCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Greenhouse
    view_detail_name = 'greenhouse-detail'
    view_update_name = 'greenhouse-update'
    view_delete_name = 'greenhouse-delete-modal'

    create_object_data = {'name': 'Test Greenhouse'}
    update_object_data = {'name': 'Updated Test Greenhouse'}


class GrowthCycleCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = GreenhouseGrowthCycle
    view_detail_name = 'greenhousegrowthcycle-detail'
    view_update_name = 'greenhousegrowthcycle-update'
    view_delete_name = 'greenhousegrowthcycle-delete-modal'

    create_object_data = {'cycle_number': 1}
    update_object_data = {'cycle_number': 2}

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(name='Test Material')
        sample = Sample.objects.create(
            owner=cls.owner_user,
            name='Published Test Sample',
            material=material,
        )
        group = MaterialComponentGroup.objects.create(name='Test Group')
        return {
            'culture': Culture.objects.create(name='Test Culture'),
            'greenhouse': Greenhouse.objects.create(owner=cls.owner_user, name='Test Greenhouse'),
            'group_settings': Composition.objects.create(name='Test Composition', group=group, sample=sample),
        }

    def get_update_success_url(self, pk=None):
        return reverse('greenhouse-detail', kwargs={'pk': self.related_objects['greenhouse'].pk})
