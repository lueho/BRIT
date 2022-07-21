from django.test import TestCase
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from rest_framework.test import APIClient

from users.models import get_default_owner, User

from ..models import Material, SampleSeries, Sample, MaterialComponentGroup, Composition
from ..serializers import (
    MaterialAPISerializer,
    SampleSeriesAPISerializer,
    SampleAPISerializer,
    CompositionAPISerializer,
)


class MaterialViewSetTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='authenticated_user')
        Material.objects.create(owner=owner, name='Test Material')

    def setUp(self):
        self.client = APIClient()
        self.authenticated_user = User.objects.get(username='authenticated_user')
        self.client.force_authenticate(self.authenticated_user)
        self.material = Material.objects.get(name='Test Material')

    def test_get_list_http_401_unauthenticated_for_not_authenticated_user(self):
        client = APIClient()
        response = client.get(reverse('api-material-list'))
        self.assertEqual(response.status_code, 401)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        response = self.client.get(reverse('api-material-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_correct_data(self):
        response = self.client.get(reverse('api-material-list'))
        serializer = MaterialAPISerializer(Material.objects.all(), many=True)
        self.assertEqual(response.data, serializer.data)

    def test_get_detail_http_401_unauthenticated_for_not_authenticated_user(self):
        client = APIClient()
        response = client.get(reverse('api-material-detail', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 401)

    def test_get_detail_http_200_ok_for_authenticated_user(self):
        response = self.client.get(reverse('api-material-detail', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        response = self.client.get(reverse('api-material-detail', kwargs={'pk': self.material.pk}))
        serializer = MaterialAPISerializer(self.material)
        self.assertEqual(response.data, serializer.data)

    def test_no_reverse_match_for_create_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-material-create'), data={})

    def test_no_reverse_match_for_update_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-material-update', kwargs={'pk': self.material.pk}), data={})

    def test_no_reverse_match_for_delete_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-material-delete', kwargs={'pk': self.material.pk}), data={})


class SampleSeriesViewSetTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='authenticated_user')
        material = Material.objects.create(owner=owner, name='Test Material')
        SampleSeries.objects.create(owner=owner, material=material, name='Test Series')

    def setUp(self):
        self.client = APIClient()
        self.authenticated_user = User.objects.get(username='authenticated_user')
        self.client.force_authenticate(self.authenticated_user)
        self.series = SampleSeries.objects.get(name='Test Series')

    def test_get_list_http_401_unauthenticated_for_not_authenticated_user(self):
        client = APIClient()
        response = client.get(reverse('api-sampleseries-list'))
        self.assertEqual(response.status_code, 401)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        response = self.client.get(reverse('api-sampleseries-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_correct_data(self):
        response = self.client.get(reverse('api-sampleseries-list'))
        serializer = SampleSeriesAPISerializer(SampleSeries.objects.all(), many=True)
        self.assertEqual(response.data, serializer.data)

    def test_get_detail_http_401_unauthenticated_for_not_authenticated_user(self):
        client = APIClient()
        response = client.get(reverse('api-sampleseries-detail', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 401)

    def test_get_detail_http_200_ok_for_authenticated_user(self):
        response = self.client.get(reverse('api-sampleseries-detail', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        response = self.client.get(reverse('api-sampleseries-detail', kwargs={'pk': self.series.pk}))
        serializer = SampleSeriesAPISerializer(self.series)
        self.assertEqual(response.data, serializer.data)

    def test_no_reverse_match_for_create_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-sampleseries-create'), data={})

    def test_no_reverse_match_for_update_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-sampleseries-update', kwargs={'pk': self.series.pk}), data={})

    def test_no_reverse_match_for_delete_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-sampleseries-delete', kwargs={'pk': self.series.pk}), data={})


class SampleViewSetTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='authenticated_user')
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, material=material, name='Test Series')
        Sample.objects.create(owner=owner, series=series, name='Test Sample')

    def setUp(self):
        self.client = APIClient()
        self.authenticated_user = User.objects.get(username='authenticated_user')
        self.client.force_authenticate(self.authenticated_user)
        self.sample = Sample.objects.get(name='Test Sample')

    def test_get_list_http_401_unauthenticated_for_not_authenticated_user(self):
        client = APIClient()
        response = client.get(reverse('api-sample-list'))
        self.assertEqual(response.status_code, 401)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        response = self.client.get(reverse('api-sample-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_correct_data(self):
        response = self.client.get(reverse('api-sample-list'))
        serializer = SampleAPISerializer(Sample.objects.all(), many=True)
        self.assertEqual(response.data, serializer.data)

    def test_get_detail_http_401_unauthenticated_for_not_authenticated_user(self):
        client = APIClient()
        response = client.get(reverse('api-sample-detail', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 401)

    def test_get_detail_http_200_ok_for_authenticated_user(self):
        response = self.client.get(reverse('api-sample-detail', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        response = self.client.get(reverse('api-sample-detail', kwargs={'pk': self.sample.pk}))
        serializer = SampleAPISerializer(self.sample)
        self.assertEqual(response.data, serializer.data)

    def test_no_reverse_match_for_create_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-sample-create'), data={})

    def test_no_reverse_match_for_update_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-sample-update', kwargs={'pk': self.sample.pk}), data={})

    def test_no_reverse_match_for_delete_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-sample-delete', kwargs={'pk': self.sample.pk}), data={})


class CompositionViewSetTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='authenticated_user')
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, material=material, name='Test Series')
        sample = Sample.objects.create(owner=owner, series=series, name='Test Sample')
        group = MaterialComponentGroup.objects.create(owner=owner, name='Test Component Group')
        Composition.objects.create(owner=owner, name='Test Composition', sample=sample, group=group)

    def setUp(self):
        self.client = APIClient()
        self.authenticated_user = User.objects.get(username='authenticated_user')
        self.client.force_authenticate(self.authenticated_user)
        self.composition = Composition.objects.get(name='Test Composition')

    def test_get_list_http_401_unauthenticated_for_not_authenticated_user(self):
        client = APIClient()
        response = client.get(reverse('api-composition-list'))
        self.assertEqual(response.status_code, 401)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        response = self.client.get(reverse('api-composition-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_correct_data(self):
        response = self.client.get(reverse('api-composition-list'))
        serializer = CompositionAPISerializer(Composition.objects.all(), many=True)
        self.assertEqual(response.data, serializer.data)

    def test_get_detail_http_401_unauthenticated_for_not_authenticated_user(self):
        client = APIClient()
        response = client.get(reverse('api-composition-detail', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 401)

    def test_get_detail_http_200_ok_for_authenticated_user(self):
        response = self.client.get(reverse('api-composition-detail', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        response = self.client.get(reverse('api-composition-detail', kwargs={'pk': self.composition.pk}))
        serializer = CompositionAPISerializer(self.composition)
        self.assertEqual(response.data, serializer.data)

    def test_no_reverse_match_for_create_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-composition-create'), data={})

    def test_no_reverse_match_for_update_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-composition-update', kwargs={'pk': self.composition.pk}), data={})

    def test_no_reverse_match_for_delete_link(self):
        with self.assertRaises(NoReverseMatch):
            self.client.post(reverse('api-composition-delete', kwargs={'pk': self.composition.pk}), data={})
