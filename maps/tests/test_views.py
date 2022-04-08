from django.contrib.auth.models import Group, User, Permission
from django.test import TestCase, modify_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from users.models import get_default_owner
from ..models import Attribute, RegionAttributeValue, Catchment, LauRegion, NutsRegion, Region, GeoDataset


class NutsRegionMapViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        region = Region.objects.create(owner=owner, name='Test Region')
        dataset = GeoDataset.objects.create(
            owner=owner,
            name='Test Dataset',
            region=region,
            model_name='NutsRegion'
        )

    def setUp(self):
        pass

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('NutsRegion'))
        self.assertEqual(response.status_code, 200)


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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class NutsRegionSummaryAPIViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        NutsRegion.objects.create(
            owner=owner,
            nuts_id='TE57',
            name_latn='Test NUTS'
        )

    def setUp(self):
        self.region = NutsRegion.objects.get(nuts_id='TE57')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('data.nutsregion-summary'), {'pk': self.region.pk})
        self.assertEqual(response.status_code, 200)

    def test_returns_correct_data(self):
        response = self.client.get(reverse('data.nutsregion-summary'), {'pk': self.region.pk})
        self.assertIn('summaries', response.data)
        self.assertEqual(response.data['summaries'][0]['Name'], self.region.name_latn)


# ----------- Attribute CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AttributeListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('attribute-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AttributeCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_attribute'))
        member.groups.add(members)

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('attribute-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Attribute', 'unit': 'Test Unit'}
        response = self.client.post(reverse('attribute-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AttributeModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_attribute'))
        member.groups.add(members)

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('attribute-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Attribute', 'unit': 'Test Unit'}
        response = self.client.post(reverse('attribute-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AttributeDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.attribute = Attribute.objects.create(
            owner=self.owner,
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('attribute-detail', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-detail', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AttributeModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.attribute = Attribute.objects.create(
            owner=self.owner,
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('attribute-detail-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-detail-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AttributeUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_attribute'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.attribute = Attribute.objects.create(
            owner=self.owner,
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-update', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-update', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-update', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-update', kwargs={'pk': self.attribute.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Attribute', 'unit': self.attribute.unit}
        response = self.client.post(reverse('attribute-update', kwargs={'pk': self.attribute.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Attribute', 'unit': self.attribute.unit}
        response = self.client.post(reverse('attribute-update', kwargs={'pk': self.attribute.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AttributeModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_attribute'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.attribute = Attribute.objects.create(
            owner=self.owner,
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Attribute', 'unit': self.attribute.unit}
        response = self.client.post(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Attribute', 'unit': self.attribute.unit}
        response = self.client.post(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class AttributeModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_attribute'))
        member.groups.add(members)

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.attribute = Attribute.objects.create(
            owner=self.owner,
            name='Test Attribute',
            unit='Test Unit',
            description='This ist a test element'
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        with self.assertRaises(Attribute.DoesNotExist):
            Attribute.objects.get(pk=self.attribute.pk)
        self.assertEqual(response.status_code, 302)


# ----------- Region Attribute Value CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class RegionAttributeValueListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class RegionAttributeValueCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_regionattributevalue'))
        member.groups.add(members)
        Region.objects.create(owner=owner, name='Test Region')
        Attribute.objects.create(owner=owner, name='Test Attribute', unit='Test Unit')

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')
        self.region = Region.objects.get(name='Test Region')
        self.attribute = Attribute.objects.get(name='Test Attribute')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('regionattributevalue-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Attribute Value',
            'region': self.region.id,
            'attribute': self.attribute.id,
            'value': 123.321
        }
        response = self.client.post(reverse('regionattributevalue-create'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class RegionAttributeValueModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_regionattributevalue'))
        member.groups.add(members)
        Region.objects.create(owner=owner, name='Test Region')
        Attribute.objects.create(owner=owner, name='Test Attribute', unit='Test Unit')

    def setUp(self):
        self.owner = get_default_owner()
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')
        self.region = Region.objects.get(name='Test Region')
        self.attribute = Attribute.objects.get(name='Test Attribute')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('regionattributevalue-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Attribute Value',
            'region': self.region.id,
            'attribute': self.attribute.id,
            'value': 123.321
        }
        response = self.client.post(reverse('regionattributevalue-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class RegionAttributeValueDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        Region.objects.create(owner=owner, name='Test Region')
        Attribute.objects.create(owner=owner, name='Test Attribute', unit='Test Unit')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.region = Region.objects.get(name='Test Region')
        self.attribute = Attribute.objects.get(name='Test Attribute')
        self.value = RegionAttributeValue.objects.create(
            owner=self.owner,
            name='Test Value',
            region=self.region,
            attribute=self.attribute,
            value=123.312
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-detail', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-detail', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class RegionAttributeValueModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        Region.objects.create(owner=owner, name='Test Region')
        Attribute.objects.create(owner=owner, name='Test Attribute', unit='Test Unit')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.region = Region.objects.get(name='Test Region')
        self.attribute = Attribute.objects.get(name='Test Attribute')
        self.value = RegionAttributeValue.objects.create(
            owner=self.owner,
            name='Test Value',
            region=self.region,
            attribute=self.attribute,
            value=123.312
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-detail-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-detail-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class RegionAttributeValueUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_regionattributevalue'))
        member.groups.add(members)
        Region.objects.create(owner=owner, name='Test Region')
        Attribute.objects.create(owner=owner, name='Test Attribute', unit='Test Unit')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.region = Region.objects.get(name='Test Region')
        self.attribute = Attribute.objects.get(name='Test Attribute')
        self.value = RegionAttributeValue.objects.create(
            owner=self.owner,
            name='Test Value',
            region=self.region,
            attribute=self.attribute,
            value=123.312
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {
            'name': 'Updated Value',
            'region': self.region.id,
            'attribute': self.attribute.id,
            'value': 456.654
        }
        response = self.client.post(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Value',
            'region': self.region.id,
            'attribute': self.attribute.id,
            'value': 456.654
        }
        response = self.client.post(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}), data=data)
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class RegionAttributeValueModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_regionattributevalue'))
        member.groups.add(members)
        Region.objects.create(owner=owner, name='Test Region')
        Attribute.objects.create(owner=owner, name='Test Attribute', unit='Test Unit')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.region = Region.objects.get(name='Test Region')
        self.attribute = Attribute.objects.get(name='Test Attribute')
        self.value = RegionAttributeValue.objects.create(
            owner=self.owner,
            name='Test Value',
            region=self.region,
            attribute=self.attribute,
            value=123.312
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {
            'name': 'Updated Value',
            'region': self.region.id,
            'attribute': self.attribute.id,
            'value': 456.654
        }
        response = self.client.post(
            reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Value',
            'region': self.region.id,
            'attribute': self.attribute.id,
            'value': 456.654
        }
        response = self.client.post(
            reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class RegionAttributeValueModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_regionattributevalue'))
        member.groups.add(members)
        Region.objects.create(owner=owner, name='Test Region')
        Attribute.objects.create(owner=owner, name='Test Attribute', unit='Test Unit')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.region = Region.objects.get(name='Test Region')
        self.attribute = Attribute.objects.get(name='Test Attribute')
        self.value = RegionAttributeValue.objects.create(
            owner=self.owner,
            name='Test Value',
            region=self.region,
            attribute=self.attribute,
            value=123.312
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        with self.assertRaises(RegionAttributeValue.DoesNotExist):
            RegionAttributeValue.objects.get(pk=self.value.pk)
        self.assertEqual(response.status_code, 302)
