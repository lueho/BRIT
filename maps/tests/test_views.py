from django.contrib.auth.models import User, Permission
from django.urls import reverse
from rest_framework.test import APITestCase

from ..models import Catchment, LauRegion, NutsRegion


class NutsRegionPedigreeAPITestCase(APITestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        member.user_permissions.add(Permission.objects.get(codename='add_collection'))

        uk = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UK',
            levl_code=0,
            name_latn='United Kingdom'
        )
        Catchment.objects.create(
            owner=owner,
            region=uk.region_ptr
        )
        ukh = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH',
            levl_code=1,
            name_latn='East of England',
            parent=uk
        )
        Catchment.objects.create(
            owner=owner,
            region=ukh.region_ptr,
            parent_region=uk.region_ptr
        )
        ukh1 = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH1',
            levl_code=2,
            name_latn='East Anglia',
            parent=ukh
        )
        Catchment.objects.create(
            owner=owner,
            region=ukh1.region_ptr,
            parent_region=ukh.region_ptr
        )
        ukh2 = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH2',
            levl_code=2,
            name_latn='Bedfordshire and Hertfordshire',
            parent=ukh
        )
        Catchment.objects.create(
            owner=owner,
            region=ukh2.region_ptr,
            parent_region=ukh.region_ptr
        )
        ukh11 = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH11',
            levl_code=3,
            name_latn='Peterborough',
            parent=ukh1
        )
        Catchment.objects.create(
            owner=owner,
            region=ukh11.region_ptr,
            parent_region=ukh1.region_ptr
        )
        ukh14 = NutsRegion.objects.create(
            owner=owner,
            nuts_id='UKH14',
            levl_code=3,
            name_latn='Suffolk',
            parent=ukh1
        )
        Catchment.objects.create(
            owner=owner,
            region=ukh14.region_ptr,
            parent_region=ukh1.region_ptr
        )
        babergh = LauRegion.objects.create(
            owner=owner,
            lau_id='E07000200',
            lau_name='Babergh',
            nuts_parent=ukh14
        )
        Catchment.objects.create(
            owner=owner,
            region=babergh.region_ptr,
            parent_region=ukh14.region_ptr
        )
        ipswich = LauRegion.objects.create(
            owner=owner,
            lau_id='E07000202',
            lau_name='Ipswich',
            nuts_parent=ukh14
        )
        Catchment.objects.create(
            owner=owner,
            region=ipswich.region_ptr,
            parent_region=ukh14.region_ptr
        )

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.uk = Catchment.objects.get(region__nutsregion__nuts_id='UK')
        self.ukh = Catchment.objects.get(region__nutsregion__nuts_id='UKH')
        self.ukh1 = Catchment.objects.get(region__nutsregion__nuts_id='UKH1')
        self.ukh2 = Catchment.objects.get(region__nutsregion__nuts_id='UKH2')
        self.ukh11 = Catchment.objects.get(region__nutsregion__nuts_id='UKH11')
        self.ukh14 = Catchment.objects.get(region__nutsregion__nuts_id='UKH14')
        self.babergh = Catchment.objects.get(region__lauregion__lau_id='E07000200')
        self.ipswich = Catchment.objects.get(region__lauregion__lau_id='E07000202')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('data.nuts_lau_catchment_options'),
                                   {'id': self.uk.id, 'direction': 'children'})
        self.assertEqual(response.status_code, 200)

    def test_get_http_400_bad_request_on_missing_query_parameter_id(self):
        response = self.client.get(reverse('data.nuts_lau_catchment_options'), {'direction': 'children'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['detail'],
            'Query parameter "id" missing. Must provide valid catchment id.')

    def test_get_http_400_bad_request_on_missing_query_parameter_direction(self):
        response = self.client.get(reverse('data.nuts_lau_catchment_options'), {'id': self.uk.id})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['detail'],
            'Missing or wrong query parameter "direction". Options: "parents", "children"'
        )

    def test_get_http_400_bad_request_on_wrong_query_parameter_direction(self):
        response = self.client.get(reverse('data.nuts_lau_catchment_options'), {'id': self.uk.id, 'direction': 'south'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['detail'],
            'Missing or wrong query parameter "direction". Options: "parents", "children"'
        )

    def test_get_http_404_bad_request_on_non_existing_region_id(self):
        response = self.client.get(reverse('data.nuts_lau_catchment_options'), {'id': 0, 'direction': 'parents'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['detail'], 'A NUTS region with the provided id does not exist.')

    def test_get_response_contains_level_4_in_children_if_input_is_level_3(self):
        response = self.client.get(reverse('data.nuts_lau_catchment_options'),
                                   {'id': self.ukh14.id, 'direction': 'children'})
        self.assertIn('id_level_4', response.data)
