import json
from collections import OrderedDict

from django.forms.formsets import BaseFormSet
from django.http import JsonResponse
from django.http.request import QueryDict, MultiValueDict
from django.test import RequestFactory
from django.urls import reverse
from mock import Mock, patch

from utils.models import Property
from utils.tests.testcases import ViewWithPermissionsTestCase
from maps.models import Catchment, Region
from materials.models import Material, MaterialCategory, Sample, SampleSeries
from .. import views
from ..forms import CollectionModelForm, BaseWasteFlyerUrlFormSet
from ..models import (Collection, Collector, CollectionSystem, WasteCategory, WasteComponent, WasteFlyer, WasteStream,
                      CollectionFrequency, CollectionPropertyValue, AggregatedCollectionPropertyValue)


# ----------- Collection Frequency CRUD --------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class CollectionFrequencyListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-list'))
        self.assertEqual(response.status_code, 200)


class CollectionFrequencyCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_collectionfrequency'

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collectionfrequency-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collectionfrequency-create'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collectionfrequency-create'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Frequency'}
        response = self.client.post(reverse('collectionfrequency-create'), data=data)
        self.assertEqual(response.status_code, 302)


class CollectionFrequencyModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_collectionfrequency'

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-create-modal'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-create-modal'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collectionfrequency-create-modal'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collectionfrequency-create-modal'), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collectionfrequency-create-modal'), data={})
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {'name': 'Test Frequency'}
        response = self.client.post(reverse('collectionfrequency-create-modal'), data=data)
        self.assertEqual(response.status_code, 302)


class CollectionFrequencyDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.frequency = CollectionFrequency.objects.create(name='Test Frequency')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-detail', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-detail', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)


class CollectionFrequencyModalDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.frequency = CollectionFrequency.objects.create(name='Test Frequency')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-detail-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-detail-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)


class CollectionFrequencyUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_collectionfrequency'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.frequency = CollectionFrequency.objects.create(name='Test Frequency')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-update', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-update', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collectionfrequency-update', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collectionfrequency-update', kwargs={'pk': self.frequency.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Frequency'}
        response = self.client.post(reverse('collectionfrequency-update', kwargs={'pk': self.frequency.pk}), data=data)
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Updated Test Frequency'}
        response = self.client.post(reverse('collectionfrequency-update', kwargs={'pk': self.frequency.pk}), data=data)
        self.assertEqual(response.status_code, 302)


class CollectionFrequencyModalUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_collectionfrequency'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.frequency = CollectionFrequency.objects.create(name='Test Frequency')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-update-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-update-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collectionfrequency-update-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collectionfrequency-update-modal', kwargs={'pk': self.frequency.pk}), data={})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        data = {'name': 'Updated Test Frequency'}
        response = self.client.post(
            reverse('collectionfrequency-update-modal', kwargs={'pk': self.frequency.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {'name': 'Update Test Frequency'}
        response = self.client.post(
            reverse('collectionfrequency-update-modal', kwargs={'pk': self.frequency.pk}),
            data=data
        )
        self.assertEqual(response.status_code, 302)


class CollectionFrequencyModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_collectionfrequency'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.frequency = CollectionFrequency.objects.create(name='Test Frequency')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-delete-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-delete-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collectionfrequency-delete-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collectionfrequency-delete-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collectionfrequency-delete-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('collectionfrequency-delete-modal', kwargs={'pk': self.frequency.pk}))
        with self.assertRaises(CollectionFrequency.DoesNotExist):
            CollectionFrequency.objects.get(pk=self.frequency.pk)
        self.assertEqual(response.status_code, 302)


# ----------- CollectionPropertyValue CRUD --------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionPropertyValueCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_collectionpropertyvalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.collection = Collection.objects.create(name='Test Collection')
        cls.prop = Property.objects.create(name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'collection': self.collection.pk,
            'property': self.prop.pk,
            'year': 2022,
            'average': 123.5,
            'standard_deviation': 12.6
        }
        response = self.client.post(reverse('collectionpropertyvalue-create'), data=data)
        self.assertEqual(response.status_code, 302)


class CollectionPropertyValueDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ('change_collectionpropertyvalue', 'delete_collectionpropertyvalue')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        collection = Collection.objects.create(name='Test Collection')
        prop = Property.objects.create(name='Test Property', unit='Test Unit')
        cls.val = CollectionPropertyValue.objects.create(
            collection=collection,
            property=prop,
            average=123.5,
            standard_deviation=12.54
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('collectionpropertyvalue-detail', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 200)

    def test_template_contains_edit_and_delete_button_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collectionpropertyvalue-detail', kwargs={'pk': self.val.pk}))
        self.assertContains(response, reverse('collectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertContains(response, reverse('collectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))

    def test_template_does_not_contain_edit_and_delete_button_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionpropertyvalue-detail', kwargs={'pk': self.val.pk}))
        self.assertNotContains(response, reverse('collectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertNotContains(response, reverse('collectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionpropertyvalue-detail', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 200)


class CollectionPropertyValueUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_collectionpropertyvalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.collection = Collection.objects.create(name='Test Collection')
        cls.prop = Property.objects.create(name='Test Property', unit='Test Unit')
        cls.val = CollectionPropertyValue.objects.create(
            collection=cls.collection,
            property=cls.prop,
            average=123.5,
            standard_deviation=12.54
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'collection': self.collection.pk,
            'property': self.prop.pk,
            'year': 2022,
            'average': 123.5,
            'standard_deviation': 32.2
        }
        response = self.client.post(reverse('collectionpropertyvalue-update', kwargs={'pk': self.val.pk}), data=data)
        self.assertEqual(response.status_code, 302)


class CollectionPropertyValueModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_collectionpropertyvalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        collection = Collection.objects.create(name='Test Collection')
        prop = Property.objects.create(name='Test Property', unit='Test Unit')
        cls.val = CollectionPropertyValue.objects.create(
            collection=collection,
            property=prop,
            average=123.5,
            standard_deviation=12.54
        )

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('collectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        with self.assertRaises(CollectionPropertyValue.DoesNotExist):
            CollectionPropertyValue.objects.get(pk=self.val.pk)
        self.assertEqual(response.status_code, 302)


# ----------- AggregatedCollectionPropertyValue CRUD --------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AggregatedCollectionPropertyValueCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_aggregatedcollectionpropertyvalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Collection.objects.create(name='Test Collection 1')
        Collection.objects.create(name='Test Collection 2')
        cls.prop = Property.objects.create(name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-create'))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'collections': [collection.pk for collection in Collection.objects.all()],
            'property': self.prop.pk,
            'year': 2022,
            'average': 123.5,
            'standard_deviation': 12.6
        }
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-create'), data=data)
        self.assertEqual(response.status_code, 302)


class AggregatedCollectionPropertyValueDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ('change_aggregatedcollectionpropertyvalue', 'delete_aggregatedcollectionpropertyvalue')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.prop = Property.objects.create(name='Test Property', unit='Test Unit')
        cls.val = AggregatedCollectionPropertyValue.objects.create(
            property=cls.prop,
            average=123.5,
            standard_deviation=12.54
        )
        cls.val.collections.add(Collection.objects.create(name='Test Collection 1'))
        cls.val.collections.add(Collection.objects.create(name='Test Collection 2'))

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-detail', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 200)

    def test_template_contains_edit_and_delete_button_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-detail', kwargs={'pk': self.val.pk}))
        self.assertContains(response, reverse('aggregatedcollectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertContains(response, reverse('aggregatedcollectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))

    def test_template_does_not_contain_edit_and_delete_button_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-detail', kwargs={'pk': self.val.pk}))
        self.assertNotContains(response, reverse('aggregatedcollectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertNotContains(response, reverse('aggregatedcollectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-detail', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 200)


class AggregatedCollectionPropertyValueUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_aggregatedcollectionpropertyvalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.prop = Property.objects.create(name='Test Property', unit='Test Unit')
        cls.val = AggregatedCollectionPropertyValue.objects.create(
            property=cls.prop,
            average=123.5,
            standard_deviation=12.54
        )
        cls.val.collections.add(Collection.objects.create(name='Test Collection 1'))
        cls.val.collections.add(Collection.objects.create(name='Test Collection 2'))

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-update', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            'collections': [self.val.collections.first().pk],
            'property': self.prop.pk,
            'year': 2022,
            'average': 555,
            'standard_deviation': 32.2
        }
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-update', kwargs={'pk': self.val.pk}), data=data)
        self.assertEqual(response.status_code, 302)


class AggregatedCollectionPropertyValueModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_aggregatedcollectionpropertyvalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        prop = Property.objects.create(name='Test Property', unit='Test Unit')
        cls.val = AggregatedCollectionPropertyValue.objects.create(
            property=prop,
            average=123.5,
            standard_deviation=12.54
        )
        cls.val.collections.add(Collection.objects.create())
        cls.val.collections.add(Collection.objects.create())

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('aggregatedcollectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        with self.assertRaises(AggregatedCollectionPropertyValue.DoesNotExist):
            AggregatedCollectionPropertyValue.objects.get(pk=self.val.pk)
        self.assertEqual(response.status_code, 302)

    def test_collections_are_not_deleted(self):
        self.client.force_login(self.member)
        self.assertEqual(Collection.objects.count(), 2)
        response = self.client.post(reverse('aggregatedcollectionpropertyvalue-delete-modal', kwargs={'pk': self.val.pk}))
        self.assertEqual(Collection.objects.count(), 2)
        self.assertEqual(response.status_code, 302)


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_collection'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        MaterialCategory.objects.create(name='Biowaste component')
        material1 = WasteComponent.objects.create(name='Test material 1')
        material2 = WasteComponent.objects.create(name='Test material 2')
        waste_stream = WasteStream.objects.create(
            name='Test waste stream',
            category=WasteCategory.objects.create(name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(name='Test Frequency')
        cls.collection = Collection.objects.create(
            name='collection1',
            catchment=Catchment.objects.create(name='Test catchment'),
            collector=Collector.objects.create(name='Test collector'),
            collection_system=CollectionSystem.objects.create(name='Test system'),
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=frequency,
            description='This is a test case.'
        )
        cls.collection.flyers.add(waste_flyer)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collection-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collection-create'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_group_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collection-create'), kwargs={})
        self.assertEqual(response.status_code, 302)

    def test_post_get_formset_kwargs_fetches_correct_parent_object(self):
        request = RequestFactory().post(reverse('collection-create'))
        request.user = self.member
        view = views.CollectionCreateView()
        view.setup(request)
        view.object = self.collection
        formset_kwargs = view.get_formset_kwargs()
        self.assertEqual(formset_kwargs['parent_object'], self.collection)

    def test_get_formset_has_correct_queryset(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-create'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['formset'].forms), 1)

    def test_post_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collection-create'), kwargs={})
        self.assertEqual(response.status_code, 403)

    def test_post_with_missing_data_errors(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse('collection-create'),
            data={'connection_rate_year': 123}
        )
        self.assertEqual(response.status_code, 200)

        error_msg = 'This field is required.'
        self.assertTrue(error_msg in response.context['form'].errors['catchment'])
        self.assertTrue(error_msg in response.context['form'].errors['collector'])
        self.assertTrue(error_msg in response.context['form'].errors['collection_system'])
        self.assertTrue(error_msg in response.context['form'].errors['waste_category'])
        self.assertTrue(error_msg in response.context['form'].errors['allowed_materials'])
        self.assertTrue('Year needs to be in YYYY format.' in response.context['form'].errors['connection_rate_year'])

    def test_post_with_valid_form_data(self):
        self.assertEqual(Collection.objects.count(), 1)
        self.client.force_login(self.member)
        response = self.client.post(
            reverse('collection-create'),
            data={
                'catchment': Catchment.objects.first().id,
                'collector': Collector.objects.first().id,
                'collection_system': CollectionSystem.objects.first().id,
                'waste_category': WasteCategory.objects.first().id,
                'allowed_materials': [c.id for c in WasteComponent.objects.all()],
                'connection_rate': 0.7,
                'connection_rate_year': 2020,
                'frequency': CollectionFrequency.objects.first().id,
                'description': 'This is a test case that should pass!',
                'form-INITIAL_FORMS': '0',
                'form-TOTAL_FORMS': '2',
                'form-0-url': 'https://www.test-flyer.org',
                'form-0-id': '',
                'form-1-url': '',
                'form-1-id': ''
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Collection.objects.count(), 2)


class CollectionCopyViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_collection'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        MaterialCategory.objects.create(name='Biowaste component')
        material1 = WasteComponent.objects.create(name='Test material 1')
        material2 = WasteComponent.objects.create(name='Test material 2')
        waste_stream = WasteStream.objects.create(
            name='Test waste stream',
            category=WasteCategory.objects.create(name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        cls.flyer = WasteFlyer.objects.create(
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(name='Test Frequency')
        cls.collection = Collection.objects.create(
            name='collection1',
            catchment=Catchment.objects.create(name='Test catchment'),
            collector=Collector.objects.create(name='Test collector'),
            collection_system=CollectionSystem.objects.create(name='Test system'),
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=frequency,
            description='This is a test case.'
        )
        cls.collection.flyers.add(cls.flyer)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_group_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 200)

    def test_get_object(self):
        request = RequestFactory().get(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        view = views.CollectionCopyView()
        view.setup(request)
        view.kwargs = {'pk': self.collection.id}
        self.assertEqual(view.get_object(), self.collection)

    def test_get_get_initial_handles_missing_data(self):
        self.collection.collector = None
        self.collection.catchment = None
        self.collection.collection_system = None
        self.collection.waste_stream = None
        self.collection.connection_rate = None
        self.collection.connection_rate_year = None
        self.collection.frequency = None
        self.collection.description = None
        self.collection.save()
        request = RequestFactory().get(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        view = views.CollectionCopyView()
        view.setup(request)
        view.kwargs = {'pk': self.collection.id}
        view.original_object = view.get_original_object()
        expected = {}
        initial = view.get_initial()
        self.assertEqual(set(expected.keys()), set(initial.keys()))
        for key, value in expected.items():
            if key == 'allowed_materials':
                self.assertIn(key, initial)
                self.assertEqual(set(expected[key]), set(initial[key]))
            else:
                self.assertIn(key, initial)
                self.assertEqual(value, initial[key])

    def test_get_get_formset_kwargs_fetches_and_parent_object(self):
        request = RequestFactory().get(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        view = views.CollectionCopyView()
        view.setup(request)
        view.kwargs = {'pk': self.collection.id}
        view.original_object = view.get_original_object()
        expected = {
            'parent_object': self.collection
        }
        self.assertDictEqual(expected, view.get_formset_kwargs())

    def test_get_formset_has_correct_queryset(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['formset'].forms), len(self.collection.flyers.all()) + 1)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_member(self):
        self.client.force_login(self.member)
        data = {
            'catchment': Catchment.objects.first().id,
            'collector': Collector.objects.create(name='New Test Collector').id,
            'collection_system': CollectionSystem.objects.first().id,
            'waste_category': WasteCategory.objects.first().id,
            'allowed_materials': [c.id for c in WasteComponent.objects.all()],
            'connection_rate': 0.7,
            'connection_rate_year': 2020,
            'frequency': CollectionFrequency.objects.first().id,
            'description': 'This is a test case that should pass!',
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '0',
        }
        response = self.client.post(reverse('collection-copy', kwargs={'pk': self.collection.id}), data=data)
        self.assertEqual(response.status_code, 302)

    def test_post_creates_new_copy(self):
        self.client.force_login(self.member)
        self.assertEqual(Collection.objects.count(), 1)
        get_response = self.client.get(reverse('collection-copy', kwargs={'pk': self.collection.pk}))
        initial = get_response.context['form'].initial
        data = {
            'catchment': initial['catchment'].id,
            'collector': initial['collector'].id,
            'collection_system': initial['collection_system'].id,
            'waste_category': initial['waste_category'].id,
            'allowed_materials': [c.id for c in initial['allowed_materials']],
            'connection_rate': initial['connection_rate'],
            'connection_rate_year': initial['connection_rate_year'],
            'frequency': initial['frequency'].id,
            'description': initial['description'],
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '0',
        }
        post_response = self.client.post(reverse('collection-copy', kwargs={'pk': self.collection.pk}), data=data)
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(Collection.objects.count(), 2)

    def test_post_copy_is_still_associated_with_unchanged_original_flyers(self):
        self.client.force_login(self.member)
        self.assertEqual(Collection.objects.count(), 1)
        get_response = self.client.get(reverse('collection-copy', kwargs={'pk': self.collection.pk}))
        initial = get_response.context['form'].initial
        data = {
            'catchment': initial['catchment'].id,
            'collector': initial['collector'].id,
            'collection_system': initial['collection_system'].id,
            'waste_category': initial['waste_category'].id,
            'allowed_materials': [c.id for c in initial['allowed_materials']],
            'connection_rate': initial['connection_rate'],
            'connection_rate_year': initial['connection_rate_year'],
            'frequency': initial['frequency'].id,
            'description': 'This is the copy.',
            'form-INITIAL_FORMS': '1',
            'form-TOTAL_FORMS': '1',
            'form-0-url': self.flyer.url,
            'form-0-id': self.flyer.id,
        }
        self.client.post(reverse('collection-copy', kwargs={'pk': self.collection.pk}), data=data)
        copy = Collection.objects.get(description='This is the copy.')
        self.assertEqual(copy.flyers.count(), 1)
        flyer = copy.flyers.first()
        self.assertEqual(flyer.url, self.flyer.url)


class CollectionUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_collection'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        MaterialCategory.objects.create(name='Biowaste component')
        material1 = WasteComponent.objects.create(name='Test material 1')
        material2 = WasteComponent.objects.create(name='Test material 2')
        waste_stream = WasteStream.objects.create(
            name='Test waste stream',
            category=WasteCategory.objects.create(name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(name='Test Frequency')
        cls.collection = Collection.objects.create(
            name='collection1',
            catchment=Catchment.objects.create(name='Test catchment'),
            collector=Collector.objects.create(name='Test collector'),
            collection_system=CollectionSystem.objects.create(name='Test system'),
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=frequency,
            description='This is a test case.'
        )
        cls.collection.flyers.add(waste_flyer)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collection-update', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collection-update', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_group_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-update', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 200)

    def test_get_get_formset_kwargs(self):
        kwargs = {'pk': self.collection.pk}
        request = RequestFactory().get(reverse('collection-update', kwargs=kwargs))
        request.user = self.member
        view = views.CollectionUpdateView()
        view.setup(request)
        view.kwargs = kwargs
        view.object = self.collection
        expected_formset_kwargs = {
            'parent_object': self.collection,
            'owner': self.member
        }
        self.assertDictEqual(expected_formset_kwargs, view.get_formset_kwargs())

    def test_post_get_formset_kwargs(self):
        kwargs = {'pk': self.collection.pk}
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-url': 'https://www.test-flyer.org',
            'form-1-url': 'https://www.best-flyer.org'
        }
        request = RequestFactory().post(reverse('collection-update', kwargs=kwargs), data=data)
        request.user = self.member
        view = views.CollectionUpdateView()
        view.setup(request)
        view.kwargs = kwargs
        view.object = self.collection
        query_dict = QueryDict('', mutable=True)
        query_dict.update(data)
        expected_formset_kwargs = {
            'parent_object': self.collection,
            'owner': self.member,
            'data': query_dict
        }
        self.assertDictEqual(expected_formset_kwargs, view.get_formset_kwargs())

    def test_get_get_formset(self):
        kwargs = {'pk': self.collection.pk}
        request = RequestFactory().get(reverse('collection-update', kwargs=kwargs))
        request.user = self.member
        view = views.CollectionUpdateView()
        view.setup(request)
        view.kwargs = kwargs
        view.object = self.collection
        formset = view.get_formset()
        self.assertIsInstance(formset, BaseWasteFlyerUrlFormSet)

    def test_post_get_formset(self):
        kwargs = {'pk': self.collection.pk}
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-url': 'https://www.test-flyer.org',
            'form-1-url': 'https://www.best-flyer.org'
        }
        request = RequestFactory().post(reverse('collection-update', kwargs=kwargs), data=data)
        request.user = self.member
        view = views.CollectionUpdateView()
        view.setup(request)
        view.kwargs = kwargs
        view.object = self.collection
        formset = view.get_formset()
        self.assertIsInstance(formset, BaseWasteFlyerUrlFormSet)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collection-update', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collection-update', kwargs={'pk': self.collection.id}))
        self.assertEqual(response.status_code, 403)

    def test_context_contains_form_and_formset(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-update', kwargs={'pk': self.collection.id}))
        self.assertIsInstance(response.context['form'], CollectionModelForm)
        self.assertIsInstance(response.context['formset'], BaseFormSet)

    def test_post_with_missing_data_errors(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse('collection-update', kwargs={'pk': self.collection.id}),
            data={'connection_rate_year': 123}
        )
        self.assertEqual(response.status_code, 200)

        error_msg = 'This field is required.'
        self.assertTrue(error_msg in response.context['form'].errors['catchment'])
        self.assertTrue(error_msg in response.context['form'].errors['collector'])
        self.assertTrue(error_msg in response.context['form'].errors['collection_system'])
        self.assertTrue(error_msg in response.context['form'].errors['waste_category'])
        self.assertTrue(error_msg in response.context['form'].errors['allowed_materials'])
        self.assertTrue('Year needs to be in YYYY format.' in response.context['form'].errors['connection_rate_year'])

    def test_post_with_valid_form_data(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse('collection-update', kwargs={'pk': self.collection.id}),
            data={
                'catchment': Catchment.objects.first().id,
                'collector': Collector.objects.first().id,
                'collection_system': CollectionSystem.objects.first().id,
                'waste_category': WasteCategory.objects.first().id,
                'allowed_materials': [c.id for c in WasteComponent.objects.all()],
                'connection_rate': 0.7,
                'connection_rate_year': 2020,
                'frequency': CollectionFrequency.objects.first().id,
                'description': 'This is a test case that should pass!',
                'form-INITIAL_FORMS': '0',
                'form-TOTAL_FORMS': '2',
                'form-0-url': 'https://www.test-flyer.org',
            }
        )
        self.assertEqual(response.status_code, 302)

    def test_associated_flyers_are_displayed_as_initial_values_in_formset(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-update', kwargs={'pk': self.collection.pk}))
        expected_initial = [flyer.url for flyer in self.collection.flyers.all()]
        real_initial = [form.initial['url'] for form in response.context['formset'].initial_forms]
        self.assertListEqual(expected_initial, real_initial)

    def test_new_flyers_are_created_from_unknown_urls(self):
        self.client.force_login(self.member)
        data = {
            'catchment': self.collection.catchment.id,
            'collector': self.collection.collector.id,
            'collection_system': self.collection.collection_system.id,
            'waste_category': self.collection.waste_stream.category.id,
            'allowed_materials': [m.id for m in self.collection.waste_stream.allowed_materials.all()],
            'connection_rate': 0.7,
            'connection_rate_year': 2020,
            'frequency': self.collection.frequency.id,
            'description': self.collection.description,
            'form-INITIAL_FORMS': '1',
            'form-TOTAL_FORMS': '2',
            'form-0-url': 'https://www.best-flyer.org',
            'form-1-url': 'https://www.fest-flyer.org',
        }
        self.client.post(reverse('collection-update', kwargs={'pk': self.collection.pk}), data=data)
        flyer = WasteFlyer.objects.get(url='https://www.fest-flyer.org')
        self.assertIsInstance(flyer, WasteFlyer)

    def test_regression_post_with_valid_data_doesnt_delete_unchanged_flyers(self):
        self.client.force_login(self.member)
        data = {
            'catchment': self.collection.catchment.id,
            'collector': self.collection.collector.id,
            'collection_system': self.collection.collection_system.id,
            'waste_category': self.collection.waste_stream.category.id,
            'allowed_materials': [m.id for m in self.collection.waste_stream.allowed_materials.all()],
            'connection_rate': 0.7,
            'connection_rate_year': 2020,
            'frequency': self.collection.frequency.id,
            'description': self.collection.description,
            'form-INITIAL_FORMS': '1',
            'form-TOTAL_FORMS': '2',
            'form-0-url': self.collection.flyers.first().url,
            'form-0-id': self.collection.flyers.first().id,
            'form-1-url': 'https://www.fest-flyer.org',
            'form-1-id': '',
        }
        response = self.client.post(reverse('collection-update', kwargs={'pk': self.collection.id}), data=data)
        self.assertEqual(response.status_code, 302)
        self.assertIn(WasteFlyer.objects.get(url='https://www.fest-flyer.org'), self.collection.flyers.all())
        self.assertIn(WasteFlyer.objects.get(url='https://www.test-flyer.org'), self.collection.flyers.all())
        self.assertEqual(WasteFlyer.objects.count(), 2)


# ----------- Collection utils ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionAutocompleteViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Collection.objects.create(catchment=Catchment.objects.create(name='Hamburg'))
        Collection.objects.create(catchment=Catchment.objects.create(name='Berlin'))

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('collection-autocomplete'))
        self.assertEqual(response.status_code, 200)

    def test_get_returns_json_response(self):
        response = self.client.get(reverse('collection-autocomplete'))
        self.assertIsInstance(response, JsonResponse)

    def test_get_returns_only_collections_with_names_containing_filter_string(self):
        response = self.client.get(reverse('collection-autocomplete') + '?q=Ham')
        self.assertContains(response, 'Hamburg')
        self.assertNotContains(response, 'Berlin')


class CollectionAddPropertyValueViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_collectionpropertyvalue'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.collection = Collection.objects.create(name='Test Collection')
        cls.prop = Property.objects.create(name='Test Property', unit='Test Unit')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('collection-add-property', kwargs={'pk': self.collection.pk}))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collection-add-property', kwargs={'pk': self.collection.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-add-property', kwargs={'pk': self.collection.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_initial_has_collection_and_property(self):
        request = RequestFactory().get(reverse('collection-add-property', kwargs={'pk': self.collection.id}))
        view = views.CollectionAddPropertyValueView()
        view.setup(request)
        view.kwargs = {'pk': self.collection.id}
        initial = view.get_initial()
        expected = {
            'collection': self.collection.pk,
            'property': Property.objects.get(name='specific waste generation').pk
        }
        self.assertDictEqual(expected, initial)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collection-add-property', kwargs={'pk': self.collection.pk}))
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('collection-add-property', kwargs={'pk': self.collection.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'collection': self.collection.pk,
            'property': self.prop.pk,
            'year': 2022,
            'average': 123.5,
            'standard_deviation': 12.6
        }
        response = self.client.post(reverse('collection-add-property', kwargs={'pk': self.collection.pk}), data=data)
        self.assertEqual(response.status_code, 302)





class CollectionSummaryAPIViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_collection'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        MaterialCategory.objects.create(name='Biowaste component')
        material1 = WasteComponent.objects.create(name='Test material 1')
        material2 = WasteComponent.objects.create(name='Test material 2')
        waste_stream = WasteStream.objects.create(
            name='Test waste stream',
            category=WasteCategory.objects.create(name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(name='Test Frequency')
        cls.collection = Collection.objects.create(
            name='collection1',
            catchment=Catchment.objects.create(name='Test catchment'),
            collector=Collector.objects.create(name='Test collector'),
            collection_system=CollectionSystem.objects.create(name='Test system'),
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=frequency,
            description='This is a test case.'
        )
        cls.collection.flyers.add(waste_flyer)

    def test_get_http_200_ok_for_group_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-summary-api'), {'pk': self.collection.pk})
        self.assertEqual(response.status_code, 200)

    def test_get_returns_correct_summary_on_existing_collection_pk(self):
        self.maxDiff = None
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-summary-api'), {'pk': self.collection.pk})
        expected = {'summaries': [
            OrderedDict([
                ('id', self.collection.id),
                ('Catchment', self.collection.catchment.name),
                ('Collector', self.collection.collector.name),
                ('Collection system', self.collection.collection_system.name),
                ('Waste category', self.collection.waste_stream.category.name),
                ('Allowed materials', [m.name for m in self.collection.waste_stream.allowed_materials.all()]),
                ('Connection rate', '70.0\u00A0% (2020)'),
                ('Frequency', self.collection.frequency.name),
                ('Sources', [flyer.url for flyer in self.collection.flyers.all()]),
                ('Comments', self.collection.description)
            ]),
        ]
        }
        self.assertDictEqual(response.data, expected)


@patch('case_studies.soilcom.tasks.export_collections_to_file.delay')
class CollectionListFileExportViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        MaterialCategory.objects.create(name='Biowaste component')
        material1 = WasteComponent.objects.create(name='Test material 1')
        material2 = WasteComponent.objects.create(name='Test material 2')
        waste_stream = WasteStream.objects.create(
            name='Test waste stream',
            category=WasteCategory.objects.create(name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(name='Test Frequency')
        for i in range(1, 3):
            collection = Collection.objects.create(
                name=f'collection{i}',
                catchment=Catchment.objects.create(name='Test catchment'),
                collector=Collector.objects.create(name='Test collector'),
                collection_system=CollectionSystem.objects.create(name='Test system'),
                waste_stream=waste_stream,
                connection_rate=0.7,
                connection_rate_year=2020,
                frequency=frequency,
                description='This is a test case.'
            )
            collection.flyers.add(waste_flyer)

    def setUp(self):
        self.mock_task = Mock()
        self.mock_task.task_id = '1234'

    def test_get_http_302_redirect_for_anonymous(self, mock_export):
        mock_export.return_value = self.mock_task
        response = self.client.get(reverse('collection-export'))
        self.assertEqual(302, response.status_code)

    def test_get_http_200_ok_for_authenticated_user(self, mock_export):
        mock_export.return_value = self.mock_task
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-export'))
        self.assertEqual(200, response.status_code)

    def test_query_parameters_are_handled(self, mock_export):
        mock_export.return_value = self.mock_task
        self.client.force_login(self.member)
        response = self.client.get(f'{reverse("collection-export")}?format=xlsx&page=1&collector=1')
        mock_export.assert_called_once_with('xlsx', {'collector': ['1']})
        expected_response = {'task_id': '1234'}
        self.assertDictEqual(expected_response, json.loads(response.content))


class CollectionWasteSamplesViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_collection'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.collection = Collection.objects.create(name='Test Collection')
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        cls.collection.samples.add(Sample.objects.create(name='Test Sample 1', series=series))
        Sample.objects.create(name='Test Sample 2', series=series)
        cls.url = reverse('collection-wastesamples', kwargs={'pk': cls.collection.pk})

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={self.url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.post(self.url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={self.url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_on_submit_of_add_form(self):
        self.client.force_login(self.member)
        sample = Sample.objects.get(name='Test Sample 2')
        data = {'sample': sample.pk, 'submit': 'Add'}
        response = self.client.post(self.url, data, follow=True)
        self.assertRedirects(response, self.url)

    def test_post_success_and_http_302_redirect_on_submit_of_remove_form(self):
        self.client.force_login(self.member)
        sample = Sample.objects.get(name='Test Sample 1')
        data = {'sample': sample.pk, 'submit': 'Remove'}
        response = self.client.post(self.url, data, follow=True)
        self.assertRedirects(response, self.url)


# ----------- WasteFlyer CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteFlyerListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ('view_wasteflyer', 'change_wasteflyer',)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        WasteFlyer.objects.create(
            abbreviation='Flyer1',
            url='https://www.test-flyer.org'
        )
        WasteFlyer.objects.create(
            abbreviation='Flyer2',
            url='https://www.best-flyer.org'
        )
        WasteFlyer.objects.create(
            abbreviation='Flyer3',
            url='https://www.rest-flyer.org'
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('wasteflyer-list'))
        self.assertEqual(response.status_code, 200)

    def test_all_flyers_are_included(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('wasteflyer-list'))
        self.assertIn('object_list', response.context)
        self.assertEqual(len(response.context['object_list']), 3)

    def test_contains_check_urls_button_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('wasteflyer-list'))
        self.assertContains(response, 'check urls')


class WasteFlyerDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_wasteflyer'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.flyer = WasteFlyer.objects.create(abbreviation='TEST')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('wasteflyer-detail', kwargs={'pk': self.flyer.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('wasteflyer-detail', kwargs={'pk': self.flyer.pk}))
        self.assertEqual(response.status_code, 200)

    def test_contains_check_url_button_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('wasteflyer-detail', kwargs={'pk': self.flyer.pk}))
        self.assertContains(response, 'check url')

    def test_does_not_contain_check_url_button_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('wasteflyer-detail', kwargs={'pk': self.flyer.pk}))
        self.assertNotContains(response, 'check url')


class WasteCollectionMapViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ('add_collection', 'view_collection', 'change_collection', 'delete_collection')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        catchment = Catchment.objects.create(name='Test Catchment', region=region)
        cls.collection = Collection.objects.create(name='Test Collection', catchment=catchment)

    def test_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('WasteCollection'))
        self.assertEqual(response.status_code, 200)

    def test_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('WasteCollection'))
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('WasteCollection'))
        self.assertTemplateUsed(response, 'waste_collection_map.html')

    def test_create_collection_option_visible_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('WasteCollection'))
        self.assertContains(response, 'Add new collection')

    def test_create_collection_option_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('WasteCollection'))
        self.assertNotContains(response, 'Add new collection')

    def test_copy_collection_option_visible_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('WasteCollection'))
        self.assertContains(response, 'Copy selected collection')

    def test_copy_collection_option_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('WasteCollection'))
        self.assertNotContains(response, 'Copy selected collection')

    def test_update_collection_option_visible_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('WasteCollection'))
        self.assertContains(response, 'Edit selected collection')

    def test_update_collection_option_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('WasteCollection'))
        self.assertNotContains(response, 'Edit selected collection')

    def test_collection_dashboard_option_visible_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('WasteCollection'))
        self.assertContains(response, 'Waste collection dashboard')

    def test_collection_dashboard_option_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('WasteCollection'))
        self.assertNotContains(response, 'Waste collection dashboard')


class WasteFlyerListCheckUrlsView(ViewWithPermissionsTestCase):
    member_permissions = 'change_wasteflyer'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for i in range(1, 5):
            WasteFlyer.objects.create(
                title=f'Waste flyer {i}',
                abbreviation=f'WF{i}',
                url_valid=i % 2 == 0
            )

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        params = {
            'csrfmiddlewaretoken': ['Hm7MXB2NjRCOIpNbGaRKR87VCHM5KwpR1t4AdZFgaqKfqui1EJwhKKmkxFKDfL3h'],
            'url_valid': ['False'],
            'page': ['2']
        }
        qdict = QueryDict('', mutable=True)
        qdict.update(MultiValueDict(params))
        url = reverse('wasteflyer-list-check-urls') + '?' + qdict.urlencode()
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
