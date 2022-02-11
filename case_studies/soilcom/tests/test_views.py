from collections import OrderedDict

from django.contrib.auth.models import Permission, User
from django.test import RequestFactory, TestCase, modify_settings
from django.urls import reverse

from maps.models import Catchment
from materials.models import MaterialGroup
from .. import views
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

        MaterialGroup.objects.create(owner=owner, name='Biowaste component')
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
        Collection.objects.create(
            owner=owner,
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            flyer=waste_flyer,
            description='This is a test case.'
        )

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

    #
    def test_get_http_200_ok_for_group_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('collection-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(reverse('collection-create'), kwargs={})
        self.assertEqual(response.status_code, 302)

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
        self.assertFormError(response, 'form', 'catchment', 'This field is required.')
        # self.assertFormError(response, 'form', 'collector', 'This field is required.')
        self.assertFormError(response, 'form', 'collection_system', 'This field is required.')
        self.assertFormError(response, 'form', 'waste_category', 'This field is required.')
        self.assertFormError(response, 'form', 'allowed_materials', 'This field is required.')
        # self.assertFormError(response, 'form', 'flyer_url', 'This field is required.')

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
                'flyer_url': 'https://www.test-flyer.org',
                'description': 'This is a test case that should pass!'
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

        MaterialGroup.objects.create(owner=owner, name='Biowaste component')
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
        Collection.objects.create(
            owner=owner,
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            flyer=waste_flyer,
            description='This is a test case.'
        )

    def setUp(self):
        self.collection = Collection.objects.first()
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
            'flyer_url': self.collection.flyer.url,
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

        MaterialGroup.objects.create(owner=owner, name='Biowaste component')
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
        Collection.objects.create(
            owner=owner,
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            flyer=waste_flyer,
            description='This is a test case.'
        )

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

    def test_post_with_missing_data_errors(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse('collection-update', kwargs={'pk': self.collection.id}),
            data={}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'catchment', 'This field is required.')
        # self.assertFormError(response, 'form', 'collector', 'This field is required.')
        self.assertFormError(response, 'form', 'collection_system', 'This field is required.')
        self.assertFormError(response, 'form', 'waste_category', 'This field is required.')
        self.assertFormError(response, 'form', 'allowed_materials', 'This field is required.')
        # self.assertFormError(response, 'form', 'flyer_url', 'This field is required.')

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
                'flyer_url': 'https://www.test-flyer.org',
                'description': 'This is a test case that should pass!'
            }
        )
        # self.assertRedirects(response, reverse('WasteCollection'))
        self.assertEqual(response.status_code, 302)


class CollectionSummaryAPIViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        member.user_permissions.add(Permission.objects.get(codename='change_collection'))

        MaterialGroup.objects.create(owner=owner, name='Biowaste component')
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
        Collection.objects.create(
            owner=owner,
            catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
            collector=Collector.objects.create(owner=owner, name='Test collector'),
            collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
            waste_stream=waste_stream,
            flyer=waste_flyer,
            description='This is a test case.'
        )

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
                ('Flyer', self.collection.flyer.url),
                ('Comments', self.collection.description)
            ]),
        ]
        }
        self.assertDictEqual(response.data, expected)
