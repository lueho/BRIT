from decimal import Decimal

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase

from maps.models import GeoPolygon, LauRegion, NutsRegion, Region
from maps.validation import RegionCompositionError
from population.models import (
    GeographicScope,
    PopulationDataset,
    PopulationEstimate,
    PopulationObservation,
    SourceStatus,
    TemporalBasis,
)
from population.services import (
    METHOD_DIRECT,
    METHOD_SUMMED,
    TEMPORAL_BASIS_MIXED,
    materialize_estimate,
    resolve_population,
)


def square(x0, y0, size=1):
    return MultiPolygon(
        Polygon(
            (
                (x0, y0),
                (x0 + size, y0),
                (x0 + size, y0 + size),
                (x0, y0 + size),
                (x0, y0),
            )
        )
    )


class PopulationServiceTestCaseBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.nuts_dataset = PopulationDataset.objects.create(
            slug="eurostat-nama-10r-3popgdp",
            name="Average annual population to calculate regional GDP data",
            provider="Eurostat",
            source_code="nama_10r_3popgdp",
            geographic_scope=GeographicScope.NUTS,
            temporal_basis=TemporalBasis.CALENDAR_YEAR_AVERAGE,
            source_unit="THS",
            classification_version="NUTS2021",
            is_canonical=True,
        )
        cls.lau_dataset = PopulationDataset.objects.create(
            slug="destatis-lau-population",
            name="Municipal population",
            provider="Destatis",
            geographic_scope=GeographicScope.LAU,
            temporal_basis=TemporalBasis.POINT_IN_TIME,
        )

        cls.nuts0 = NutsRegion.objects.create(
            name="Deutschland", country="DE", nuts_id="DE", levl_code=0, cntr_code="DE"
        )
        cls.nuts1 = NutsRegion.objects.create(
            name="Niedersachsen",
            country="DE",
            nuts_id="DE9",
            levl_code=1,
            cntr_code="DE",
            parent=cls.nuts0,
        )
        cls.nuts2 = NutsRegion.objects.create(
            name="Weser-Ems",
            country="DE",
            nuts_id="DE94",
            levl_code=2,
            cntr_code="DE",
            parent=cls.nuts1,
        )
        cls.nuts3 = NutsRegion.objects.create(
            name="Emsland",
            country="DE",
            nuts_id="DE949",
            levl_code=3,
            cntr_code="DE",
            parent=cls.nuts2,
        )
        cls.nuts3_sibling = NutsRegion.objects.create(
            name="Grafschaft Bentheim",
            country="DE",
            nuts_id="DE94A",
            levl_code=3,
            cntr_code="DE",
            parent=cls.nuts2,
        )
        cls.lau1 = LauRegion.objects.create(
            name="Lingen",
            country="DE",
            cntr_code="DE",
            lau_id="03454026",
            lau_name="Lingen (Ems)",
            nuts_parent=cls.nuts3,
        )
        cls.lau2 = LauRegion.objects.create(
            name="Meppen",
            country="DE",
            cntr_code="DE",
            lau_id="03454033",
            lau_name="Meppen",
            nuts_parent=cls.nuts3,
        )

    @staticmethod
    def observe(dataset, region, year, value, status=SourceStatus.FINAL):
        return PopulationObservation.objects.create(
            dataset=dataset,
            region=region,
            year=year,
            value=Decimal(value),
            source_status=status,
        )

    @staticmethod
    def custom_region(name, members):
        region = Region.objects.create(name=name, country="DE", type="custom")
        region.composed_of.set(members)
        return region


