from django.test import TestCase

from ..models import HamburgRoadsideTrees
from ..serializers import HamburgRoadsideTreeSimpleModelSerializer


class HamburgRoadsideTreeSimpleModelSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.tree = HamburgRoadsideTrees.objects.create(
            art_latein='Quercus robur',
            pflanzjahr=1990,
            kronendurchmesser=10,
            stammumfang=2,
            strasse='Musterstraße',
            hausnummer='10'
        )
        cls.serializer = HamburgRoadsideTreeSimpleModelSerializer(instance=cls.tree)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertIn('id', data)
        self.assertIn('art_latein', data)
        self.assertIn('pflanzjahr', data)
        self.assertIn('kronendurchmesser', data)
        self.assertIn('stammumfang', data)
        self.assertIn('address', data)

    def test_address_field_content(self):
        data = self.serializer.data
        expected_address = f"{self.tree.strasse} {self.tree.hausnummer}"
        self.assertEqual(data['address'], expected_address)
