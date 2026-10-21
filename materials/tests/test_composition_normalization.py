from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from utils.properties.models import Unit

from ..composition_normalization import (
    WARNING_AGGREGATE_COMPONENTS_EXCLUDED,
    WARNING_LEGACY_OTHER_IGNORED,
    WARNING_REMAINING_FRACTION_ASSIGNED_TO_OTHER,
    WARNING_SHARES_SCALED_TO_100,
    get_sample_normalized_compositions,
    get_sorted_component_measurements,
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

    def _measure(
        self, sample, group, component, average, unit=None, basis=None, **kwargs
    ):
        if isinstance(component, str):
            component = MaterialComponent.objects.create(
                name=component,
                publication_status="published",
                owner=self.owner,
            )
        return ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=component,
            basis_component=basis,
            unit=unit or self.percent_unit,
            average=Decimal(average),
            owner=self.owner,
            **kwargs,
        )

    def test_converts_weight_fraction_units_to_percent_before_normalizing(self):
        sample, group = self._sample_with_group("Mixed Units")
        g_per_kg = Unit.objects.create(name="g/kg", symbol="g/kg", owner=self.owner)
        self._measure(sample, group, "Carbon", "300", unit=g_per_kg)
        self._measure(sample, group, "Nitrogen", "20")

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [(s["component_name"], s["percent"]) for s in composition["shares"]],
            [("Carbon", 30.0), ("Nitrogen", 20.0), ("Other", 50.0)],
        )
        self.assertEqual(composition["warnings"], [])

    def test_converts_mg_per_kg_to_percent(self):
        sample, group = self._sample_with_group("Trace")
        mg_per_kg = Unit.objects.create(name="mg/kg", symbol="mg/kg", owner=self.owner)
        self._measure(sample, group, "Zinc", "5000", unit=mg_per_kg)

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [(s["component_name"], s["percent"]) for s in composition["shares"]],
            [("Zinc", 0.5), ("Other", 99.5)],
        )

    def test_converts_units_on_dry_matter_basis_too(self):
        sample, group = self._sample_with_group("DM Units")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        g_per_kg = Unit.objects.create(name="g/kg", symbol="g/kg", owner=self.owner)
        self._measure(sample, group, "Carbon", "400", unit=g_per_kg, basis=dm)
        self._measure(sample, group, "Nitrogen", "10", basis=dm)

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [s["as_percentage"] for s in composition["shares"]],
            ["40.0% of DM", "10.0% of DM", "50.0% of DM"],
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

    def test_share_total_is_not_a_sum_of_rounded_shares(self):
        sample, group = self._sample_with_group("Thirds")
        for name in ("Carbon", "Nitrogen", "Oxygen"):
            self._measure(sample, group, name, "50")

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [share["percent"] for share in composition["shares"]], [33.3, 33.3, 33.3]
        )
        self.assertEqual(composition["share_total_percent"], 100.0)

    def test_aggregate_components_are_excluded_from_shares(self):
        sample, group = self._sample_with_group("Aggregate Total")
        total = MaterialComponent.objects.create(
            name="Total (with halides)",
            publication_status="published",
            owner=self.owner,
            is_aggregate=True,
        )
        self._measure(sample, group, "Carbon", "40")
        self._measure(sample, group, "Oxygen", "30")
        self._measure(sample, group, total, "100")

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [(s["component_name"], s["percent"]) for s in composition["shares"]],
            [("Carbon", 40.0), ("Oxygen", 30.0), ("Other", 30.0)],
        )
        self.assertIn(
            WARNING_AGGREGATE_COMPONENTS_EXCLUDED, composition["warning_codes"]
        )
        self.assertIn("Total (with halides)", composition["warnings"][0])

    def test_aggregate_only_group_yields_no_derived_composition(self):
        sample, group = self._sample_with_group("Only Total")
        total = MaterialComponent.objects.create(
            name="Total (with halides)",
            publication_status="published",
            owner=self.owner,
            is_aggregate=True,
        )
        self._measure(sample, group, total, "100")

        self.assertEqual(get_sample_normalized_compositions(sample), [])

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

    def test_non_compositional_group_is_not_normalized(self):
        sample, group = self._sample_with_group("Non Compositional")
        group.is_compositional = False
        group.save(update_fields=["is_compositional"])
        measurement = self._measure(sample, group, "Carbon", "40")

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(composition["shares"], [])
        self.assertEqual(composition["normalization_status"], "unavailable")
        self.assertEqual(composition["warning_codes"], ["non_compositional_group"])
        self.assertIsNone(composition["fractions_of"])
        measurement.refresh_from_db()
        self.assertEqual(measurement.average, Decimal("40"))
        self.assertEqual(measurement.value_qualifier, "exact")

    def test_mixed_basis_components_are_blocked(self):
        sample, group = self._sample_with_group("Mixed Bases")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        fm = MaterialComponent.objects.create(name="Fresh matter", owner=self.owner)
        self._measure(sample, group, "Carbon", "40", basis=dm)
        self._measure(sample, group, "Nitrogen", "10", basis=fm)

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(composition["shares"], [])
        self.assertEqual(composition["normalization_status"], "unavailable")
        self.assertEqual(composition["warning_codes"], ["multiple_basis_components"])

    def test_mixed_basis_with_missing_basis_is_blocked(self):
        sample, group = self._sample_with_group("Mixed Missing Basis")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        self._measure(sample, group, "Carbon", "40", basis=dm)
        self._measure(sample, group, "Nitrogen", "10")

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(composition["shares"], [])
        self.assertEqual(composition["warning_codes"], ["multiple_basis_components"])

    def test_same_basis_components_remain_normalized(self):
        sample, group = self._sample_with_group("Same Basis")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        self._measure(sample, group, "Carbon", "40", basis=dm)
        self._measure(sample, group, "Nitrogen", "10", basis=dm)

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(composition["normalization_status"], "normalized")
        self.assertEqual(
            [share["percent"] for share in composition["shares"]],
            [40.0, 10.0, 50.0],
        )
        self.assertEqual(composition["fractions_of"], dm.pk)

    def test_configured_basis_mismatch_is_blocked(self):
        sample, group = self._sample_with_group("Basis Mismatch")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        fm = MaterialComponent.objects.create(name="Fresh matter", owner=self.owner)
        Composition.objects.create(
            sample=sample, group=group, fractions_of=fm, owner=self.owner
        )
        self._measure(sample, group, "Carbon", "40", basis=dm)

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(composition["shares"], [])
        self.assertEqual(composition["warning_codes"], ["configured_basis_mismatch"])

    def test_repeated_component_observations_are_blocked(self):
        sample, group = self._sample_with_group("Repeated Component")
        carbon = MaterialComponent.objects.create(name="Carbon", owner=self.owner)
        self._measure(sample, group, carbon, "40")
        self._measure(sample, group, carbon, "42")

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(composition["shares"], [])
        self.assertEqual(
            composition["warning_codes"], ["repeated_component_measurements"]
        )

    def test_censored_measurements_are_approximated_as_zero(self):
        sample, group = self._sample_with_group("Censored")
        self._measure(sample, group, "Carbon", "40")
        censored = self._measure(
            sample,
            group,
            "Nitrogen",
            "0.1",
            raw_value="<0.1",
            value_qualifier="less_than",
        )
        below_dl = self._measure(
            sample,
            group,
            "Sulfur",
            "0.2",
            value_qualifier="below_detection_limit",
        )
        trace = self._measure(
            sample,
            group,
            "Trace element",
            "0",
            raw_value="<0",
            value_qualifier="less_than",
        )

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(composition["normalization_status"], "normalized")
        self.assertEqual(
            [(s["component_name"], s["percent"]) for s in composition["shares"]],
            [("Carbon", 40.0), ("Other", 60.0)],
        )
        self.assertIn(
            "censored_values_approximated_as_zero", composition["warning_codes"]
        )
        for measurement, qualifier in (
            (censored, "less_than"),
            (below_dl, "below_detection_limit"),
            (trace, "less_than"),
        ):
            measurement.refresh_from_db()
            self.assertEqual(measurement.value_qualifier, qualifier)
        self.assertEqual(censored.average, Decimal("0.1"))
        self.assertEqual(below_dl.average, Decimal("0.2"))
        self.assertEqual(trace.average, Decimal("0"))

    def test_censored_only_group_is_unavailable_without_fabricated_other(self):
        sample, group = self._sample_with_group("Censored Only")
        self._measure(
            sample,
            group,
            "Carbon",
            "0.1",
            raw_value="<0.1",
            value_qualifier="less_than",
        )

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(composition["shares"], [])
        self.assertEqual(composition["normalization_status"], "unavailable")
        self.assertEqual(
            composition["warning_codes"], ["censored_values_approximated_as_zero"]
        )
        self.assertIsNone(composition["share_total_percent"])

    def test_unsupported_qualifiers_are_blocked(self):
        for qualifier in ("greater_than", "range", "estimated"):
            with self.subTest(qualifier=qualifier):
                sample, group = self._sample_with_group(f"Qualifier {qualifier}")
                self._measure(
                    sample,
                    group,
                    f"Carbon {qualifier}",
                    "40",
                    value_qualifier=qualifier,
                )
                composition = get_sample_normalized_compositions(sample)[0]
                self.assertEqual(composition["shares"], [])
                self.assertEqual(
                    composition["warning_codes"], ["unsupported_value_qualifier"]
                )

    def test_invalid_measurement_values_are_blocked(self):
        cases = (
            {"average": "-1"},
            {"average": "40", "standard_deviation": Decimal("-0.5")},
            {"average": "40", "detection_limit": Decimal("-0.5")},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                sample, group = self._sample_with_group(f"Invalid {sorted(kwargs)}")
                self._measure(sample, group, f"Carbon {sorted(kwargs)}", **kwargs)
                composition = get_sample_normalized_compositions(sample)[0]
                self.assertEqual(composition["shares"], [])
                self.assertEqual(
                    composition["warning_codes"], ["invalid_measurement_value"]
                )

    def test_individual_mass_fraction_above_100_is_blocked(self):
        sample, group = self._sample_with_group("Over 100 Percent")
        self._measure(sample, group, "Carbon", "101")
        composition = get_sample_normalized_compositions(sample)[0]
        self.assertEqual(composition["shares"], [])
        self.assertEqual(composition["warning_codes"], ["invalid_mass_fraction"])

        sample, group = self._sample_with_group("Over 100 MgKg")
        mg_per_kg = Unit.objects.create(name="mg/kg", symbol="mg/kg", owner=self.owner)
        self._measure(sample, group, "Zinc", "1000001", unit=mg_per_kg)
        composition = get_sample_normalized_compositions(sample)[0]
        self.assertEqual(composition["shares"], [])
        self.assertEqual(composition["warning_codes"], ["invalid_mass_fraction"])

    def test_non_finite_measurement_values_do_not_crash_sorting(self):
        for non_finite in (
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
        ):
            with self.subTest(average=non_finite):
                sample, group = self._sample_with_group(f"Non Finite {non_finite}")
                first = self._measure(sample, group, f"Carbon {non_finite}", "40")
                second = self._measure(sample, group, f"Nitrogen {non_finite}", "10")
                first.average = non_finite

                sorted_measurements = get_sorted_component_measurements(
                    sample, component_measurements=[first, second]
                )
                composition = get_sample_normalized_compositions(
                    sample, component_measurements=sorted_measurements
                )[0]

                self.assertEqual(composition["shares"], [])
                self.assertEqual(
                    composition["warning_codes"], ["invalid_measurement_value"]
                )

    def test_non_weight_fraction_unit_is_blocked(self):
        sample, group = self._sample_with_group("Becquerel")
        bq_per_kg = Unit.objects.create(name="Bq/kg", symbol="Bq/kg", owner=self.owner)
        self._measure(sample, group, "Cesium-137", "40", unit=bq_per_kg)

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(composition["shares"], [])
        self.assertEqual(composition["warning_codes"], ["invalid_units"])

    def _other_group(self, name):
        return MaterialComponentGroup.objects.create(
            name=name,
            publication_status="published",
            owner=self.owner,
        )

    def _compositions_by_group_name(self, sample):
        return {
            composition["group_name"]: composition
            for composition in get_sample_normalized_compositions(sample)
        }

    def test_residual_gap_is_decomposed_into_other_group_components(self):
        sample, biochemical = self._sample_with_group("Cross Decomposition")
        proximate = self._other_group("Proximate Analysis")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        organic_matter = MaterialComponent.objects.create(
            name="Organic matter", owner=self.owner
        )
        ash = MaterialComponent.objects.create(
            name="Total Ash",
            owner=self.owner,
            basis_component=dm,
            complement_component=organic_matter,
        )
        self._measure(sample, biochemical, "Cellulose", "70.2", basis=dm)
        self._measure(sample, biochemical, "Hemicellulose", "21.8", basis=dm)
        self._measure(sample, biochemical, "Lignin", "5.7", basis=dm)
        self._measure(sample, proximate, ash, "2.3", basis=dm)

        compositions = self._compositions_by_group_name(sample)

        biochemical_composition = compositions["Cross Decomposition Group"]
        self.assertEqual(
            [
                (share["component_name"], share["percent"], share["inferred"])
                for share in biochemical_composition["shares"]
            ],
            [
                ("Cellulose", 70.2, False),
                ("Hemicellulose", 21.8, False),
                ("Lignin", 5.7, False),
                ("Total Ash", 2.3, True),
            ],
        )
        self.assertNotIn(
            WARNING_REMAINING_FRACTION_ASSIGNED_TO_OTHER,
            biochemical_composition["warning_codes"],
        )
        self.assertIn(
            "remaining_fraction_decomposed",
            biochemical_composition["warning_codes"],
        )

        proximate_composition = compositions["Proximate Analysis"]
        self.assertEqual(
            [
                (share["component_name"], share["percent"], share["inferred"])
                for share in proximate_composition["shares"]
            ],
            [
                ("Total Ash", 2.3, False),
                ("Organic matter", 97.7, True),
            ],
        )

    def test_residual_complement_applies_without_other_groups(self):
        sample, group = self._sample_with_group("Ash Only")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        organic_matter = MaterialComponent.objects.create(
            name="Organic matter", owner=self.owner
        )
        ash = MaterialComponent.objects.create(
            name="Total Ash",
            owner=self.owner,
            basis_component=dm,
            complement_component=organic_matter,
        )
        self._measure(sample, group, ash, "2.3", basis=dm)

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [
                (share["component_name"], share["percent"], share["inferred"])
                for share in composition["shares"]
            ],
            [("Total Ash", 2.3, False), ("Organic matter", 97.7, True)],
        )

    def test_residual_complement_requires_matching_basis(self):
        sample, group = self._sample_with_group("Complement Basis")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        fm = MaterialComponent.objects.create(name="Fresh matter", owner=self.owner)
        organic_matter = MaterialComponent.objects.create(
            name="Organic matter", owner=self.owner
        )
        ash = MaterialComponent.objects.create(
            name="Total Ash",
            owner=self.owner,
            basis_component=dm,
            complement_component=organic_matter,
        )
        self._measure(sample, group, ash, "2.3", basis=fm)

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [
                (share["component_name"], share["percent"])
                for share in composition["shares"]
            ],
            [("Total Ash", 2.3), ("Other", 97.7)],
        )

    def test_residual_complement_needs_single_measured_component(self):
        sample, group = self._sample_with_group("Two Components")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        organic_matter = MaterialComponent.objects.create(
            name="Organic matter", owner=self.owner
        )
        ash = MaterialComponent.objects.create(
            name="Total Ash",
            owner=self.owner,
            basis_component=dm,
            complement_component=organic_matter,
        )
        self._measure(sample, group, ash, "2.3", basis=dm)
        self._measure(sample, group, "Volatile solids", "80", basis=dm)

        composition = get_sample_normalized_compositions(sample)[0]

        self.assertEqual(
            [
                (share["component_name"], share["percent"])
                for share in composition["shares"]
            ],
            [("Volatile solids", 80.0), ("Total Ash", 2.3), ("Other", 17.7)],
        )

    def test_multi_component_cover_becomes_aggregate_share(self):
        sample, group = self._sample_with_group("Covered Gap")
        other_group = self._other_group("Covering Group")
        self._measure(sample, group, "Cellulose", "50")
        self._measure(sample, other_group, "Total Ash", "30")
        self._measure(sample, other_group, "Extractives", "20")

        composition = self._compositions_by_group_name(sample)["Covered Gap Group"]

        self.assertEqual(
            [
                (share["component_name"], share["percent"], share["inferred"])
                for share in composition["shares"]
            ],
            [("Cellulose", 50.0, False), ("Other measured components", 50.0, True)],
        )
        self.assertIn("remaining_fraction_decomposed", composition["warning_codes"])

    def test_residual_decomposition_requires_matching_basis(self):
        sample, biochemical = self._sample_with_group("Basis Guard")
        proximate = self._other_group("Foreign Basis")
        dm = MaterialComponent.objects.create(name="Dry matter", owner=self.owner)
        fm = MaterialComponent.objects.create(name="Fresh matter", owner=self.owner)
        self._measure(sample, biochemical, "Cellulose", "97.7", basis=dm)
        self._measure(sample, proximate, "Total Ash", "2.3", basis=fm)

        compositions = self._compositions_by_group_name(sample)

        self.assertEqual(
            [
                (share["component_name"], share["percent"])
                for share in compositions["Basis Guard Group"]["shares"]
            ],
            [("Cellulose", 97.7), ("Other", 2.3)],
        )
        self.assertEqual(
            [
                (share["component_name"], share["percent"])
                for share in compositions["Foreign Basis"]["shares"]
            ],
            [("Total Ash", 2.3), ("Other", 97.7)],
        )

    def test_residual_gap_remains_other_without_covering_components(self):
        sample, biochemical = self._sample_with_group("No Cover")
        proximate = self._other_group("Partial Only")
        self._measure(sample, biochemical, "Cellulose", "97.7")
        self._measure(sample, proximate, "Total Ash", "5.0")

        compositions = self._compositions_by_group_name(sample)

        self.assertEqual(
            [
                (share["component_name"], share["percent"])
                for share in compositions["No Cover Group"]["shares"]
            ],
            [("Cellulose", 97.7), ("Other", 2.3)],
        )

    def test_residual_decomposition_ignores_aggregate_components(self):
        sample, biochemical = self._sample_with_group("Aggregate Candidate")
        proximate = self._other_group("Aggregate Group")
        total = MaterialComponent.objects.create(
            name="Total Biochemical",
            publication_status="published",
            owner=self.owner,
            is_aggregate=True,
        )
        self._measure(sample, biochemical, "Cellulose", "97.7")
        self._measure(sample, proximate, total, "2.3")

        compositions = self._compositions_by_group_name(sample)

        self.assertEqual(
            [
                (share["component_name"], share["percent"])
                for share in compositions["Aggregate Candidate Group"]["shares"]
            ],
            [("Cellulose", 97.7), ("Other", 2.3)],
        )
