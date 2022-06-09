import re

from django.test import TestCase

from materials.models import Composition, Material, MaterialComponent, MaterialComponentGroup, Sample, SampleSeries, \
    WeightShare
from users.models import get_default_owner

from ..input_file_template import template_string
from ..models import InputMaterial
from ..serializers import SimuCFSerializer, SimuCF


class MaterialSerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        sample = Sample.objects.create(owner=owner, name='Test Sample', series=series)
        group = MaterialComponentGroup.objects.create(owner=owner, name='Biochemical Composition')
        composition = Composition.objects.create(owner=owner, group=group, sample=sample)
        component_names = [
            'Carbohydrates', 'Amino Acids', 'Starches', 'Hemicellulose', 'Fats',
            'Waxes', 'Proteins', 'Cellulose', 'Lignin'
        ]
        for name in component_names:
            component = MaterialComponent.objects.create(owner=owner, name=name)
            WeightShare.objects.create(
                owner=owner, name=name, composition=composition,
                component=component, average=0.7)

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
        serializer = SimuCFSerializer(simucf)
        print(serializer.data)