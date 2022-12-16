from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlencode
from rest_framework.test import APITestCase

from utils.tests.testcases import ViewWithPermissionsTestCase
from ..models import Attribute, RegionAttributeValue, Catchment, LauRegion, NutsRegion, Region, GeoDataset


# ----------- Catchment CRUD--------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['add_catchment', 'change_catchment']
    url = reverse('catchment-list')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = Catchment.objects.create(name='Test Catchment')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_add_and_dashboard_button_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse('catchment-create'))
        self.assertNotContains(response, reverse('maps-dashboard'))

    def test_add_and_dashboard_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertContains(response, reverse('catchment-create'))
        self.assertContains(response, reverse('maps-dashboard'))




class CatchmentCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_catchment'

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-create')
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('catchment-create'))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-create'))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-create')
        response = self.client.post(url, data={}, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('catchment-create'))
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Catchment', 'type': 'custom', 'region': Region.objects.create().pk}
        response = self.client.post(reverse('catchment-create'), data, follow=True)
        self.assertRedirects(response, reverse('catchment-detail',
                                               kwargs={'pk': list(response.context.get('messages'))[0].message}))


class CatchmentDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['change_catchment', 'delete_catchment']

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = Catchment.objects.create(name='Test Catchment')

    def test_get_http_200_pk_for_anonymous(self):
        response = self.client.get(reverse('catchment-detail', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'maps/catchment_detail.html')

    def test_edit_and_delete_button_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('catchment-detail', kwargs={'pk': self.catchment.pk}))
        self.assertNotContains(response, reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertNotContains(response, reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))

    def test_edit_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-detail', kwargs={'pk': self.catchment.pk}))
        self.assertContains(response, reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertContains(response, reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))


class CatchmentUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_catchment'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create()
        cls.catchment = Catchment.objects.create(name='Test Catchment')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-update', kwargs={'pk': self.catchment.pk})
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-update', kwargs={'pk': self.catchment.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-update', kwargs={'pk': self.catchment.pk})
        response = self.client.post(url, data={}, follow=True)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('catchment-update', kwargs={'pk': self.catchment.pk}), data={})
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Catchment', 'type': 'custom', 'region': self.region.pk}
        response = self.client.post(reverse('catchment-update', kwargs={'pk': self.catchment.pk}), data, follow=True)
        self.assertRedirects(response, reverse('catchment-detail', kwargs={'pk': self.catchment.pk}))


class CatchmentModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_catchment'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = Catchment.objects.create(name='Test Catchment')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(403, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))
        self.assertEqual(200, response.status_code)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk})
        response = self.client.post(url, data={})
        self.assertRedirects(response, f'{settings.LOGIN_URL}?next={url}')

    def test_post_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}), data={})
        self.assertEqual(403, response.status_code)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('catchment-delete-modal', kwargs={'pk': self.catchment.pk}), {})
        self.assertRedirects(response, reverse('catchment-list'))
        with self.assertRaises(Catchment.DoesNotExist):
            Catchment.objects.get(pk=self.catchment.pk)


# ----------- Catchment API---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentGeometryAPITestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = Catchment.objects.create(name='Test Catchment')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('ajax_catchment_geometries') + '?' + urlencode({'catchment': self.catchment.pk}))
        self.assertEqual(200, response.status_code)


class NutsRegionMapViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(name='Test Region')
        GeoDataset.objects.create(
            name='Test Dataset',
            region=region,
            model_name='NutsRegion'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('NutsRegion'))
        self.assertEqual(response.status_code, 200)


