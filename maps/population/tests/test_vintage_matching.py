"""Vintage-aware region matching for the population import contract.

``region_version`` (per observation) and ``classification_version`` (per
dataset) select which NUTS vintage a provider code refers to. Without this,
holding more than one vintage would make every import fail with
"ambiguous region code".
"""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from maps.models import NutsRegion, NutsVintage
from maps.population.importers import import_population_payload
from maps.population.models import PopulationObservation
from maps.population.serializers import PopulationImportSerializer


def _payload(observations, **dataset_overrides):
    dataset = {
        "slug": "eurostat-nama-10r-3popgdp",
        "name": "Average annual population",
        "provider": "eurostat",
        "geographic_scope": "nuts",
        "temporal_basis": "calendar_year_average",
    }
    dataset.update(dataset_overrides)
    payload = {
        "schema_version": "1.0",
        "dataset": dataset,
        "observations": [
            {
                "region_scheme": "NUTS",
                "indicator": "population",
                "reference_period": 2020,
                "value": "100",
                "unit": "thousands",
                **observation,
            }
            for observation in observations
        ],
    }
    serializer = PopulationImportSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class VintageAwareMatchingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.v2021 = NutsVintage.current()
        cls.v2024 = NutsVintage.objects.create(year=2024)
        # Pure recode of identical geography: DEG0B (2021) -> DEG0Q (2024).
        cls.deg0b_2021 = NutsRegion.objects.create(
            name="Schmalkalden-Meiningen",
            country="DE",
            nuts_id="DEG0B",
            levl_code=3,
            version=cls.v2021,
        )
        cls.deg0q_2024 = NutsRegion.objects.create(
            name="Schmalkalden-Meiningen",
            country="DE",
            nuts_id="DEG0Q",
            levl_code=3,
            version=cls.v2024,
        )
        # Same code carried by both vintages.
        cls.de111_2021 = NutsRegion.objects.create(
            name="Stuttgart", country="DE", nuts_id="DE111", levl_code=3
        )
        cls.de111_2024 = NutsRegion.objects.create(
            name="Stuttgart",
            country="DE",
            nuts_id="DE111",
            levl_code=3,
            version=cls.v2024,
        )

    def test_observation_region_version_selects_the_vintage(self):
        report = import_population_payload(
            _payload([{"region_code": "DE111", "region_version": "2024"}])
        )
        self.assertEqual(report.errors, [])
        self.assertTrue(report.committed)
        self.assertEqual(
            PopulationObservation.objects.get().region_id, self.de111_2024.pk
        )

    def test_dataset_classification_version_selects_the_vintage(self):
        report = import_population_payload(
            _payload([{"region_code": "DE111"}], classification_version="NUTS2024")
        )
        self.assertEqual(report.errors, [])
        self.assertEqual(report.created, 1)
        self.assertEqual(self.de111_2024.population_observations.count(), 1)

    def test_observation_version_overrides_dataset_version(self):
        report = import_population_payload(
            _payload(
                [{"region_code": "DE111", "region_version": "2021"}],
                classification_version="2024",
            )
        )
        self.assertEqual(report.errors, [])
        self.assertEqual(report.resolutions.get("exact"), 1)
        self.assertEqual(self.de111_2021.population_observations.count(), 1)

    def test_no_version_given_uses_the_current_vintage(self):
        report = import_population_payload(_payload([{"region_code": "DE111"}]))
        self.assertEqual(report.errors, [])
        self.assertEqual(report.resolutions.get("current_vintage"), 1)

    def test_code_missing_from_requested_vintage_falls_back_and_is_reported(self):
        report = import_population_payload(
            _payload([{"region_code": "DEG0Q", "region_version": "2021"}])
        )
        self.assertEqual(report.errors, [])
        self.assertTrue(report.committed)
        self.assertEqual(report.resolutions.get("fallback_vintage"), 1)
        self.assertEqual(
            report.warnings,
            [
                {
                    "index": 0,
                    "region_scheme": "NUTS",
                    "region_code": "DEG0Q",
                    "requested_version": "2021",
                    "matched_version": "2024",
                    "resolution": "fallback_vintage",
                }
            ],
        )

    def test_unknown_vintage_label_falls_back_to_a_held_vintage(self):
        report = import_population_payload(
            _payload([{"region_code": "DEG0Q", "region_version": "2016"}])
        )
        self.assertEqual(report.errors, [])
        self.assertEqual(report.resolutions.get("fallback_vintage"), 1)

    def test_code_in_several_vintages_is_ambiguous_only_without_a_vintage_hint(self):
        NutsRegion.objects.create(
            name="Stuttgart",
            country="DE",
            nuts_id="DE111",
            levl_code=3,
            version=NutsVintage.objects.create(year=2016),
        )
        report = import_population_payload(
            _payload([{"region_code": "DE111", "region_version": "2013"}])
        )
        self.assertFalse(report.committed)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(
            report.errors[0]["reason"], "ambiguous region code (multiple matches)"
        )

    def test_vintage_is_resolved_once_per_label_not_once_per_observation(self):
        observations = [
            {
                "region_code": "DE111",
                "region_version": "2024",
                "reference_period": 2000 + index,
            }
            for index in range(6)
        ]
        with CaptureQueriesContext(connection) as captured:
            import_population_payload(_payload(observations))
        vintage_queries = [
            query
            for query in captured.captured_queries
            if "maps_nutsvintage" in query["sql"]
        ]
        self.assertEqual(len(vintage_queries), 1)

    def test_unknown_code_still_reports_no_matching_region(self):
        report = import_population_payload(
            _payload([{"region_code": "ZZ999", "region_version": "2024"}])
        )
        self.assertFalse(report.committed)
        self.assertEqual(report.errors[0]["reason"], "no matching region")
