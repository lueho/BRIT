from django.urls import reverse

from materials.models import Composition, Material, MaterialComponent, MaterialComponentGroup, Sample, SampleSeries, \
    WeightShare
from utils.tests.testcases import ViewWithPermissionsTestCase
from ..models import InputMaterial


class SimuCFModelFormViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
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
            WeightShare.objects.create(
                name=name, composition=composition,
                component=component, average=0.7)

        cls.input_material = InputMaterial.objects.get(name='Test Sample')

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
