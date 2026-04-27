from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from materials.models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Sample,
    SampleSeries,
    WeightShare,
)
from utils.properties.models import Unit

from ..models import InputMaterial


class InputMaterialManagerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(name="Test Series", material=material)
        suitable_sample = Sample.objects.create(
            name="Suitable Sample", material=material, series=series
        )
        Sample.objects.create(
            name="Unsuitable Sample", material=material, series=series
        )
        unsuitable_sample = Sample.objects.create(
            name="Unsuitable Sample", material=material, series=series
        )
        group = MaterialComponentGroup.objects.create(name="Biochemical Composition")
        Composition.objects.create(group=group, sample=unsuitable_sample)
        composition = Composition.objects.create(group=group, sample=suitable_sample)
        component_names = [
            "Carbohydrates",
            "Amino Acids",
            "Starches",
            "Hemicellulose",
            "Fats",
            "Waxes",
            "Proteins",
            "Cellulose",
            "Lignin",
        ]
        for name in component_names:
            component = MaterialComponent.objects.create(name=name)
            WeightShare.objects.create(
                name=name, composition=composition, component=component, average=0.7
            )

    def test_filter_returns_only_suitable_samples(self):
        qs = InputMaterial.objects.all().order_by("name")
        self.assertQuerySetEqual(
            qs, InputMaterial.objects.filter(name="Suitable Sample")
        )


class InputMaterialTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(name="Test Series", material=material)
        sample = Sample.objects.create(
            name="Test Sample", material=material, series=series
        )
        group = MaterialComponentGroup.objects.create(name="Biochemical Composition")
        composition = Composition.objects.create(group=group, sample=sample)
        component_names = [
            "Carbohydrates",
            "Amino Acids",
            "Starches",
            "Hemicellulose",
            "Fats",
            "Waxes",
            "Proteins",
            "Cellulose",
            "Lignin",
        ]
        for name in component_names:
            component = MaterialComponent.objects.create(name=name)
            WeightShare.objects.create(
                name=name, composition=composition, component=component, average=0.7
            )

    def setUp(self):
        self.input = InputMaterial.objects.get(name="Test Sample")

    def test_property_composition_throws_improperly_configured_error_when_composition_is_not_setup(
        self,
    ):
        Composition.objects.get(group__name="Biochemical Composition").delete()
        with self.assertRaises(ImproperlyConfigured):
            self.assertEqual(
                self.input.composition.group.name, "Biochemical Composition"
            )

    def test_property_composition_returns_correct_composition(self):
        self.assertEqual(self.input.composition.group.name, "Biochemical Composition")

    def test_property_carbohydrates_handles_missing_weightshare(self):
        WeightShare.objects.get(name="Carbohydrates").delete()
        self.assertEqual(self.input.carbohydrates, Decimal("0.0000000000"))

    def test_property_carbohydrates_returns_valid_value(self):
        self.assertEqual(self.input.carbohydrates, Decimal("0.7000000000"))

    def test_property_carbohydrates_uses_raw_derived_share(self):
        percent_unit = Unit.objects.filter(name="%").first()
        if percent_unit is None:
            percent_unit = Unit.objects.create(name="%", symbol="percent")
        composition = Composition.objects.get(group__name="Biochemical Composition")
        carbohydrates = MaterialComponent.objects.get(name="Carbohydrates")
        amino_acids = MaterialComponent.objects.get(name="Amino Acids")
        ComponentMeasurement.objects.create(
            sample=self.input,
            group=composition.group,
            component=carbohydrates,
            unit=percent_unit,
            average=Decimal("40"),
        )
        ComponentMeasurement.objects.create(
            sample=self.input,
            group=composition.group,
            component=amino_acids,
            unit=percent_unit,
            average=Decimal("60"),
        )

        self.assertEqual(self.input.carbohydrates, Decimal("0.4"))

    def test_property_amino_acids_handles_missing_weightshare(self):
        WeightShare.objects.get(name="Amino Acids").delete()
        self.assertEqual(self.input.amino_acids, Decimal("0.0000000000"))

    def test_property_amino_acids_returns_valid_value(self):
        self.assertEqual(self.input.amino_acids, Decimal("0.7000000000"))

    def test_property_starch_handles_missing_weightshare(self):
        WeightShare.objects.get(name="Starches").delete()
        self.assertEqual(self.input.starch, Decimal("0.0000000000"))

    def test_property_starch_returns_valid_value(self):
        self.assertEqual(self.input.starch, Decimal("0.7000000000"))

    def test_property_hemicellulose_handles_missing_weightshare(self):
        WeightShare.objects.get(name="Hemicellulose").delete()
        self.assertEqual(self.input.hemicellulose, Decimal("0.0000000000"))

    def test_property_hemicellulose_returns_valid_value(self):
        self.assertEqual(self.input.hemicellulose, Decimal("0.7000000000"))

    def test_property_fats_handles_missing_weightshare(self):
        WeightShare.objects.get(name="Fats").delete()
        self.assertEqual(self.input.fats, Decimal("0.0000000000"))

    def test_property_fats_returns_valid_value(self):
        self.assertEqual(self.input.fats, Decimal("0.7000000000"))

    def test_property_waxs_handles_missing_weightshare(self):
        WeightShare.objects.get(name="Waxes").delete()
        self.assertEqual(self.input.waxs, Decimal("0.0000000000"))

    def test_property_waxs_returns_valid_value(self):
        self.assertEqual(self.input.waxs, Decimal("0.7000000000"))

    def test_property_proteins_handles_missing_weightshare(self):
        WeightShare.objects.get(name="Proteins").delete()
        self.assertEqual(self.input.proteins, Decimal("0.0000000000"))

    def test_property_proteins_returns_valid_value(self):
        self.assertEqual(self.input.proteins, Decimal("0.7000000000"))

    def test_property_cellulose_handles_missing_weightshare(self):
        WeightShare.objects.get(name="Cellulose").delete()
        self.assertEqual(self.input.cellulose, Decimal("0.0000000000"))

    def test_property_cellulose_returns_valid_value(self):
        self.assertEqual(self.input.cellulose, Decimal("0.7000000000"))

    def test_property_lignin_handles_missing_weightshare(self):
        WeightShare.objects.get(name="Lignin").delete()
        self.assertEqual(self.input.lignin, Decimal("0.0000000000"))

    def test_property_lignin_returns_valid_value(self):
        self.assertEqual(self.input.lignin, Decimal("0.7000000000"))