class NutsRegionPedigreeAPITestCase(APITestCase):
    member_permissions = 'add_collection'

    @classmethod
    def setUpTestData(cls):
        uk = NutsRegion.objects.create(
            nuts_id='UK',
            levl_code=0,
            name_latn='United Kingdom'
        )
        Catchment.objects.create(
            region=uk.region_ptr
        )
        ukh = NutsRegion.objects.create(
            nuts_id='UKH',
            levl_code=1,
            name_latn='East of England',
            parent=uk
        )
        Catchment.objects.create(
            region=ukh.region_ptr,
            parent_region=uk.region_ptr
        )
        ukh1 = NutsRegion.objects.create(
            nuts_id='UKH1',
            levl_code=2,
            name_latn='East Anglia',
            parent=ukh
        )
        Catchment.objects.create(
            region=ukh1.region_ptr,
            parent_region=ukh.region_ptr
        )
        ukh2 = NutsRegion.objects.create(
            nuts_id='UKH2',
            levl_code=2,
            name_latn='Bedfordshire and Hertfordshire',
            parent=ukh
        )
        Catchment.objects.create(
            region=ukh2.region_ptr,
            parent_region=ukh.region_ptr
        )
        ukh11 = NutsRegion.objects.create(
            nuts_id='UKH11',
            levl_code=3,
            name_latn='Peterborough',
            parent=ukh1
        )
        Catchment.objects.create(
            region=ukh11.region_ptr,
            parent_region=ukh1.region_ptr
        )
        ukh14 = NutsRegion.objects.create(
            nuts_id='UKH14',
            levl_code=3,
            name_latn='Suffolk',
            parent=ukh1
        )
        Catchment.objects.create(
            region=ukh14.region_ptr,
            parent_region=ukh1.region_ptr
        )
        babergh = LauRegion.objects.create(
            lau_id='E07000200',
            lau_name='Babergh',
            nuts_parent=ukh14
        )
        Catchment.objects.create(
            region=babergh.region_ptr,
            parent_region=ukh14.region_ptr
        )
        ipswich = LauRegion.objects.create(
            lau_id='E07000202',
            lau_name='Ipswich',
            nuts_parent=ukh14
        )
        Catchment.objects.create(
            region=ipswich.region_ptr,
            parent_region=ukh14.region_ptr
        )

    def setUp(self):
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


class NutsRegionSummaryAPIViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        NutsRegion.objects.create(
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

class AttributeListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('attribute-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('attribute-list'))
        self.assertEqual(response.status_code, 200)


class AttributeCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_attribute'

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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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


class AttributeModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_attribute'

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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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


class AttributeDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
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


class AttributeModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
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


class AttributeUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_attribute'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-update', kwargs={'pk': self.attribute.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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


class AttributeModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_attribute'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-update-modal', kwargs={'pk': self.attribute.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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


class AttributeModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_attribute'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.attribute = Attribute.objects.create(
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('attribute-delete-modal', kwargs={'pk': self.attribute.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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

class RegionAttributeValueListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-list'))
        self.assertEqual(response.status_code, 200)


class RegionAttributeValueCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')

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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-create'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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


class RegionAttributeValueModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')

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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-create-modal'))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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


class RegionAttributeValueDetailViewTestCase(ViewWithPermissionsTestCase):
    value = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=region,
            attribute=attribute,
            value=123.312
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-detail', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-detail', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)


class RegionAttributeValueModalDetailViewTestCase(ViewWithPermissionsTestCase):
    value = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=region,
            attribute=attribute,
            value=123.312
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('regionattributevalue-detail-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('regionattributevalue-detail-modal', kwargs={'pk': self.value.pk}))
        self.assertEqual(response.status_code, 200)


class RegionAttributeValueUpdateViewTestCase(ViewWithPermissionsTestCase):
    attribute = None
    region = None
    value = None
    member_permissions = 'change_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=cls.region,
            attribute=cls.attribute,
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-update', kwargs={'pk': self.value.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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


class RegionAttributeValueModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    attribute = None
    region = None
    value = None
    member_permissions = 'change_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.attribute = Attribute.objects.create(name='Test Attribute', unit='Test Unit')
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=cls.region,
            attribute=cls.attribute,
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-update-modal', kwargs={'pk': self.value.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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


class RegionAttributeValueModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    value = None
    member_permissions = 'delete_regionattributevalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.value = RegionAttributeValue.objects.create(
            name='Test Value',
            region=Region.objects.create(name='Test Region'),
            attribute=Attribute.objects.create(name='Test Attribute', unit='Test Unit'),
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

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('regionattributevalue-delete-modal', kwargs={'pk': self.value.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

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
