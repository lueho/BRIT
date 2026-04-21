from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from utils.properties.models import Unit

from ..composition_normalization import get_sample_normalized_compositions
from ..models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Sample,
    SampleSeries,
    WeightShare,
)


class SampleCompositionNormalizationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="sample-normalization-owner",
            password="test123",
        )
        cls.material = Material.objects.create(
            name="Test Material",
            type="material",
            owner=cls.owner,
        )
        cls.series = SampleSeries.objects.create(
            name="Test Series",
            material=cls.material,
            owner=cls.owner,
        )
        cls.percent_unit = Unit.objects.filter(name="%").first()
        if cls.percent_unit is None:
            cls.percent_unit = Unit.objects.create(name="%", symbol="percent")
        elif not cls.percent_unit.symbol:
            cls.percent_unit.symbol = "percent"
            cls.percent_unit.save(update_fields=["symbol"])

    def test_prefers_raw_measurements_per_group_and_warns_on_mismatch(self):
        sample = Sample.objects.create(
            name="Mixed Raw Group",
            material=self.material,
            series=self.series,
            publication_status="published",
            owner=self.owner,
        )
        sample.compositions.all().delete()
        group = MaterialComponentGroup.objects.create(
            name="Macronutrients",
            publication_status="published",
            owner=self.owner,
        )
        phosphorus = MaterialComponent.objects.create(
            name="Phosphorus",
            publication_status="published",
            owner=self.owner,
        )
        potassium = MaterialComponent.objects.create(
            name="Potassium",
            publication_status="published",
            owner=self.owner,
        )
        persisted = Composition.objects.create(
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default(),
            owner=self.owner,
        )
        WeightShare.objects.create(
            composition=persisted,
            component=phosphorus,
            average=Decimal("0.2"),
            standard_deviation=Decimal("0.0"),
            owner=self.owner,
        )
        WeightShare.objects.create(
            composition=persisted,
            component=potassium,
            average=Decimal("0.8"),
            standard_deviation=Decimal("0.0"),
            owner=self.owner,
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=phosphorus,
            unit=self.percent_unit,
            average=Decimal("70"),
            owner=self.owner,
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=potassium,
            unit=self.percent_unit,
            average=Decimal("30"),
            owner=self.owner,
        )

        compositions = get_sample_normalized_compositions(sample)

        self.assertEqual(len(compositions), 1)
        composition = compositions[0]
        self.assertTrue(composition["is_derived"])
        self.assertEqual(composition["origin"], "raw_derived")
        self.assertEqual(
            {share["as_percentage"] for share in composition["shares"]},
            {"70.0%", "30.0%"},
        )
        self.assertEqual(composition["settings_pk"], persisted.pk)
        self.assertEqual(composition["warning_count"], 1)
        self.assertIn("saved normalized composition", composition["warnings"][0])

    def test_uses_persisted_fallback_for_groups_without_raw_measurements(self):
        sample = Sample.objects.create(
            name="Persisted Fallback Group",
            material=self.material,
            series=self.series,
            publication_status="published",
            owner=self.owner,
        )
        sample.compositions.all().delete()
        group = MaterialComponentGroup.objects.create(
            name="Fallback Group",
            publication_status="published",
            owner=self.owner,
        )
        protein = MaterialComponent.objects.create(
            name="Protein",
            publication_status="published",
            owner=self.owner,
        )
        persisted = Composition.objects.create(
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default(),
            owner=self.owner,
        )
        WeightShare.objects.create(
            composition=persisted,
            component=protein,
            average=Decimal("1.0"),
            standard_deviation=Decimal("0.0"),
            owner=self.owner,
        )

        compositions = get_sample_normalized_compositions(sample)

        self.assertEqual(len(compositions), 1)
        composition = compositions[0]
        self.assertFalse(composition["is_derived"])
        self.assertEqual(composition["origin"], "persisted_fallback")
        self.assertEqual(composition["warning_count"], 0)
        self.assertEqual(composition["shares"][0]["as_percentage"], "100.0 ± 0.0%")

    def test_resolves_mixed_state_per_group_with_settings_order(self):
        sample = Sample.objects.create(
            name="Mixed-State Sample",
            material=self.material,
            series=self.series,
            publication_status="published",
            owner=self.owner,
        )
        sample.compositions.all().delete()
        persisted_group = MaterialComponentGroup.objects.create(
            name="Persisted Group",
            publication_status="published",
            owner=self.owner,
        )
        raw_group = MaterialComponentGroup.objects.create(
            name="Raw Group",
            publication_status="published",
            owner=self.owner,
        )
        protein = MaterialComponent.objects.create(
            name="Protein A",
            publication_status="published",
            owner=self.owner,
        )
        carbon = MaterialComponent.objects.create(
            name="Carbon A",
            publication_status="published",
            owner=self.owner,
        )
        Composition.objects.create(
            sample=sample,
            group=persisted_group,
            fractions_of=MaterialComponent.objects.default(),
            order=100,
            owner=self.owner,
        ).add_component(
            protein,
            average=Decimal("1.0"),
            standard_deviation=Decimal("0.0"),
        )
        Composition.objects.create(
            sample=sample,
            group=raw_group,
            fractions_of=MaterialComponent.objects.default(),
            order=110,
            owner=self.owner,
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=raw_group,
            component=carbon,
            unit=self.percent_unit,
            average=Decimal("100"),
            owner=self.owner,
        )

        compositions = get_sample_normalized_compositions(sample)

        self.assertEqual(
            [composition["group_name"] for composition in compositions],
            [
                "Persisted Group",
                "Raw Group",
            ],
        )
        self.assertEqual(
            [composition["origin"] for composition in compositions],
            ["persisted_fallback", "raw_derived"],
        )