class DirectResolutionTestCase(PopulationServiceTestCaseBase):
    def test_direct_exact_year_resolution_nuts0(self):
        self.observe(self.nuts_dataset, self.nuts0, 2021, "83155031.5")
        result = resolve_population(self.nuts0, 2021)
        self.assertIsNotNone(result)
        self.assertEqual(result.value, Decimal("83155031.5"))
        self.assertEqual(result.year, 2021)
        self.assertEqual(result.method, METHOD_DIRECT)
        self.assertEqual(result.temporal_basis, TemporalBasis.CALENDAR_YEAR_AVERAGE)
        self.assertEqual(result.datasets, (self.nuts_dataset,))
        self.assertFalse(result.is_provisional)
        self.assertFalse(result.is_mixed_provenance)

    def test_direct_exact_year_resolution_nuts1(self):
        self.observe(self.nuts_dataset, self.nuts1, 2021, "8003421")
        result = resolve_population(self.nuts1, 2021)
        self.assertEqual(result.value, Decimal("8003421"))
        self.assertEqual(result.method, METHOD_DIRECT)

    def test_direct_exact_year_resolution_nuts2(self):
        self.observe(self.nuts_dataset, self.nuts2, 2021, "2521000")
        result = resolve_population(self.nuts2, 2021)
        self.assertEqual(result.value, Decimal("2521000"))
        self.assertEqual(result.method, METHOD_DIRECT)

    def test_direct_exact_year_resolution_nuts3(self):
        self.observe(self.nuts_dataset, self.nuts3, 2021, "330000")
        result = resolve_population(self.nuts3, 2021)
        self.assertEqual(result.value, Decimal("330000"))
        self.assertEqual(result.method, METHOD_DIRECT)

    def test_direct_exact_year_lau_resolution_from_separate_lau_dataset(self):
        self.observe(self.lau_dataset, self.lau1, 2021, "55000")
        result = resolve_population(self.lau1, 2021)
        self.assertEqual(result.value, Decimal("55000"))
        self.assertEqual(result.method, METHOD_DIRECT)
        self.assertEqual(result.datasets, (self.lau_dataset,))
        self.assertEqual(result.temporal_basis, TemporalBasis.POINT_IN_TIME)

    def test_missing_year_returns_none_and_never_selects_another_year(self):
        self.observe(self.nuts_dataset, self.nuts3, 2020, "329000")
        self.observe(self.nuts_dataset, self.nuts3, 2022, "331000")
        self.assertIsNone(resolve_population(self.nuts3, 2021))

    def test_canonical_dataset_preferred_over_non_canonical(self):
        other = PopulationDataset.objects.create(
            slug="other-nuts",
            name="Other",
            provider="Other",
            geographic_scope=GeographicScope.NUTS,
            temporal_basis=TemporalBasis.POINT_IN_TIME,
        )
        self.observe(other, self.nuts3, 2021, "999")
        self.observe(self.nuts_dataset, self.nuts3, 2021, "330000")
        result = resolve_population(self.nuts3, 2021)
        self.assertEqual(result.datasets, (self.nuts_dataset,))
        self.assertEqual(result.value, Decimal("330000"))


