"""Tests for the provider-neutral population bulk-import API.

The import API is the public, versioned contract through which private
ETL (e.g. BRIT-data) writes population observations into BRIT without BRIT
depending on any provider-specific code.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from maps.models import LauRegion, NutsRegion
from maps.population.models import (
    PopulationDataset,
    PopulationImportRun,
    PopulationObservation,
    SourceStatus,
)

User = get_user_model()


def _payload(**overrides):
    payload = {
        "schema_version": "1.0",
        "dataset": {
            "slug": "eurostat-nama-10r-3popgdp",
            "name": "Average annual population",
            "provider": "eurostat",
            "external_id": "nama_10r_3popgdp",
            "release": "2026-02",
            "geographic_scope": "nuts",
            "temporal_basis": "calendar_year_average",
            "source_unit": "THS",
            "classification_version": "NUTS2021",
            "is_canonical": True,
        },
        "observations": [
            {
                "region_scheme": "NUTS",
                "region_code": "DE94A",
                "region_version": "2021",
                "indicator": "population",
                "reference_period": "2023",
                "value": "330.5",
                "unit": "thousands",
            }
        ],
    }
    payload.update(overrides)
    return payload


class PopulationImportAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.nuts3 = NutsRegion.objects.create(
            name="Grafschaft Bentheim",
            country="DE",
            nuts_id="DE94A",
            levl_code=3,
            cntr_code="DE",
        )
        cls.lau = LauRegion.objects.create(
            name="Lingen",
            country="DE",
            cntr_code="DE",
            lau_id="03454026",
            lau_name="Lingen (Ems)",
        )
        cls.importer = User.objects.create_user(
            "importer",
        )
        for codename in (
            "add_populationobservation",
            "change_populationobservation",
            "add_populationdataset",
            "add_populationimportrun",
        ):
            cls.importer.user_permissions.add(
                Permission.objects.get(
                    codename=codename,
                    content_type__app_label="population",
                )
            )
        cls.no_perm_user = User.objects.create_user(
            "nobody",
        )

    def setUp(self):
        self.url = reverse("population:import")

    def post(self, payload, user=None, **params):
        self.client.force_authenticate(user if user is not None else self.importer)
        url = self.url
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"
        return self.client.post(url, payload, format="json")

    def test_import_creates_dataset_and_observations(self):
        response = self.post(_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        body = response.data
        self.assertTrue(body["committed"])
        self.assertEqual(body["schema_version"], "1.0")
        self.assertEqual(body["created"], 1)
        self.assertEqual(body["updated"], 0)
        self.assertEqual(body["unchanged"], 0)
        self.assertEqual(body["errors"], [])

        dataset = PopulationDataset.objects.get(slug="eurostat-nama-10r-3popgdp")
        self.assertEqual(dataset.provider, "eurostat")
        self.assertEqual(dataset.source_code, "nama_10r_3popgdp")

        obs = PopulationObservation.objects.get(dataset=dataset, region=self.nuts3)
        self.assertEqual(obs.year, 2023)
        # 330.5 thousands -> persons
        self.assertEqual(obs.value, Decimal("330500.000"))
        self.assertIsNotNone(obs.import_run_id)

        run = PopulationImportRun.objects.get(pk=obs.import_run_id)
        self.assertEqual(run.created_count, 1)
        self.assertEqual(run.structure_version, "2026-02")

    def test_persons_unit_stored_directly(self):
        payload = _payload()
        payload["observations"][0]["unit"] = "persons"
        payload["observations"][0]["value"] = "330500"
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        obs = PopulationObservation.objects.get(region=self.nuts3)
        self.assertEqual(obs.value, Decimal("330500.000"))

    def test_reimport_same_values_reports_unchanged(self):
        self.post(_payload())
        response = self.post(_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["created"], 0)
        self.assertEqual(response.data["unchanged"], 1)
        self.assertEqual(PopulationObservation.objects.count(), 1)

    def test_reimport_changed_value_updates(self):
        self.post(_payload())
        payload = _payload()
        payload["observations"][0]["value"] = "400"
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["updated"], 1)
        obs = PopulationObservation.objects.get(region=self.nuts3)
        self.assertEqual(obs.value, Decimal("400000.000"))
        self.assertEqual(PopulationObservation.objects.count(), 1)

    def test_dry_run_does_not_persist(self):
        response = self.post(_payload(), dry_run="true")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(response.data["committed"])
        self.assertTrue(response.data["dry_run"])
        self.assertEqual(response.data["created"], 1)
        self.assertFalse(PopulationObservation.objects.exists())
        self.assertFalse(PopulationDataset.objects.exists())
        self.assertFalse(PopulationImportRun.objects.exists())

    def test_unknown_schema_version_rejected(self):
        response = self.post(_payload(schema_version="9.9"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_indicator_must_be_population(self):
        payload = _payload()
        payload["observations"][0]["indicator"] = "gdp"
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_unit_rejected(self):
        payload = _payload()
        payload["observations"][0]["unit"] = "furlongs"
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unmatched_region_reported_and_nothing_committed(self):
        payload = _payload()
        payload["observations"][0]["region_code"] = "ZZ999"
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(response.data["committed"])
        self.assertEqual(len(response.data["errors"]), 1)
        self.assertEqual(response.data["errors"][0]["region_code"], "ZZ999")
        self.assertFalse(PopulationObservation.objects.exists())
        self.assertFalse(PopulationDataset.objects.exists())

    def test_lau_region_matched(self):
        payload = _payload()
        payload["dataset"]["slug"] = "destatis-lau"
        payload["dataset"]["geographic_scope"] = "lau"
        payload["dataset"].pop("classification_version")
        payload["observations"][0] = {
            "region_scheme": "LAU",
            "region_code": "03454026",
            "indicator": "population",
            "reference_period": "2023",
            "value": "52000",
            "unit": "persons",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        obs = PopulationObservation.objects.get(region=self.lau)
        self.assertEqual(obs.value, Decimal("52000.000"))

    def test_source_status_propagates(self):
        payload = _payload()
        payload["observations"][0]["source_status"] = "provisional"
        payload["observations"][0]["flags"] = "p"
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        obs = PopulationObservation.objects.get(region=self.nuts3)
        self.assertEqual(obs.source_status, SourceStatus.PROVISIONAL)
        self.assertEqual(obs.flags, "p")

    def test_requires_permission(self):
        response = self.post(_payload(), user=self.no_perm_user)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(PopulationObservation.objects.exists())

    def test_unauthenticated_rejected(self):
        response = self.client.post(self.url, _payload(), format="json")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_schema_endpoint_returns_contract(self):
        response = self.client.get(reverse("population:import-schema"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        schema = response.json()
        self.assertEqual(schema.get("$schema", "").startswith("http"), True)
        self.assertIn("schema_version", schema.get("properties", {}))

    # --- dataset definition immutability -----------------------------------

    def _post_and_expect_no_commit(self, payload):
        """A reimport must not commit: committed=False report or a 400."""
        response = self.post(payload)
        if response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED):
            self.assertFalse(response.data["committed"], response.data)
        else:
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST, response.data
            )

    def test_dataset_definition_fields_immutable_once_observations_exist(self):
        response = self.post(_payload())
        self.assertTrue(response.data["committed"])
        original = PopulationDataset.objects.get()
        for field, new_value in (
            ("provider", "other-provider"),
            ("external_id", "demo_r_pjanaggr3"),
            ("geographic_scope", "lau"),
            ("temporal_basis", "point_in_time"),
            ("source_unit", "NR"),
            ("classification_version", "NUTS2024"),
        ):
            with self.subTest(field=field):
                payload = _payload()
                payload["dataset"][field] = new_value
                if field == "geographic_scope":
                    # keep observation scheme consistent so any refusal is an
                    # explicit non-commit, not a form mismatch
                    payload["observations"][0]["region_scheme"] = "LAU"
                    payload["observations"][0]["region_code"] = "03454026"
                self._post_and_expect_no_commit(payload)
                dataset = PopulationDataset.objects.get()
                self.assertEqual(dataset.provider, original.provider)
                self.assertEqual(dataset.source_code, original.source_code)
                self.assertEqual(dataset.geographic_scope, original.geographic_scope)
                self.assertEqual(dataset.temporal_basis, original.temporal_basis)
                self.assertEqual(dataset.source_unit, original.source_unit)
                self.assertEqual(
                    dataset.classification_version,
                    original.classification_version,
                )
                self.assertEqual(PopulationObservation.objects.count(), 1)
                self.assertEqual(PopulationImportRun.objects.count(), 1)

    def test_dataset_name_and_canonical_flag_may_change_with_observations(self):
        self.post(_payload())
        payload = _payload()
        payload["dataset"]["name"] = "Renamed average dataset"
        payload["dataset"]["is_canonical"] = False
        response = self.post(payload)
        self.assertTrue(response.data["committed"], response.data)
        dataset = PopulationDataset.objects.get()
        self.assertEqual(dataset.name, "Renamed average dataset")
        self.assertFalse(dataset.is_canonical)

    def test_dataset_definition_change_allowed_on_empty_dataset(self):
        PopulationDataset.objects.create(
            slug="eurostat-nama-10r-3popgdp",
            name="Empty dataset",
            provider="old-provider",
            source_code="old_code",
            geographic_scope="nuts",
            temporal_basis="point_in_time",
            source_unit="NR",
            classification_version="NUTS2024",
        )
        response = self.post(_payload())
        self.assertTrue(response.data["committed"], response.data)
        dataset = PopulationDataset.objects.get()
        self.assertEqual(dataset.provider, "eurostat")
        self.assertEqual(dataset.temporal_basis, "calendar_year_average")
        self.assertEqual(dataset.classification_version, "NUTS2021")

    def test_scope_region_scheme_mismatch_rejected(self):
        payload = _payload()
        payload["observations"][0]["region_scheme"] = "LAU"
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_values_rejected(self):
        payload = _payload()
        payload["observations"][0]["value"] = "-5"
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_value_is_stored(self):
        payload = _payload()
        payload["observations"][0]["value"] = "0"
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(PopulationObservation.objects.get().value, Decimal("0.000"))
