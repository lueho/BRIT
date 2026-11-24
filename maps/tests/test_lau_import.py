"""The provider-neutral LAU vintage import contract.

Mirrors the NUTS vintage import: BRIT holds several LAU vintages but owns no
acquisition code, so private ETL (BRIT-data) loads them through this API.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import GEOSGeometry
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from maps.models import Catchment, LauRegion, NutsRegion, NutsVintage

DE_GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [
        [[[6.0, 47.0], [15.0, 47.0], [15.0, 55.0], [6.0, 55.0], [6.0, 47.0]]]
    ],
}
DE1_GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [
        [[[9.0, 47.5], [13.0, 47.5], [13.0, 50.5], [9.0, 50.5], [9.0, 47.5]]]
    ],
}


def lau(
    lau_id,
    cntr_code="DE",
    name="Flensburg",
    nuts_parent_id="DEF01",
    geometry=DE_GEOMETRY,
    **overrides,
):
    payload = {
        "cntr_code": cntr_code,
        "lau_id": lau_id,
        "lau_name": name,
        "nuts_parent_id": nuts_parent_id,
        "geometry": geometry,
    }
    payload.update(overrides)
    return payload


class LauImportApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("lau:import")
        cls.importer = get_user_model().objects.create_user("gisco-lau-loader")
        cls.importer.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="maps",
                codename__in=("add_lauregion", "change_lauregion"),
            )
        )
        cls.outsider = get_user_model().objects.create_user("lau-outsider")
        cls.v2021 = NutsVintage.current()
        cls.de3_2021 = NutsRegion.objects.create(
            name="Kreis Flensburg",
            country="DE",
            nuts_id="DEF01",
            levl_code=3,
            cntr_code="DE",
            version=cls.v2021,
        )
        cls.v2024 = NutsVintage.objects.create(
            year=2024, source_release="GISCO NUTS 2024"
        )
        cls.de3_2024 = NutsRegion.objects.create(
            name="Kreis Flensburg 2024",
            country="DE",
            nuts_id="DEF01",
            levl_code=3,
            cntr_code="DE",
            version=cls.v2024,
        )
        cls.de2_2024 = NutsRegion.objects.create(
            name="Schleswig-Holstein",
            country="DE",
            nuts_id="DEF0",
            levl_code=2,
            cntr_code="DE",
            version=cls.v2024,
        )
        cls.de3only_2021 = NutsRegion.objects.create(
            name="Kreis Nordfriesland",
            country="DE",
            nuts_id="DEF02",
            levl_code=3,
            cntr_code="DE",
            version=cls.v2021,
        )
        cls.fr3_2024 = NutsRegion.objects.create(
            name="Nord",
            country="FR",
            nuts_id="FRE11",
            levl_code=3,
            cntr_code="FR",
            version=cls.v2024,
        )

    def payload(self, regions, year=2018, nuts_year=2024, **overrides):
        payload = {
            "schema_version": "1.0",
            "vintage": {"year": year, "nuts_year": nuts_year},
            "regions": regions,
        }
        payload.update(overrides)
        return payload

    def post(self, payload, user=None, query=""):
        self.client.force_login(user or self.importer)
        return self.client.post(
            self.url + query, payload, content_type="application/json"
        )

    def test_a_lau_region_is_created_published_with_its_parent(self):
        response = self.post(self.payload([lau("01001000")]))
        self.assertEqual(response.status_code, 201, response.json())
        report = response.json()
        self.assertEqual((report["created"], report["updated"]), (1, 0))
        self.assertEqual(report["errors"], [])
        self.assertEqual((report["lau_year"], report["nuts_year"]), (2018, 2024))

        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        self.assertEqual(imported.lau_name, "Flensburg")
        self.assertEqual(imported.name, "Flensburg")
        self.assertEqual(imported.country, "DE")
        self.assertEqual(imported.nuts_parent_id, self.de3_2024.pk)
        self.assertEqual(imported.geom.geom_type, "MultiPolygon")
        self.assertEqual(imported.publication_status, LauRegion.STATUS_PUBLISHED)

    def test_the_same_nuts_code_in_two_vintages_binds_the_declared_one(self):
        response = self.post(self.payload([lau("01001000")], nuts_year=2021))
        self.assertEqual(response.status_code, 201, response.json())
        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        self.assertEqual(imported.nuts_parent_id, self.de3_2021.pk)

    def test_a_parent_only_in_another_vintage_fails_the_request(self):
        """DEF02 exists only in NUTS 2021; declaring NUTS 2024 must not
        substitute it."""
        response = self.post(
            self.payload([lau("01001000", nuts_parent_id="DEF02")], nuts_year=2024)
        )
        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("DEF02", str(response.json()["errors"]))
        self.assertFalse(LauRegion.objects.exists())

    def test_a_parent_below_level_3_is_an_error(self):
        response = self.post(self.payload([lau("01001000", nuts_parent_id="DEF0")]))
        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("level", str(response.json()["errors"]))

    def test_a_parent_in_another_country_is_an_error(self):
        response = self.post(self.payload([lau("01001000", nuts_parent_id="FRE11")]))
        self.assertEqual(response.status_code, 400, response.json())

    def test_an_unknown_nuts_year_fails_the_whole_request(self):
        response = self.post(self.payload([lau("01001000")], nuts_year=2006))
        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("2006", str(response.json()["errors"]))
        self.assertFalse(LauRegion.objects.exists())

    def test_reimporting_identical_rows_changes_nothing(self):
        payload = self.payload([lau("01001000")])
        self.post(payload)
        response = self.post(payload)
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(
            (report["created"], report["updated"], report["unchanged"]), (0, 0, 1)
        )
        self.assertEqual(LauRegion.objects.filter(lau_id="01001000").count(), 1)

    def test_a_changed_geometry_updates_and_counts(self):
        self.post(self.payload([lau("01001000")]))
        response = self.post(self.payload([lau("01001000", geometry=DE1_GEOMETRY)]))
        report = response.json()
        self.assertEqual((report["updated"], report["geometry_changed"]), (1, 1))
        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        self.assertTrue(
            imported.geom.equals_exact(
                GEOSGeometry(json.dumps(DE1_GEOMETRY), srid=4326)
            )
        )

    def test_omitted_lau_name_and_name_en_are_preserved(self):
        self.post(self.payload([lau("01001000", name_en="Flensburg city")]))
        response = self.post(
            self.payload(
                [
                    {
                        "cntr_code": "DE",
                        "lau_id": "01001000",
                        "nuts_parent_id": "DEF01",
                    }
                ]
            )
        )
        self.assertEqual(response.json()["unchanged"], 1)
        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        self.assertEqual(imported.lau_name, "Flensburg")
        self.assertEqual(imported.name_en, "Flensburg city")

    def test_a_new_row_without_geometry_is_an_error(self):
        response = self.post(self.payload([lau("01001000", geometry=None)]))
        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("needs a geometry", str(response.json()["errors"]))
        self.assertFalse(LauRegion.objects.exists())

    def test_an_update_without_geometry_keeps_the_borders(self):
        self.post(self.payload([lau("01001000")]))
        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        response = self.post(
            self.payload(
                [
                    {
                        "cntr_code": "DE",
                        "lau_id": "01001000",
                        "lau_name": "Flensburg neu",
                        "nuts_parent_id": "DEF01",
                    }
                ]
            )
        )
        self.assertEqual(response.json()["updated"], 1, response.json())
        imported.refresh_from_db()
        self.assertIsNotNone(imported.borders_id)
        self.assertEqual(imported.lau_name, "Flensburg neu")

    def test_a_blank_lau_name_resets_name_to_the_lau_id(self):
        self.post(self.payload([lau("01001000")]))
        response = self.post(self.payload([lau("01001000", name="")]))
        self.assertEqual(response.json()["updated"], 1, response.json())
        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        self.assertEqual(imported.lau_name, "")
        self.assertEqual(imported.name, "01001000")

    def test_a_parent_change_on_a_catchment_region_warns(self):
        NutsRegion.objects.create(
            name="Kreis Rendsburg",
            country="DE",
            nuts_id="DEF03",
            levl_code=3,
            cntr_code="DE",
            version=self.v2024,
        )
        self.post(self.payload([lau("01001000")]))
        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        Catchment.objects.create(name="catch", region=imported, type="lau")
        response = self.post(self.payload([lau("01001000", nuts_parent_id="DEF03")]))
        warnings = str(response.json()["warnings"])
        self.assertIn("nuts_parent changed", warnings)
        self.assertIn("01001000", warnings)
        imported.refresh_from_db()
        self.assertEqual(imported.nuts_parent.nuts_id, "DEF03")

    def test_the_same_lau_id_in_another_year_is_untouched(self):
        self.post(self.payload([lau("01001000")], year=2018))
        response = self.post(
            self.payload([lau("01001000", name="Flensburg 2021")], year=2021)
        )
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(LauRegion.objects.filter(lau_id="01001000").count(), 2)
        self.assertEqual(
            LauRegion.objects.get(lau_id="01001000", year=2018).lau_name, "Flensburg"
        )

    def test_a_dry_run_via_body_writes_nothing_but_reports(self):
        response = self.post(self.payload([lau("01001000")], dry_run=True))
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["created"], 1)
        self.assertFalse(report["committed"])
        self.assertFalse(LauRegion.objects.exists())

    def test_a_dry_run_via_query_param_writes_nothing(self):
        response = self.post(self.payload([lau("01001000")]), query="?dry_run=true")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["dry_run"])
        self.assertFalse(LauRegion.objects.exists())

    def test_a_duplicate_key_inside_the_payload_is_an_error(self):
        response = self.post(
            self.payload([lau("01001000"), lau("01001000", name="Other")])
        )
        self.assertEqual(response.status_code, 400, response.json())
        self.assertFalse(LauRegion.objects.exists())

    def test_an_existing_row_parented_to_another_vintage_fails_closed(self):
        lau_row = LauRegion.objects.create(
            name="Flensburg",
            country="DE",
            cntr_code="DE",
            lau_id="01001000",
            lau_name="Flensburg",
            year=2018,
            nuts_parent=self.de3_2021,
        )
        response = self.post(self.payload([lau("01001000")], nuts_year=2024))
        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("DEF01", str(response.json()["errors"]))
        self.assertIn("2021", str(response.json()["errors"]))
        lau_row.refresh_from_db()
        self.assertEqual(lau_row.nuts_parent_id, self.de3_2021.pk)

    def test_a_null_parent_is_stored_and_counted(self):
        response = self.post(self.payload([lau("01001000", nuts_parent_id=None)]))
        self.assertEqual(response.status_code, 201, response.json())
        report = response.json()
        self.assertEqual(report["without_parent"], 1)
        self.assertTrue(
            any("without" in w or "parent" in w for w in report["warnings"])
        )
        self.assertIsNone(LauRegion.objects.get(lau_id="01001000").nuts_parent_id)

    def test_a_geometry_change_on_a_referenced_region_warns(self):
        self.post(self.payload([lau("01001000")]))
        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        Catchment.objects.create(name="catch", region=imported, type="lau")
        response = self.post(self.payload([lau("01001000", geometry=DE1_GEOMETRY)]))
        self.assertIn("01001000", str(response.json()["warnings"]))

    def test_a_shared_geopolygon_is_not_mutated_in_place(self):
        """Two regions sharing one GeoPolygon must not corrupt each other."""
        self.post(self.payload([lau("01001000")]))
        imported = LauRegion.objects.get(lau_id="01001000", year=2018)
        other = LauRegion.objects.create(
            name="Shared",
            country="DE",
            cntr_code="DE",
            lau_id="02002000",
            year=2018,
            borders=imported.borders,
        )
        other_geom = other.geom

        self.post(self.payload([lau("01001000", geometry=DE1_GEOMETRY)]))

        other.refresh_from_db()
        imported.refresh_from_db()
        self.assertNotEqual(imported.borders_id, other.borders_id)
        self.assertTrue(other.geom.equals_exact(other_geom))

    def test_importing_needs_the_lau_region_permissions(self):
        response = self.post(self.payload([lau("01001000")]), user=self.outsider)
        self.assertEqual(response.status_code, 403)

    def test_an_anonymous_request_is_rejected(self):
        response = self.client.post(
            self.url,
            self.payload([lau("01001000")]),
            content_type="application/json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_the_contract_schema_is_served(self):
        response = self.client.get(reverse("lau:import-schema"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["properties"]["schema_version"]["const"], "1.0"
        )


class LauRegionVintageKeyTestCase(TestCase):
    def test_a_duplicate_vintage_key_violates_the_constraint(self):
        vintage = NutsVintage.current()
        parent = NutsRegion.objects.create(
            name="k",
            country="DE",
            nuts_id="DEX99",
            levl_code=3,
            cntr_code="DE",
            version=vintage,
        )
        LauRegion.objects.create(
            name="a",
            country="DE",
            cntr_code="DE",
            lau_id="99999999",
            year=2020,
            nuts_parent=parent,
        )
        with self.assertRaises(IntegrityError):
            LauRegion.objects.create(
                name="b",
                country="DE",
                cntr_code="DE",
                lau_id="99999999",
                year=2020,
                nuts_parent=parent,
            )