class ComposedResolutionTestCase(PopulationServiceTestCaseBase):
    def test_custom_population_sums_disjoint_lau_components(self):
        self.observe(self.lau_dataset, self.lau1, 2021, "55000")
        self.observe(self.lau_dataset, self.lau2, 2021, "35000")
        region = self.custom_region("Lingen+Meppen", [self.lau1, self.lau2])
        result = resolve_population(region, 2021)
        self.assertEqual(result.value, Decimal("90000"))
        self.assertEqual(result.method, METHOD_SUMMED)
        self.assertEqual(len(result.observations), 2)
        self.assertFalse(result.is_mixed_provenance)
        self.assertEqual(result.temporal_basis, TemporalBasis.POINT_IN_TIME)

    def test_custom_population_sums_disjoint_nuts_components(self):
        self.observe(self.nuts_dataset, self.nuts3, 2021, "330000")
        self.observe(self.nuts_dataset, self.nuts3_sibling, 2021, "140000")
        region = self.custom_region(
            "Emsland+Bentheim", [self.nuts3, self.nuts3_sibling]
        )
        result = resolve_population(region, 2021)
        self.assertEqual(result.value, Decimal("470000"))
        self.assertEqual(result.method, METHOD_SUMMED)
        self.assertFalse(result.is_mixed_provenance)

    def test_custom_population_mixed_nuts_lau_exposes_mixed_provenance(self):
        self.observe(self.nuts_dataset, self.nuts3_sibling, 2021, "140000")
        self.observe(self.lau_dataset, self.lau1, 2021, "55000")
        region = self.custom_region("Mixed", [self.nuts3_sibling, self.lau1])
        result = resolve_population(region, 2021)
        self.assertEqual(result.value, Decimal("195000"))
        self.assertTrue(result.is_mixed_provenance)
        self.assertEqual(result.temporal_basis, TEMPORAL_BASIS_MIXED)
        self.assertCountEqual(result.datasets, (self.nuts_dataset, self.lau_dataset))

    def test_parent_nuts_plus_child_nuts_is_rejected(self):
        self.observe(self.nuts_dataset, self.nuts2, 2021, "2521000")
        self.observe(self.nuts_dataset, self.nuts3, 2021, "330000")
        region = self.custom_region("Overlap", [self.nuts2, self.nuts3])
        with self.assertRaises(RegionCompositionError) as ctx:
            resolve_population(region, 2021)
        self.assertIn("DE949", ctx.exception.conflicts)
        self.assertIn("DE94", ctx.exception.conflicts)

    def test_nuts3_plus_child_lau_is_rejected(self):
        region = self.custom_region("Overlap", [self.nuts3, self.lau1])
        with self.assertRaises(RegionCompositionError) as ctx:
            resolve_population(region, 2021)
        self.assertIn("DE949", ctx.exception.conflicts)

    def test_nested_custom_components_are_rejected(self):
        inner = self.custom_region("Inner", [self.lau1])
        region = self.custom_region("Outer", [inner, self.lau2])
        with self.assertRaises(RegionCompositionError):
            resolve_population(region, 2021)

    def test_self_reference_is_rejected(self):
        region = Region.objects.create(name="Self", country="DE", type="custom")
        region.composed_of.set([region])
        with self.assertRaises(RegionCompositionError):
            resolve_population(region, 2021)

    def test_spatial_overlap_is_rejected_and_boundary_contact_is_valid(self):
        lau_a = LauRegion.objects.create(
            name="A",
            country="DE",
            cntr_code="DE",
            lau_id="00000001",
            borders=GeoPolygon.objects.create(geom=square(0, 0)),
        )
        lau_b_overlapping = LauRegion.objects.create(
            name="B",
            country="DE",
            cntr_code="DE",
            lau_id="00000002",
            borders=GeoPolygon.objects.create(geom=square(0.5, 0)),
        )
        lau_c_touching = LauRegion.objects.create(
            name="C",
            country="DE",
            cntr_code="DE",
            lau_id="00000003",
            borders=GeoPolygon.objects.create(geom=square(1, 0)),
        )

        overlapping = self.custom_region("Overlapping", [lau_a, lau_b_overlapping])
        with self.assertRaises(RegionCompositionError):
            resolve_population(overlapping, 2021)

        self.observe(self.lau_dataset, lau_a, 2021, "100")
        self.observe(self.lau_dataset, lau_c_touching, 2021, "200")
        touching = self.custom_region("Touching", [lau_a, lau_c_touching])
        result = resolve_population(touching, 2021)
        self.assertEqual(result.value, Decimal("300"))

    def test_missing_component_observation_yields_no_partial_sum(self):
        self.observe(self.lau_dataset, self.lau1, 2021, "55000")
        region = self.custom_region("Incomplete", [self.lau1, self.lau2])
        self.assertIsNone(resolve_population(region, 2021))

    def test_provisional_status_propagates_through_custom_estimates(self):
        self.observe(self.lau_dataset, self.lau1, 2021, "55000")
        self.observe(
            self.lau_dataset, self.lau2, 2021, "35000", status=SourceStatus.PROVISIONAL
        )
        region = self.custom_region("Provisional", [self.lau1, self.lau2])
        result = resolve_population(region, 2021)
        self.assertTrue(result.is_provisional)

        estimate = materialize_estimate(region, 2021)
        self.assertTrue(estimate.is_provisional)


class EstimateMaterializationTestCase(PopulationServiceTestCaseBase):
    def test_source_revision_makes_dependent_estimates_identifiable(self):
        obs1 = self.observe(self.lau_dataset, self.lau1, 2021, "55000")
        self.observe(self.lau_dataset, self.lau2, 2021, "35000")
        region = self.custom_region("Revisable", [self.lau1, self.lau2])

        estimate = materialize_estimate(region, 2021)
        self.assertEqual(estimate.value, Decimal("90000"))
        self.assertCountEqual(
            estimate.components.values_list("pk", flat=True),
            [obs1.pk, self.lau2.population_observations.get().pk],
        )
        self.assertFalse(PopulationEstimate.objects.stale().exists())

        obs1.value = Decimal("56000")
        obs1.save()
        self.assertIn(estimate, PopulationEstimate.objects.stale())

        refreshed = materialize_estimate(region, 2021)
        self.assertEqual(refreshed.pk, estimate.pk)
        self.assertEqual(refreshed.value, Decimal("91000"))
        self.assertFalse(PopulationEstimate.objects.stale().exists())

    def test_materialize_returns_none_for_incomplete_composition(self):
        self.observe(self.lau_dataset, self.lau1, 2021, "55000")
        region = self.custom_region("Incomplete", [self.lau1, self.lau2])
        self.assertIsNone(materialize_estimate(region, 2021))
        self.assertFalse(PopulationEstimate.objects.filter(region=region).exists())
