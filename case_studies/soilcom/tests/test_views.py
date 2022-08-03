from collections import OrderedDict
import csv
import io

from django.contrib.auth.models import Permission, User
from django.forms.formsets import BaseFormSet
from django.http import QueryDict
from django.test import RequestFactory, TestCase, modify_settings
from django.urls import reverse

from maps.models import Catchment, Region
from materials.models import MaterialCategory
from users.models import get_default_owner, Group
from .. import views
from ..forms import CollectionModelForm, BaseWasteFlyerUrlFormSet
from ..models import (Collection, Collector, CollectionSystem, WasteCategory, WasteComponent, WasteFlyer, WasteStream,
                      CollectionFrequency)


# ----------- Collection Frequency CRUD --------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionFrequencyListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-list'))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionFrequencyCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_collectionfrequency'))
        member.groups.add(members)

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')

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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionFrequencyModalCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_collectionfrequency'))
        member.groups.add(members)

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')

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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionFrequencyDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        CollectionFrequency.objects.create(owner=owner, name='Test Frequency')

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.frequency = CollectionFrequency.objects.get(name='Test Frequency')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-detail', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-detail', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionFrequencyModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='owner')
        User.objects.create(username='outsider')
        CollectionFrequency.objects.create(owner=owner, name='Test Frequency')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.frequency = CollectionFrequency.objects.get(name='Test Frequency')

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('collectionfrequency-detail-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('collectionfrequency-detail-modal', kwargs={'pk': self.frequency.pk}))
        self.assertEqual(response.status_code, 200)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionFrequencyUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_collectionfrequency'))
        member.groups.add(members)
        CollectionFrequency.objects.create(owner=owner, name='Test Frequency')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.frequency = CollectionFrequency.objects.get(name='Test Frequency')

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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionFrequencyModalUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_collectionfrequency'))
        member.groups.add(members)
        CollectionFrequency.objects.create(owner=owner, name='Test Frequency')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.frequency = CollectionFrequency.objects.get(name='Test Frequency')

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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionFrequencyModalDeleteViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='delete_collectionfrequency'))
        member.groups.add(members)
        CollectionFrequency.objects.create(owner=owner, name='Test Frequency')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.frequency = CollectionFrequency.objects.get(name='Test Frequency')

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


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
# logins. Can be disabled here because it is not relevant for these tests.
@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        member.user_permissions.add(Permission.objects.get(codename='add_collection'))

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        collection1 = Collection.objects.create(
            owner=owner,
            name='collection1',
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=frequency,
            description='This is a test case.'
        )
        collection1.flyers.add(waste_flyer)

    def setUp(self):
        self.collection = Collection.objects.first()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionCopyViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        member.user_permissions.add(Permission.objects.get(codename='add_collection'))

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        collection = Collection.objects.create(
            owner=owner,
            name='collection1',
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=frequency,
            description='This is a test case.'
        )
        collection.flyers.add(waste_flyer)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.collection = Collection.objects.get(name='collection1')
        self.flyer = self.collection.flyers.get(url='https://www.test-flyer.org')

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
            'collector': Collector.objects.create(owner=self.owner, name='New Test Collector').id,
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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionUpdateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        member.user_permissions.add(Permission.objects.get(codename='change_collection'))

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        collection1 = Collection.objects.create(
            owner=owner,
            name='collection1',
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=frequency,
            description='This is a test case.'
        )
        collection1.flyers.add(waste_flyer)

    def setUp(self):
        self.owner = get_default_owner()
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.collection = Collection.objects.first()

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


class CollectionSummaryAPIViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        member.user_permissions.add(Permission.objects.get(codename='change_collection'))

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        collection1 = Collection.objects.create(
            owner=owner,
            name='collection1',
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            connection_rate=0.7,
            connection_rate_year=2020,
            frequency=frequency,
            description='This is a test case.'
        )
        collection1.flyers.add(waste_flyer)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.collection = Collection.objects.first()

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


class CollectionViewSetDownloadCSVTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        member.user_permissions.add(Permission.objects.get(codename='add_collection'))

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        for i in range(1, 3):
            collection = Collection.objects.create(
                owner=owner,
                name=f'collection{i}',
                catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
                collector=Collector.objects.create(owner=owner, name='Test collector'),
                collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
                waste_stream=waste_stream,
                connection_rate=0.7,
                connection_rate_year=2020,
                frequency=frequency,
                description='This is a test case.'
            )
            collection.flyers.add(waste_flyer)

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.collection_list = Collection.objects.all()

    def test_get_http_401_unauthenticated_for_anonymous(self):
        response = self.client.get(reverse('api-collection-download-csv'))
        self.assertEqual(401, response.status_code)

    def test_get_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('api-collection-download-csv'))
        self.assertEqual(200, response.status_code)

    def test_file_attachment(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('api-collection-download-csv'), params={})
        self.assertEqual(response.get('Content-Disposition'), 'attachment; filename="collections.csv"')

    def test_file_has_content_type_csv(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('api-collection-download-csv'), params={})
        self.assertEqual('text/csv', response.headers.get('Content-Type'))

    def test_pagination_of_streaming_content(self):
        owner = get_default_owner()
        for i in range(30):
            collection = Collection.objects.create(
                owner=owner,
                name=f'collection{i}',
                catchment=Catchment.objects.first(),
                collector=Collector.objects.first(),
                collection_system=CollectionSystem.objects.first(),
                waste_stream=WasteStream.objects.first(),
                connection_rate=0.7,
                connection_rate_year=2020,
                frequency=CollectionFrequency.objects.first(),
                description=f'This is additional test record {i}.'
            )
            for flyer in WasteFlyer.objects.all():
                collection.flyers.add(flyer)
        self.client.force_login(self.member)
        params = {}
        response = self.client.get(reverse('api-collection-download-csv'), params=params)
        content = ''
        for partial_content in response:
            content += partial_content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(content), delimiter='\t')
        self.assertEqual(Collection.objects.count(), len(list(reader)))

    def test_file_content(self):
        self.client.force_login(self.member)
        params = {}
        response = self.client.get(reverse('api-collection-download-csv'), params=params)
        # For some reason, the content needs to be decoded and again encoded to work. Why?
        content = ''
        for partial_content in response:
            content += partial_content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(content), delimiter='\t')
        fieldnames = ['Catchment', 'Country', 'NUTS Id', 'Collector', 'Collection System', 'Waste Category',
                      'Allowed Materials', 'Connection Rate', 'Connection Rate Year', 'Frequency', 'Comments',
                      'Sources', 'Created by', 'Created at', 'Last modified by', 'Last modified at']
        self.assertListEqual(fieldnames, list(reader.fieldnames))
        self.assertEqual(2, sum(1 for _ in reader))

    def test_allowed_materials_formatted_as_comma_separated_list_in_one_field(self):
        self.client.force_login(self.member)
        params = {}
        response = self.client.get(reverse('api-collection-download-csv'), params=params)
        content = ''
        for partial_content in response:
            content += partial_content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(content), delimiter='\t')
        for row in reader:
            self.assertEqual('Test material 1, Test material 2', row['Allowed Materials'])

    def test_regression_flyers_without_urls_dont_raise_type_error(self):
        rogue_flyer = WasteFlyer.objects.create(owner=self.owner, title='Rogue fLyer without url', abbreviation='RF')
        defected_collection = Collection.objects.get(name='collection1')
        defected_collection.flyers.add(rogue_flyer)
        self.client.force_login(self.member)
        response = self.client.get(reverse('api-collection-download-csv'), params={})
        content = ''
        for partial_content in response:
            content += partial_content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(content), delimiter='\t')
        self.assertEqual(Collection.objects.count(), len(list(reader)))


class CollectionViewSetDownloadXLSXTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        member.user_permissions.add(Permission.objects.get(codename='add_collection'))

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        for i in range(1, 3):
            collection = Collection.objects.create(
                owner=owner,
                name=f'collection{i}',
                catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
                collector=Collector.objects.create(owner=owner, name='Test collector'),
                collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
                waste_stream=waste_stream,
                connection_rate=0.7,
                connection_rate_year=2020,
                frequency=frequency,
                description='This is a test case.'
            )
            collection.flyers.add(waste_flyer)

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.collection_list = Collection.objects.all()

    def test_get_http_401_unauthenticated_for_anonymous(self):
        response = self.client.get(reverse('api-collection-download-xlsx'))
        self.assertEqual(401, response.status_code)

    def test_get_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('api-collection-download-xlsx'))
        self.assertEqual(200, response.status_code)

    def test_file_attachment(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('api-collection-download-xlsx'), params={})
        self.assertEqual(response.get('Content-Disposition'), 'attachment; filename="collections.xlsx"')

    def test_file_has_content_type_xlsx(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('api-collection-download-xlsx'), params={})
        self.assertEqual('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', response.headers.get('Content-Type'))

    # TODO: Find way to test correct file content


class WasteFlyerListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        member.user_permissions.add(Permission.objects.get(codename='view_wasteflyer'))
        WasteFlyer.objects.create(
            owner=owner,
            abbreviation='Flyer1',
            url='https://www.test-flyer.org'
        )
        WasteFlyer.objects.create(
            owner=owner,
            abbreviation='Flyer2',
            url='https://www.best-flyer.org'
        )
        WasteFlyer.objects.create(
            owner=owner,
            abbreviation='Flyer3',
            url='https://www.rest-flyer.org'
        )

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('wasteflyer-list'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('wasteflyer-list'))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('wasteflyer-list'))
        self.assertEqual(response.status_code, 200)

    def test_all_flyers_are_included(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('wasteflyer-list'))
        self.assertIn('object_list', response.context)
        self.assertEqual(len(response.context['object_list']), 3)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class WasteCollectionMapViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='add_collection'))
        members.permissions.add(Permission.objects.get(codename='view_collection'))
        members.permissions.add(Permission.objects.get(codename='change_collection'))
        members.permissions.add(Permission.objects.get(codename='delete_collection'))
        member.groups.add(members)
        region = Region.objects.create(owner=owner, name='Test Region')
        catchment = Catchment.objects.create(owner=owner, name='Test Catchment', region=region)
        Collection.objects.create(owner=owner, name='Test Collection', catchment=catchment)

    def setUp(self):
        self.member = User.objects.get(username='member')
        self.outsider = User.objects.get(username='outsider')
        self.collection = Collection.objects.get(name='Test Collection')

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
