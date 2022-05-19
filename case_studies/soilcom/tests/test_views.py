from collections import OrderedDict

from django.contrib.auth.models import Permission, User
from django.forms.formsets import BaseFormSet
from django.test import RequestFactory, TestCase, modify_settings
from django.urls import reverse

from maps.models import Catchment, Region
from materials.models import MaterialCategory
from users.models import get_default_owner, Group
from .. import views
from ..forms import CollectionModelForm
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

    def test_get_get_formset_kwargs_fetches_correct_queryset_and_parent_object(self):
        request = RequestFactory().get(reverse('collection-create'))
        view = views.CollectionCreateView()
        view.setup(request)
        view.kwargs = {'pk': self.collection.id}
        expected = {
            'queryset': WasteFlyer.objects.none(),
        }
        formset_kwargs = view.get_formset_kwargs()
        self.assertEqual(set(expected.keys()), set(formset_kwargs.keys()))
        for key, value in expected.items():
            if key == 'queryset':
                self.assertEqual(set(expected[key]), set(formset_kwargs[key]))
            else:
                self.assertEqual(value, formset_kwargs[key])

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
        # self.assertTrue(error_msg in response.context['form'].errors['collector'])
        self.assertTrue(error_msg in response.context['form'].errors['collection_system'])
        self.assertTrue(error_msg in response.context['form'].errors['waste_category'])
        self.assertTrue(error_msg in response.context['form'].errors['allowed_materials'])
        self.assertTrue('Year needs to be in YYYY format.' in response.context['form'].errors['connection_rate_year'])

    def test_post_with_valid_form_data(self):
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
        # self.assertRedirects(response, reverse('WasteCollection'))
        self.assertEqual(response.status_code, 302)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionCopyViewTestCase(TestCase):

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
        self.collection = Collection.objects.get(name='collection1')
        self.flyer = self.collection.flyers.get(url='https://www.test-flyer.org')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')

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

    def test_get_get_formset_kwargs_fetches_correct_queryset_and_parent_object(self):
        request = RequestFactory().get(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        view = views.CollectionCopyView()
        view.setup(request)
        view.kwargs = {'pk': self.collection.id}
        view.object = view.get_object()
        expected = {
            'queryset': self.collection.flyers.all(),
            'parent_object': self.collection
        }
        formset_kwargs = view.get_formset_kwargs()
        self.assertEqual(set(expected.keys()), set(formset_kwargs.keys()))
        for key, value in expected.items():
            if key == 'queryset':
                self.assertEqual(set(expected[key]), set(formset_kwargs[key]))
            else:
                self.assertEqual(value, formset_kwargs[key])

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


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class CollectionUpdateViewTestCase(TestCase):

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
        # self.assertTrue(error_msg in response.context['form'].errors['collector'])
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
                'form-0-id': '',
            }
        )
        self.assertEqual(response.status_code, 302)

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
                ('Connection rate', '70.0% (2020)'),
                ('Frequency', self.collection.frequency.name),
                ('Sources', [flyer.url for flyer in self.collection.flyers.all()]),
                ('Comments', self.collection.description)
            ]),
        ]
        }
        self.assertDictEqual(response.data, expected)


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
