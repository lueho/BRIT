from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from materials.models import Composition, Material, MaterialComponent, MaterialComponentGroup, Sample, SampleSeries, \
    WeightShare
from users.models import get_default_owner
from ..models import InputMaterial


class InputMaterialManagerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        material = Material.objects.create(owner=owner, name='Test Material')
        series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
        suitable_sample = Sample.objects.create(owner=owner, name='Suitable Sample', series=series)
        Sample.objects.create(owner=owner, name='Unsuitable Sample', series=series)
        unsuitable_sample = Sample.objects.create(owner=owner, name='Unsuitable Sample', series=series)
        group = MaterialComponentGroup.objects.create(owner=owner, name='Biochemical Composition')
        Composition.objects.create(owner=owner, group=group, sample=unsuitable_sample)
        composition = Composition.objects.create(owner=owner, group=group, sample=suitable_sample)
        component_names = [
            'Carbohydrates', 'Amino Acids', 'Starches', 'Hemicellulose', 'Fats',
            'Waxes', 'Proteins', 'Cellulose', 'Lignin'
        ]
        for name in component_names:
            component = MaterialComponent.objects.create(owner=owner, name=name)
            WeightShare.objects.create(
                owner=owner, name=name, composition=composition,
                component=component, average=0.7)

    def test_filter_returns_only_suitable_samples(self):
        qs = InputMaterial.objects.all().order_by('name')
        self.assertQuerysetEqual(qs, InputMaterial.objects.filter(name='Suitable Sample'))


class InputMaterialTestCase(TestCase):

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
        self.input = InputMaterial.objects.get(name='Test Sample')

    def test_property_composition_throws_improperly_configured_error_when_composition_is_not_setup(self):
        Composition.objects.get(group__name='Biochemical Composition').delete()
        with self.assertRaises(ImproperlyConfigured):
            self.assertEqual(self.input.composition.group.name, 'Biochemical Composition')

    def test_property_composition_returns_correct_composition(self):
        self.assertEqual(self.input.composition.group.name, 'Biochemical Composition')

    def test_property_carbohydrates_handles_missing_weightshare(self):
        WeightShare.objects.get(name='Carbohydrates').delete()
        self.assertEqual(self.input.carbohydrates, 0.0)

    def test_property_carbohydrates_returns_valid_value(self):
        self.assertEqual(self.input.carbohydrates, 0.7)

    def test_property_amino_acids_handles_missing_weightshare(self):
        WeightShare.objects.get(name='Amino Acids').delete()
        self.assertEqual(self.input.amino_acids, 0.0)

    def test_property_amino_acids_returns_valid_value(self):
        self.assertEqual(self.input.amino_acids, 0.7)

    def test_property_starch_handles_missing_weightshare(self):
        WeightShare.objects.get(name='Starches').delete()
        self.assertEqual(self.input.starch, 0.0)

    def test_property_starch_returns_valid_value(self):
        self.assertEqual(self.input.starch, 0.7)

    def test_property_hemicellulose_handles_missing_weightshare(self):
        WeightShare.objects.get(name='Hemicellulose').delete()
        self.assertEqual(self.input.hemicellulose, 0.0)

    def test_property_hemicellulose_returns_valid_value(self):
        self.assertEqual(self.input.hemicellulose, 0.7)

    def test_property_fats_handles_missing_weightshare(self):
        WeightShare.objects.get(name='Fats').delete()
        self.assertEqual(self.input.fats, 0.0)

    def test_property_fats_returns_valid_value(self):
        self.assertEqual(self.input.fats, 0.7)

    def test_property_waxs_handles_missing_weightshare(self):
        WeightShare.objects.get(name='Waxes').delete()
        self.assertEqual(self.input.waxs, 0.0)

    def test_property_waxs_returns_valid_value(self):
        self.assertEqual(self.input.waxs, 0.7)

    def test_property_proteins_handles_missing_weightshare(self):
        WeightShare.objects.get(name='Proteins').delete()
        self.assertEqual(self.input.proteins, 0.0)

    def test_property_proteins_returns_valid_value(self):
        self.assertEqual(self.input.proteins, 0.7)

    def test_property_cellulose_handles_missing_weightshare(self):
        WeightShare.objects.get(name='Cellulose').delete()
        self.assertEqual(self.input.cellulose, 0.0)

    def test_property_cellulose_returns_valid_value(self):
        self.assertEqual(self.input.cellulose, 0.7)

    def test_property_lignin_handles_missing_weightshare(self):
        WeightShare.objects.get(name='Lignin').delete()
        self.assertEqual(self.input.lignin, 0.0)

    def test_property_lignin_returns_valid_value(self):
        self.assertEqual(self.input.lignin, 0.7)
