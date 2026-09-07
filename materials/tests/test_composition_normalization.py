from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from utils.properties.models import Unit

from ..composition_normalization import (
    WARNING_LEGACY_OTHER_IGNORED,
    WARNING_REMAINING_FRACTION_ASSIGNED_TO_OTHER,
    WARNING_SHARES_SCALED_TO_100,
    get_sample_normalized_compositions,
)
from ..models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Sample,
    SampleSeries,
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

    def test_prefers_raw_measurements_per_group(self):
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
        self.assertEqual(composition["warning_count"], 0)

    def _sample_with_group(self, name):
        sample = Sample.objects.create(
            name=name,
            material=self.material,
            series=self.series,
            publication_status="published",
            owner=self.owner,
        )
        sample.compositions.all().delete()
        group = MaterialComponentGroup.objects.create(
            name=f"{name} Group",
            publication_status="published",
            owner=self.owner,
        )
        return sample, group

    def _measure(self, sample, group, component, average):
        if isinstance(component, str):
            component = MaterialComponent.objects.create(
                name=component,
                publication_status="published",
                owner=self.owner,
            )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=component,
            unit=self.percent_unit,
            average=Decimal(average),
            owner=self.owner,
        )

    def test_scales_shares_down_when_raw_sum_exceeds_100(self):
        sample, group = self._sample_with_group("Over 100")
        self._measure(sample, group, "Carbon", "60")
        self._measure(sample, group, "Nitrogen", "60")

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [share["as_percentage"] for share in composition["shares"]],
            ["50.0%", "50.0%"],
        )
        self.assertAlmostEqual(
            sum(share["average"] for share in composition["shares"]), 1.0
        )
        self.assertIn(WARNING_SHARES_SCALED_TO_100, composition["warning_codes"])
        self.assertEqual(composition["share_total_percent"], 100.0)
        self.assertEqual(
            [share["percent"] for share in composition["shares"]], [50.0, 50.0]
        )
        self.assertNotIn(
            MaterialComponent.objects.other().pk,
            [share["component"] for share in composition["shares"]],
        )

    def test_fills_gap_below_100_with_other(self):
        sample, group = self._sample_with_group("Under 100")
        self._measure(sample, group, "Carbon", "40")

        composition = get_sample_normalized_compositions(sample)[0]

        other = MaterialComponent.objects.other()
        self.assertEqual(
            [
                (share["component"], share["as_percentage"])
                for share in composition["shares"]
            ][-1],
            (other.pk, "60.0%"),
        )
        self.assertIn(
            WARNING_REMAINING_FRACTION_ASSIGNED_TO_OTHER, composition["warning_codes"]
        )

    def test_legacy_other_measurements_are_ignored(self):
        sample, group = self._sample_with_group("Legacy Other")
        other = MaterialComponent.objects.other()
        self._measure(sample, group, "Carbon", "40")
        self._measure(sample, group, other, "70")

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [
                (share["component_name"], share["as_percentage"])
                for share in composition["shares"]
            ],
            [("Carbon", "40.0%"), (other.name, "60.0%")],
        )
        self.assertIn(WARNING_LEGACY_OTHER_IGNORED, composition["warning_codes"])

    def test_other_only_group_yields_no_derived_composition(self):
        sample, group = self._sample_with_group("Only Other")
        self._measure(sample, group, MaterialComponent.objects.other(), "100")

        self.assertEqual(get_sample_normalized_compositions(sample), [])

    def test_resolves_raw_groups_with_settings_order(self):
        sample = Sample.objects.create(
            name="Mixed-State Sample",
            material=self.material,
            series=self.series,
            publication_status="published",
            owner=self.owner,
        )
        sample.compositions.all().delete()
        first_group = MaterialComponentGroup.objects.create(
            name="First Raw Group",
            publication_status="published",
            owner=self.owner,
        )
        second_group = MaterialComponentGroup.objects.create(
            name="Second Raw Group",
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
            group=first_group,
            fractions_of=MaterialComponent.objects.default(),
            order=100,
            owner=self.owner,
        )
        Composition.objects.create(
            sample=sample,
            group=second_group,
            fractions_of=MaterialComponent.objects.default(),
            order=110,
            owner=self.owner,
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=first_group,
            component=protein,
            unit=self.percent_unit,
            average=Decimal("100"),
            owner=self.owner,
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=second_group,
            component=carbon,
            unit=self.percent_unit,
            average=Decimal("100"),
            owner=self.owner,
        )

        compositions = get_sample_normalized_compositions(sample)

        self.assertEqual(
            [composition["group_name"] for composition in compositions],
            [
                "First Raw Group",
                "Second Raw Group",
            ],
        )
        self.assertEqual(
            [composition["origin"] for composition in compositions],
            ["raw_derived", "raw_derived"],
        )
