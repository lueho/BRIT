from django.urls import reverse
from django.urls.exceptions import NoReverseMatch


from utils.tests.testcases import ViewSetWithPermissionsTestCase
from ..models import Material, SampleSeries, Sample, MaterialComponentGroup, Composition
from ..serializers import (
    MaterialAPISerializer,
    SampleSeriesAPISerializer,
    SampleAPISerializer,
    CompositionAPISerializer,
)


class MaterialViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = ('view_material', 'add_material', 'change_material', 'delete_material')
    material = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')

    def test_get_list_http_401_unauthenticated_for_not_authenticated_user(self):
        response = self.client.get(reverse('api-material-list'))
        self.assertEqual(response.status_code, 401)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-material-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_correct_data(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-material-list'))
        serializer = MaterialAPISerializer(Material.objects.all(), many=True)
        self.assertEqual(response.data, serializer.data)

    def test_get_detail_http_401_unauthenticated_for_not_authenticated_user(self):
        response = self.client.get(reverse('api-material-detail', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 401)

    def test_get_detail_http_200_ok_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-material-detail', kwargs={'pk': self.material.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        self.client.force_login(self.outsider)
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


class SampleSeriesViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = ('view_sampleseries', 'add_sampleseries', 'change_sampleseries', 'delete_sampleseries')
    material = None
    series = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')
        cls.series = SampleSeries.objects.create(material=cls.material, name='Test Series')

    def test_get_list_http_401_unauthenticated_for_not_authenticated_user(self):
        response = self.client.get(reverse('api-sampleseries-list'))
        self.assertEqual(response.status_code, 401)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-sampleseries-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_correct_data(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-sampleseries-list'))
        serializer = SampleSeriesAPISerializer(SampleSeries.objects.all(), many=True)
        self.assertEqual(response.data, serializer.data)

    def test_get_detail_http_401_unauthenticated_for_not_authenticated_user(self):
        response = self.client.get(reverse('api-sampleseries-detail', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 401)

    def test_get_detail_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-sampleseries-detail', kwargs={'pk': self.series.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        self.client.force_login(self.outsider)
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


class SampleViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = ('view_sample', 'add_sample', 'change_sample', 'delete_sample')
    material = None
    series = None
    sample = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')
        cls.series = SampleSeries.objects.create(material=cls.material, name='Test Series')
        cls.sample = Sample.objects.create(series=cls.series, material=cls.material, name='Test Sample')

    def test_get_list_http_401_unauthenticated_for_not_authenticated_user(self):
        response = self.client.get(reverse('api-sample-list'))
        self.assertEqual(response.status_code, 401)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-sample-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_correct_data(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-sample-list'))
        serializer = SampleAPISerializer(Sample.objects.all(), many=True)
        self.assertEqual(response.data, serializer.data)

    def test_get_detail_http_401_unauthenticated_for_not_authenticated_user(self):
        response = self.client.get(reverse('api-sample-detail', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 401)

    def test_get_detail_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-sample-detail', kwargs={'pk': self.sample.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        self.client.force_login(self.outsider)
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


class CompositionViewSetTestCase(ViewSetWithPermissionsTestCase):
    member_permissions = ('view_composition', 'add_composition', 'change_composition', 'delete_composition')
    material = None
    series = None
    sample = None
    composition = None
    group = None

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name='Test Material')
        cls.series = SampleSeries.objects.create(material=cls.material, name='Test Series')
        cls.sample = Sample.objects.create(series=cls.series, material=cls.material, name='Test Sample')
        cls.group = MaterialComponentGroup.objects.create(name='Test Component Group')
        cls.composition = Composition.objects.create(name='Test Composition', sample=cls.sample, group=cls.group)

    def test_get_list_http_401_unauthenticated_for_not_authenticated_user(self):
        response = self.client.get(reverse('api-composition-list'))
        self.assertEqual(response.status_code, 401)

    def test_get_list_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-composition-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_list_returns_correct_data(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-composition-list'))
        serializer = CompositionAPISerializer(Composition.objects.all(), many=True)
        self.assertEqual(response.data, serializer.data)

    def test_get_detail_http_401_unauthenticated_for_not_authenticated_user(self):
        response = self.client.get(reverse('api-composition-detail', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 401)

    def test_get_detail_http_200_ok_for_authenticated_user(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('api-composition-detail', kwargs={'pk': self.composition.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_detail_returns_correct_data(self):
        self.client.force_login(self.outsider)
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
