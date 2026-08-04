"""The provider-neutral NUTS vintage import contract.

BRIT holds several NUTS vintages but has no way to acquire them: the loader
lives in private ETL (BRIT-data), which runs on a different host and therefore
needs an API rather than ORM access. This is that seam.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from maps.models import NutsRegion, NutsVintage

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


def region(nuts_id, levl_code, name, geometry, **overrides):
    payload = {
        "nuts_id": nuts_id,
        "levl_code": levl_code,
        "cntr_code": nuts_id[:2],
        "name_latn": name,
        "nuts_name": name,
        "geometry": geometry,
    }
    payload.update(overrides)
    return payload


class NutsImportApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("nuts:import")
        cls.importer = get_user_model().objects.create_user("gisco-loader")
        cls.importer.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="maps",
                codename__in=("add_nutsregion", "change_nutsregion"),
            )
        )
        cls.outsider = get_user_model().objects.create_user("outsider")
        cls.v2021 = NutsVintage.current()
        cls.de_2021 = NutsRegion.objects.create(
            name="Deutschland",
            country="DE",
            nuts_id="DE",
            levl_code=0,
            cntr_code="DE",
            name_latn="Deutschland",
            version=cls.v2021,
        )

    def payload(self, regions, **overrides):
        payload = {
            "schema_version": "1.0",
            "vintage": {"year": 2024, "source_release": "GISCO NUTS 2024"},
            "regions": regions,
        }
        payload.update(overrides)
        return payload

    def post(self, payload, user=None):
        self.client.force_login(user or self.importer)
        return self.client.post(self.url, payload, content_type="application/json")

    def test_a_new_vintage_is_created_with_its_regions(self):
        response = self.post(
            self.payload([region("DE", 0, "Deutschland", DE_GEOMETRY)])
        )
        self.assertEqual(response.status_code, 201, response.json())
        report = response.json()
        self.assertEqual((report["created"], report["updated"]), (1, 0))
        self.assertEqual(report["errors"], [])

        vintage = NutsVintage.objects.get(year=2024)
        self.assertEqual(vintage.source_release, "GISCO NUTS 2024")
        self.assertFalse(vintage.is_current)
        imported = NutsRegion.objects.get(nuts_id="DE", version=vintage)
        self.assertEqual(imported.name_latn, "Deutschland")
        self.assertEqual(imported.geom.geom_type, "MultiPolygon")

    def test_the_same_code_in_another_vintage_is_left_alone(self):
        self.post(self.payload([region("DE", 0, "Deutschland (2024)", DE_GEOMETRY)]))
        self.de_2021.refresh_from_db()
        self.assertEqual(self.de_2021.name_latn, "Deutschland")
        self.assertEqual(NutsRegion.objects.filter(nuts_id="DE").count(), 2)

    def test_reimporting_the_same_regions_changes_nothing(self):
        payload = self.payload([region("DE", 0, "Deutschland", DE_GEOMETRY)])
        self.post(payload)
        response = self.post(payload)
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(
            (report["created"], report["updated"], report["unchanged"]), (0, 0, 1)
        )
        self.assertEqual(NutsRegion.objects.filter(nuts_id="DE").count(), 2)

    def test_a_renamed_region_is_updated(self):
        self.post(self.payload([region("DE", 0, "Deutschland", DE_GEOMETRY)]))
        response = self.post(self.payload([region("DE", 0, "Germany", DE_GEOMETRY)]))
        report = response.json()
        self.assertEqual((report["created"], report["updated"]), (0, 1))
        self.assertEqual(
            NutsRegion.objects.get(nuts_id="DE", version__year=2024).name_latn,
            "Germany",
        )

    def test_children_are_linked_to_the_parent_of_their_own_vintage(self):
        self.post(self.payload([region("DE", 0, "Deutschland", DE_GEOMETRY)]))
        self.post(self.payload([region("DE1", 1, "Baden-Württemberg", DE1_GEOMETRY)]))
        child = NutsRegion.objects.get(nuts_id="DE1", version__year=2024)
        self.assertEqual(child.parent.nuts_id, "DE")
        self.assertEqual(child.parent.version.year, 2024)

    def test_levels_may_arrive_in_one_payload_in_any_order(self):
        """Parents are created first, so the provider need not sort its levels."""
        response = self.post(
            self.payload(
                [
                    region("DE1", 1, "Baden-Württemberg", DE1_GEOMETRY),
                    region("DE", 0, "Deutschland", DE_GEOMETRY),
                ]
            )
        )
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(
            NutsRegion.objects.get(nuts_id="DE1", version__year=2024).parent.nuts_id,
            "DE",
        )

    def test_a_dry_run_only_warns_about_a_parent_it_cannot_see(self):
        """A dry run rolls back, so parents of earlier requests are invisible."""
        response = self.post(
            self.payload(
                [region("DE1", 1, "Baden-Württemberg", DE1_GEOMETRY)], dry_run=True
            )
        )
        self.assertEqual(response.status_code, 200, response.json())
        report = response.json()
        self.assertEqual(report["errors"], [])
        self.assertIn("parent DE", report["warnings"][0])
        self.assertEqual(report["created"], 1)

    def test_a_missing_parent_is_reported_instead_of_guessed(self):
        response = self.post(
            self.payload([region("DE1", 1, "Baden-Württemberg", DE1_GEOMETRY)])
        )
        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("DE", str(response.json()["errors"]))
        self.assertFalse(NutsRegion.objects.filter(version__year=2024).exists())

    def test_nothing_is_written_when_one_region_fails(self):
        response = self.post(
            self.payload(
                [
                    region("DE", 0, "Deutschland", DE_GEOMETRY),
                    region("FR1", 1, "Île-de-France", DE1_GEOMETRY),
                ]
            )
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(NutsVintage.objects.filter(year=2024).exists())

    def test_a_dry_run_reports_without_writing(self):
        response = self.post(
            self.payload([region("DE", 0, "Deutschland", DE_GEOMETRY)], dry_run=True)
        )
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["created"], 1)
        self.assertFalse(report["committed"])
        self.assertFalse(NutsVintage.objects.filter(year=2024).exists())

    def test_a_vintage_can_be_made_the_current_one(self):
        self.post(
            self.payload(
                [region("DE", 0, "Deutschland", DE_GEOMETRY)],
                vintage={
                    "year": 2024,
                    "source_release": "GISCO NUTS 2024",
                    "is_current": True,
                },
            )
        )
        self.assertEqual(NutsVintage.current().year, 2024)
        self.assertEqual(NutsVintage.objects.filter(is_current=True).count(), 1)

    def test_imported_regions_are_published_reference_data(self):
        """A private row would be invisible to every public consumer."""
        self.post(self.payload([region("DE", 0, "Deutschland", DE_GEOMETRY)]))
        imported = NutsRegion.objects.get(nuts_id="DE", version__year=2024)
        self.assertEqual(imported.publication_status, NutsRegion.STATUS_PUBLISHED)
        self.assertIn(imported, NutsRegion.objects.published())

    def test_a_region_left_private_is_published_on_reimport(self):
        self.post(self.payload([region("DE", 0, "Deutschland", DE_GEOMETRY)]))
        NutsRegion.objects.filter(nuts_id="DE", version__year=2024).update(
            publication_status=NutsRegion.STATUS_PRIVATE
        )
        response = self.post(
            self.payload([region("DE", 0, "Deutschland", DE_GEOMETRY)])
        )
        self.assertEqual(response.json()["updated"], 1)
        self.assertEqual(
            NutsRegion.objects.get(nuts_id="DE", version__year=2024).publication_status,
            NutsRegion.STATUS_PUBLISHED,
        )

    def test_omitted_fields_keep_what_brit_already_holds(self):
        """A slimmed-down re-import must not blank names and type flags."""
        self.post(
            self.payload(
                [region("DE", 0, "Deutschland", DE_GEOMETRY, mount_type=1, urbn_type=2)]
            )
        )
        response = self.post(
            self.payload(
                [
                    {
                        "nuts_id": "DE",
                        "levl_code": 0,
                        "cntr_code": "DE",
                        "geometry": DE_GEOMETRY,
                    }
                ]
            )
        )
        self.assertEqual(response.json()["unchanged"], 1)
        imported = NutsRegion.objects.get(nuts_id="DE", version__year=2024)
        self.assertEqual(imported.name_latn, "Deutschland")
        self.assertEqual((imported.mount_type, imported.urbn_type), (1, 2))

    def test_a_code_too_short_for_its_level_is_rejected(self):
        response = self.post(
            self.payload([region("DE", 1, "Not a level 1 code", DE_GEOMETRY)])
        )
        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("cannot be 2 characters", str(response.json()["errors"]))

    def test_importing_needs_the_nuts_region_permissions(self):
        response = self.post(
            self.payload([region("DE", 0, "Deutschland", DE_GEOMETRY)]),
            user=self.outsider,
        )
        self.assertEqual(response.status_code, 403)

    def test_the_contract_schema_is_served(self):
        response = self.client.get(reverse("nuts:import-schema"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["properties"]["schema_version"]["const"], "1.0"
        )

    def test_a_geometry_carrying_the_members_geojson_allows_is_accepted(self):
        """GeoJSON may carry ``bbox``/``crs``, and names may contain quotes."""
        geometry = dict(DE_GEOMETRY, bbox=None, crs={"name": "l'ETRS89"})
        response = self.post(self.payload([region("DE", 0, "Deutschland", geometry)]))
        self.assertEqual(response.status_code, 201, response.json())
        imported = NutsRegion.objects.get(nuts_id="DE", version__year=2024)
        self.assertEqual(imported.geom.geom_type, "MultiPolygon")

    def test_a_geometry_that_cannot_be_read_is_a_bad_request(self):
        response = self.post(
            self.payload([region("DE", 0, "Deutschland", {"type": "Polygon"})])
        )
        self.assertEqual(response.status_code, 400)

    def test_a_geometry_without_any_parts_is_a_bad_request(self):
        """Empty borders would be stored on an update but dropped on a create."""
        response = self.post(
            self.payload(
                [
                    region(
                        "DE",
                        0,
                        "Deutschland",
                        {"type": "MultiPolygon", "coordinates": []},
                    )
                ]
            )
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(NutsRegion.objects.filter(version__year=2024).exists())

    def test_a_parent_that_the_code_does_not_imply_can_be_stated(self):
        """NUTS 2016 codes UKN0's children UKN10-UKN16, breaking the position rule."""
        self.post(
            self.payload(
                [
                    region("UK", 0, "United Kingdom", DE_GEOMETRY),
                    region("UKN", 1, "Northern Ireland", DE1_GEOMETRY),
                    region("UKN0", 2, "Northern Ireland", DE1_GEOMETRY),
                ]
            )
        )
        response = self.post(
            self.payload(
                [
                    region(
                        "UKN10",
                        3,
                        "Belfast",
                        DE1_GEOMETRY,
                        parent_nuts_id="UKN0",
                    )
                ]
            )
        )

        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["errors"], [])
        imported = NutsRegion.objects.get(nuts_id="UKN10", version__year=2024)
        self.assertEqual(imported.parent.nuts_id, "UKN0")

    def test_a_stated_parent_must_exist_in_the_same_vintage(self):
        response = self.post(
            self.payload(
                [region("UKN10", 3, "Belfast", DE1_GEOMETRY, parent_nuts_id="UKN0")]
            )
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("UKN0", response.json()["errors"][0])
