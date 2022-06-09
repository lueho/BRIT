from django.test import TestCase
from django.urls import reverse

from materials.models import Composition, Material, MaterialComponent, MaterialComponentGroup, Sample, SampleSeries, \
    WeightShare
from users.models import get_default_owner

from ..models import InputMaterial


class SimuCFModelFormViewTestCase(TestCase):

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

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('simucf-form'))
        self.assertEqual(200, response.status_code)

    def test_get_returns_file(self):
        data = {
            'input_material': self.input_material.id,
            'amount': 100,
            'length_of_treatment': 30
        }
        response = self.client.post(reverse('simucf-form'), data=data)
        self.assertEqual(response.get('Content-Disposition'), 'attachment; filename="simucf-input.txt"')
