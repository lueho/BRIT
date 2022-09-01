import datetime

from django.test import TestCase, modify_settings

from users.models import get_default_owner
from ..models import NutsRegion, Attribute, RegionAttributeValue, RegionAttributeTextValue
from ..serializers import NutsRegionSummarySerializer


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class NutsRegionSummarySerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        attribute = Attribute.objects.create(owner=owner, name='Population density', unit='1/km²')
        region = NutsRegion.objects.create(
            owner=owner,
            nuts_id='TE57',
            name_latn='Test NUTS'
        )
        RegionAttributeValue.objects.create(
            owner=owner,
            attribute=attribute,
            region=region,
            value=123.321,
            date=datetime.date(2018, 1, 1)
        )
        RegionAttributeValue.objects.create(
            owner=owner,
            attribute=attribute,
            region=region,
            value=123.321,
            date=datetime.date(2019, 1, 1)
        )
        Attribute.objects.get_or_create(owner=owner, name='Urban rural remoteness', unit='')
        Attribute.objects.create(owner=owner, name='Population', unit='')

    def setUp(self):
        self.owner = get_default_owner()
        self.region = NutsRegion.objects.get(nuts_id='TE57')
        self.urban_rural_remoteness = Attribute.objects.get(name='Urban rural remoteness')

    def test_serializer_contains_main_data(self):
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('nuts_id', data)
        self.assertIn('name', data)

    def test_population_method_field_returns_value_as_integer(self):
        RegionAttributeValue.objects.create(
            owner=self.owner,
            attribute=Attribute.objects.get(name='Population'),
            region=self.region,
            value=123321,
            date=datetime.date(2021, 12, 31)
        )
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('population', data)
        self.assertTrue(type(data['population'] == int))

    def test_population_method_field_returns_non_for_non_existing(self):
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('population', data)
        self.assertFalse(data['population'])

    def test_population_density_method_field_returns_newest_value(self):
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('population_density', data)
        self.assertEqual(data['population_density'], '123.321 per km² (2019)')

    def test_urban_rural_remoteness_method_field_returns_non_if_for_non_existing(self):
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('urban_rural_remoteness', data)
        self.assertFalse(data['urban_rural_remoteness'])

    def test_urban_rural_remoteness_method_field_returns_existing_values(self):
        RegionAttributeTextValue.objects.create(
            owner=self.owner,
            attribute=self.urban_rural_remoteness,
            region=self.region,
            value='intermediate, close to a city',
            date=datetime.date.today()
        )
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('urban_rural_remoteness', data)
        self.assertEqual(data['urban_rural_remoteness'], 'intermediate, close to a city')

