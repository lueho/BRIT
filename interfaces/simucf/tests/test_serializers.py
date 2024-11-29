import re

from django.test import TestCase

from materials.models import (Composition, Material, MaterialComponent, MaterialComponentGroup, Sample, SampleSeries,
                              WeightShare)
from ..input_file_template import template_string
from ..models import InputMaterial
from ..serializers import SimuCF, SimuCFSerializer


class MaterialSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        material = Material.objects.create(name='Test Material')
        series = SampleSeries.objects.create(name='Test Series', material=material)
        sample = Sample.objects.create(name='Test Sample', material=material, series=series)
        group = MaterialComponentGroup.objects.create(name='Biochemical Composition')
        composition = Composition.objects.create(group=group, sample=sample)
        component_names = [
            'Carbohydrates', 'Amino Acids', 'Starches', 'Hemicellulose', 'Fats',
            'Waxes', 'Proteins', 'Cellulose', 'Lignin'
        ]
        for name in component_names:
            component = MaterialComponent.objects.create(name=name)
            WeightShare.objects.create(name=name, composition=composition, component=component, average=0.7)

    def setUp(self):
        self.input_material = InputMaterial.objects.get(name='Test Sample')

    def test_serializer_fields_match_template_placeholders_exactly(self):
        simucf = SimuCF(material=self.input_material, amount=100, length_of_treatment=10)
        serializer = SimuCFSerializer(simucf)
        placeholders = re.findall('\$\w+', template_string)
        for placeholder in placeholders:
            self.assertIn(placeholder[1:], serializer.data)
        for key in serializer.data.keys():
            self.assertIn(f'${key}', placeholders)

    def test_serializer_list_field_method(self):
        simucf = SimuCF(material=self.input_material, amount=100, length_of_treatment=10)
        SimuCFSerializer(simucf)
