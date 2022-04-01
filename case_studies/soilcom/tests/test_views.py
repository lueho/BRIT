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
from ..models import Collection, Collector, CollectionSystem, WasteCategory, WasteComponent, WasteFlyer, WasteStream


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
        collection1 = Collection.objects.create(
            owner=owner,
            name='collection1',
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
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
            data={}
        )
        self.assertEqual(response.status_code, 200)

        error_msg = 'This field is required.'
        self.assertTrue(error_msg in response.context['form'].errors['catchment'])
        # self.assertTrue(error_msg in response.context['form'].errors['collector'])
        self.assertTrue(error_msg in response.context['form'].errors['collection_system'])
        self.assertTrue(error_msg in response.context['form'].errors['waste_category'])
        self.assertTrue(error_msg in response.context['form'].errors['allowed_materials'])

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
        collection = Collection.objects.create(
            owner=owner,
            name='collection1',
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
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

    def test_get_get_initial(self):
        request = RequestFactory().get(reverse('collection-copy', kwargs={'pk': self.collection.id}))
        view = views.CollectionCopyView()
        view.setup(request)
        view.kwargs = {'pk': self.collection.id}
        expected = {
            'catchment': self.collection.catchment,
            'collector': self.collection.collector,
            'collection_system': self.collection.collection_system,
            'waste_category': self.collection.waste_stream.category,
            'allowed_materials': self.collection.waste_stream.allowed_materials.all(),
            'description': self.collection.description
        }
        initial = view.get_initial()
        self.assertEqual(set(expected.keys()), set(initial.keys()))
        for key, value in expected.items():
            if key == 'allowed_materials':
                self.assertIn(key, initial)
                self.assertEqual(set(expected[key]), set(initial[key]))
            else:
                self.assertIn(key, initial)
                self.assertEqual(value, initial[key])

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
        collection1 = Collection.objects.create(
            owner=owner,
            name='collection1',
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
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
            data={}
        )
        self.assertEqual(response.status_code, 200)

        error_msg = 'This field is required.'
        self.assertTrue(error_msg in response.context['form'].errors['catchment'])
        # self.assertTrue(error_msg in response.context['form'].errors['collector'])
        self.assertTrue(error_msg in response.context['form'].errors['collection_system'])
        self.assertTrue(error_msg in response.context['form'].errors['waste_category'])
        self.assertTrue(error_msg in response.context['form'].errors['allowed_materials'])

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
                'description': 'This is a test case that should pass!',
                'form-INITIAL_FORMS': '0',
                'form-TOTAL_FORMS': '2',
                'form-0-url': 'https://www.test-flyer.org',
                'form-0-id': '',
            }
        )
        self.assertEqual(response.status_code, 302)


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
        collection1 = Collection.objects.create(
            owner=owner,
            name='collection1',
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            description='This is a test case.'
        )
        collection1.flyers.add(waste_flyer)

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.collection = Collection.objects.first()

    def test_get_http_200_ok_for_group_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('data.collection-summary'), {'collection_id': self.collection.id})
        self.assertEqual(response.status_code, 200)

    def test_get_returns_correct_summary_on_existing_collection_id(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('data.collection-summary'), {'collection_id': self.collection.id})
        expected = {'summaries': [
            OrderedDict([
                ('id', self.collection.id),
                ('Catchment', self.collection.catchment.name),
                ('Collector', self.collection.collector.name),
                ('Collection system', self.collection.collection_system.name),
                ('Waste category', self.collection.waste_stream.category.name),
                ('Allowed materials', [m.name for m in self.collection.waste_stream.allowed_materials.all()]),
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
        region = Region.objects.create(owner=owner, name='Test Region')
        catchment = Catchment.objects.create(owner=owner, name='Test Catchment', region=region)
        Collection.objects.create(owner=owner, name='Test Collection', catchment=catchment)

    def setUp(self):
        self.collection = Collection.objects.get(name='Test Collection')

    def test_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('WasteCollection'))
        self.assertEqual(response.status_code, 200)
