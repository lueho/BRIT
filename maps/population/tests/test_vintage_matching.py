"""Vintage-aware region matching for the population import contract.

``region_version`` (per observation) and ``classification_version`` (per
dataset) select which NUTS vintage a provider code refers to. Without this,
holding more than one vintage would make every import fail with
"ambiguous region code".
"""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from maps.models import LauRegion, NutsRegion, NutsVintage
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

    def test_code_missing_from_requested_vintage_is_rejected_not_fallback(self):
        report = import_population_payload(
            _payload([{"region_code": "DEG0Q", "region_version": "2021"}])
        )
        self.assertFalse(report.committed)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(
            report.errors[0]["reason"],
            "region code exists only in a different vintage",
        )
        self.assertNotIn("fallback_vintage", report.resolutions)
        self.assertFalse(
            any(w.get("resolution") == "fallback_vintage" for w in report.warnings)
        )
        self.assertFalse(PopulationObservation.objects.exists())

    def test_unknown_vintage_label_is_rejected_not_fallback(self):
        report = import_population_payload(
            _payload([{"region_code": "DEG0Q", "region_version": "2016"}])
        )
        self.assertFalse(report.committed)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(
            report.errors[0]["reason"], "requested NUTS vintage unavailable"
        )
        self.assertFalse(PopulationObservation.objects.exists())

    def test_unavailable_vintage_hint_is_rejected(self):
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
            report.errors[0]["reason"], "requested NUTS vintage unavailable"
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


class LauVersionMatchingTestCase(TestCase):
    """``region_version``/``classification_version`` filter ``LauRegion.year``."""

    @classmethod
    def setUpTestData(cls):
        cls.lau_2023 = LauRegion.objects.create(
            name="Lingen",
            country="DE",
            cntr_code="DE",
            lau_id="03454026",
            lau_name="Lingen (Ems)",
            year=2023,
        )

    def _lau_payload(self, observation=None, **dataset_overrides):
        obs = {
            "region_scheme": "LAU",
            "region_code": "03454026",
            "indicator": "population",
            "reference_period": 2023,
            "value": "52000",
            "unit": "persons",
        }
        if observation:
            obs.update(observation)
        # Deliberately no classification_version default: unversioned LAU
        # fixtures must not inherit a NUTS vintage hint.
        dataset = {
            "slug": "destatis-lau",
            "name": "LAU population",
            "provider": "destatis",
            "geographic_scope": "lau",
            "temporal_basis": "point_in_time",
        }
        dataset.update(dataset_overrides)
        payload = {
            "schema_version": "1.0",
            "dataset": dataset,
            "observations": [obs],
        }
        serializer = PopulationImportSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def test_lau_observation_version_matches_lau_year(self):
        for version in ("2023", "LAU2023"):
            with self.subTest(version=version):
                report = import_population_payload(
                    self._lau_payload({"region_version": version})
                )
                self.assertEqual(report.errors, [])
                self.assertTrue(report.committed)
                self.assertEqual(
                    PopulationObservation.objects.get().region_id,
                    self.lau_2023.pk,
                )
                PopulationObservation.objects.all().delete()

    def test_lau_dataset_version_matches_lau_year(self):
        for version in ("2023", "LAU2023"):
            with self.subTest(version=version):
                report = import_population_payload(
                    self._lau_payload(classification_version=version)
                )
                self.assertTrue(report.committed)
                self.assertEqual(
                    PopulationObservation.objects.get().region_id,
                    self.lau_2023.pk,
                )
                PopulationObservation.objects.all().delete()

    def test_lau_unheld_year_is_rejected(self):
        report = import_population_payload(
            self._lau_payload({"region_version": "2020"})
        )
        self.assertFalse(report.committed)
        self.assertEqual(len(report.errors), 1)
        self.assertFalse(PopulationObservation.objects.exists())

    def test_lau_wrong_kind_version_is_rejected(self):
        report = import_population_payload(
            self._lau_payload({"region_version": "NUTS2021"})
        )
        self.assertFalse(report.committed)
        self.assertFalse(PopulationObservation.objects.exists())

    def test_lau_version_selects_among_same_code_years(self):
        lau_2020 = LauRegion.objects.create(
            name="Lingen alt",
            country="DE",
            cntr_code="DE",
            lau_id="03454026",
            lau_name="Lingen (Ems)",
            year=2020,
        )
        report = import_population_payload(
            self._lau_payload({"region_version": "2020"})
        )
        self.assertTrue(report.committed)
        self.assertEqual(PopulationObservation.objects.get().region_id, lau_2020.pk)

    def test_lau_without_version_keeps_unique_code_matching(self):
        report = import_population_payload(self._lau_payload())
        self.assertTrue(report.committed)
        self.assertEqual(
            PopulationObservation.objects.get().region_id, self.lau_2023.pk
        )
