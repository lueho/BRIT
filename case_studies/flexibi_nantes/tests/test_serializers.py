from django.test import TestCase

from ..models import NantesGreenhouses
from ..serializers import NantesGreenhousesFlatSerializer


class NantesGreenHousesFlatSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.greenhouse = NantesGreenhouses.objects.create(
            nb_cycles=3,
            culture_1="tomato",
            culture_2="cucumber",
            culture_3="pepper",
            heated=True,
            lighted=True,
            high_wire=True,
            above_ground=True,
            surface_ha=1.0,
        )

    def test_serializer_construction(self):
        serializer = NantesGreenhousesFlatSerializer()
        self.assertIsNotNone(serializer)

    def test_serializer_fields(self):
        serializer = NantesGreenhousesFlatSerializer(self.greenhouse)
        self.assertIsNotNone(serializer.data)
        self.assertEqual(serializer.data["nb_cycles"], 3)
        self.assertEqual(serializer.data["culture_1"], "tomato")
        self.assertEqual(serializer.data["culture_2"], "cucumber")
        self.assertEqual(serializer.data["culture_3"], "pepper")
        self.assertEqual(serializer.data["heated"], True)
        self.assertEqual(serializer.data["lighted"], True)
        self.assertEqual(serializer.data["high_wire"], True)
        self.assertEqual(serializer.data["above_ground"], True)
        self.assertEqual(serializer.data["surface_ha"], 1.0)
