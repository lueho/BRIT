from datetime import timedelta

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from maps.models import Catchment, GeoPolygon, Region
from materials.models import Material
from processes.models import Process
from utils.tests.testcases import AbstractTestCases

from ..models import Showcase


class ShowCaseCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False
    add_scope_query_param_to_list_urls = True

    model = Showcase

    view_create_name = "showcase-create"
    view_published_list_name = "showcase-list"
    view_private_list_name = "showcase-list-owned"
    view_detail_name = "showcase-detail"
    view_update_name = "showcase-update"
    view_delete_name = "showcase-delete-modal"

    create_object_data = {"name": "Test Showcase"}
    update_object_data = {"name": "Updated Test Showcase"}

    @classmethod
    def create_related_objects(cls):
        return {
            "region": Region.objects.create(
                name="Test Region", publication_status="published"
            )
        }

    def related_objects_post_data(self):
        """Include management form data for the inline formsets."""
        data = super().related_objects_post_data()
        data.update(
            {
                "showcase_materials-TOTAL_FORMS": "0",
                "showcase_materials-INITIAL_FORMS": "0",
                "showcase_materials-MIN_NUM_FORMS": "0",
                "showcase_materials-MAX_NUM_FORMS": "1000",
                "showcase_processes-TOTAL_FORMS": "0",
                "showcase_processes-INITIAL_FORMS": "0",
                "showcase_processes-MIN_NUM_FORMS": "0",
                "showcase_processes-MAX_NUM_FORMS": "1000",
            }
        )
        return data

    def test_create_view_renders_distinct_formset_controls_per_inline(self):
        """Each inline gets its own add button, container and empty-row template."""
        self.client.force_login(self.user_with_add_perm)
        response = self.client.get(self.get_create_url())
        self.assertEqual(response.status_code, 200)
        for prefix in ("showcase_materials", "showcase_processes"):
            for element in ("add-form", "formset-container", "empty-form-row"):
                with self.subTest(prefix=prefix, element=element):
                    self.assertContains(
                        response, f'id="{prefix}_{element}"', count=1, html=False
                    )
            self.assertContains(response, f'data-formset-id="{prefix}"', count=1)

    def test_create_and_update_forms_load_leaflet_for_the_location_widget(self):
        """The geometry widget needs Leaflet and leaflet-draw on the page."""
        pages = (
            (self.user_with_add_perm, self.get_create_url()),
            (self.owner_user, self.get_update_url(self.unpublished_object.pk)),
        )
        for user, url in pages:
            with self.subTest(url=url):
                self.client.force_login(user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "leaflet/leaflet.js")
                self.assertContains(response, "leaflet-draw/leaflet.draw.min.js")
                self.assertContains(response, "leaflet/leaflet.forms.js")

    def test_create_view_post_with_inline_materials_and_processes(self):
        """Creating a showcase can attach material and process links inline."""
        self.client.force_login(self.user_with_add_perm)
        material = Material.objects.create(
            name="Inline Feedstock", publication_status="published"
        )
        process = Process.objects.create(
            name="Inline Process", publication_status="published"
        )
        data = {
            "name": "Chained Showcase",
            "region": self.related_objects["region"].pk,
            "showcase_materials-TOTAL_FORMS": "1",
            "showcase_materials-INITIAL_FORMS": "0",
            "showcase_materials-MIN_NUM_FORMS": "0",
            "showcase_materials-MAX_NUM_FORMS": "1000",
            "showcase_materials-0-material": str(material.pk),
            "showcase_materials-0-role": "input",
            "showcase_materials-0-order": "0",
            "showcase_processes-TOTAL_FORMS": "1",
            "showcase_processes-INITIAL_FORMS": "0",
            "showcase_processes-MIN_NUM_FORMS": "0",
            "showcase_processes-MAX_NUM_FORMS": "1000",
            "showcase_processes-0-process": str(process.pk),
            "showcase_processes-0-order": "0",
        }
        response = self.client.post(self.get_create_url(), data)
        self.assertEqual(response.status_code, 302)
        showcase = Showcase.objects.get(name="Chained Showcase")
        link = showcase.showcase_materials.get()
        self.assertEqual(material, link.material)
        self.assertEqual("input", link.role)
        self.assertEqual([process], showcase.process_chain)

    def test_update_view_post_replaces_inline_links(self):
        """Updating a showcase can reorder the process chain inline."""
        self.client.force_login(self.owner_user)
        process_a = Process.objects.create(
            name="First Process", publication_status="published"
        )
        process_b = Process.objects.create(
            name="Second Process", publication_status="published"
        )
        showcase = self.unpublished_object
        link = showcase.showcase_processes.create(process=process_a, order=1)
        data = {
            "name": "Updated Test Showcase",
            "region": self.related_objects["region"].pk,
            "showcase_materials-TOTAL_FORMS": "0",
            "showcase_materials-INITIAL_FORMS": "0",
            "showcase_materials-MIN_NUM_FORMS": "0",
            "showcase_materials-MAX_NUM_FORMS": "1000",
            "showcase_processes-TOTAL_FORMS": "2",
            "showcase_processes-INITIAL_FORMS": "1",
            "showcase_processes-MIN_NUM_FORMS": "0",
            "showcase_processes-MAX_NUM_FORMS": "1000",
            "showcase_processes-0-id": str(link.pk),
            "showcase_processes-0-process": str(process_a.pk),
            "showcase_processes-0-order": "2",
            "showcase_processes-1-process": str(process_b.pk),
            "showcase_processes-1-order": "1",
        }
        response = self.client.post(self.get_update_url(showcase.pk), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual([process_b, process_a], showcase.process_chain)

    def test_detail_view_hides_private_connections_from_anonymous_users(self):
        owner = self.owner_user
        showcase = self.published_object
        public_material = Material.objects.create(
            name="Public Detail Feedstock", publication_status="published"
        )
        private_material = Material.objects.create(
            name="Private Detail Feedstock", owner=owner
        )
        for material in (public_material, private_material):
            showcase.showcase_materials.create(material=material, role="input")
        showcase.showcase_processes.create(
            process=Process.objects.create(name="Private Detail Step", owner=owner),
            order=1,
        )

        response = self.client.get(self.get_detail_url(showcase.pk))

        self.assertContains(response, "Public Detail Feedstock")
        self.assertNotContains(response, "Private Detail Feedstock")
        self.assertNotContains(response, "Private Detail Step")

        self.client.force_login(owner)
        response = self.client.get(self.get_detail_url(showcase.pk))
        self.assertContains(response, "Private Detail Feedstock")
        self.assertContains(response, "Private Detail Step")

    def test_detail_map_omits_private_catchment_for_anonymous_users(self):
        owner = self.owner_user
        showcase = self.published_object
        showcase.catchment = Catchment.objects.create(
            name="Private Map Catchment", region=showcase.region, owner=owner
        )
        showcase.save()

        response = self.client.get(self.get_detail_url(showcase.pk))
        self.assertIsNone(response.context["view"].get_catchment_feature_id())

        self.client.force_login(owner)
        response = self.client.get(self.get_detail_url(showcase.pk))
        self.assertEqual(
            showcase.catchment.pk, response.context["view"].get_catchment_feature_id()
        )


class ShowcaseGeoJSONVersionTestCase(TestCase):
    """The showcase GeoJSON serializes its region's name and borders, so the
    dataset version used for client cache revalidation must track them."""

    def setUp(self):
        self.region = Region.objects.create(
            name="Showcase Region", publication_status="published"
        )
        self.region.geom = MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)))
        self.region.save()
        Showcase.objects.create(
            name="Showcase", region=self.region, publication_status="published"
        )

    def version(self):
        response = self.client.get(
            reverse("api-showcase-version"), {"scope": "published"}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["version"]

    def test_geojson_header_matches_version_action(self):
        response = self.client.get(
            reverse("api-showcase-geojson"), {"scope": "published"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Data-Version"], self.version())

    def test_version_changes_when_region_borders_change_in_place(self):
        before = self.version()

        # A savepoint gives the update its own (sub)transaction id, as a
        # separate request would in production.
        with transaction.atomic():
            borders = GeoPolygon.objects.get(pk=self.region.borders_id)
            borders.geom = MultiPolygon(Polygon.from_bbox((0, 0, 2, 2)))
            borders.save()

        self.assertNotEqual(self.version(), before)

    def test_version_changes_when_region_is_modified(self):
        before = self.version()

        Region.objects.filter(pk=self.region.pk).update(
            name="Renamed Region",
            lastmodified_at=timezone.now() + timedelta(seconds=5),
        )

        self.assertNotEqual(self.version(), before)

    def test_version_changes_on_region_edits_within_one_second(self):
        first_edit = timezone.now().replace(microsecond=100_000) + timedelta(seconds=5)
        Region.objects.filter(pk=self.region.pk).update(
            name="North", lastmodified_at=first_edit
        )
        before = self.version()

        Region.objects.filter(pk=self.region.pk).update(
            name="East", lastmodified_at=first_edit.replace(microsecond=800_000)
        )

        self.assertNotEqual(self.version(), before)

    def test_version_rotates_on_catchment_region_border_change_in_place(self):
        """The GeoJSON also ships pilot polygons built from catchment region
        borders, so in-place border edits must rotate the version."""
        catchment_region = Region.objects.create(
            name="TBN Region", publication_status="published"
        )
        catchment_region.geom = MultiPolygon(Polygon.from_bbox((3, 3, 4, 4)))
        catchment_region.save()
        catchment = Catchment.objects.create(
            name="TBN Catchment",
            region=catchment_region,
            publication_status="published",
        )
        Showcase.objects.filter(region=self.region).update(catchment=catchment)
        before = self.version()

        with transaction.atomic():
            borders = GeoPolygon.objects.get(pk=catchment_region.borders_id)
            borders.geom = MultiPolygon(Polygon.from_bbox((3, 3, 5, 5)))
            borders.save()

        self.assertNotEqual(self.version(), before)

    def test_version_rotates_when_catchment_is_modified(self):
        catchment = Catchment.objects.create(
            name="TBN Catchment",
            region=self.region,
            publication_status="published",
        )
        Showcase.objects.filter(region=self.region).update(catchment=catchment)
        before = self.version()

        Catchment.objects.filter(pk=catchment.pk).update(
            name="Renamed Catchment",
            lastmodified_at=timezone.now() + timedelta(seconds=5),
        )

        self.assertNotEqual(self.version(), before)

    def test_version_rotates_on_catchment_reassignment(self):
        other_region = Region.objects.create(
            name="Other TBN Region", publication_status="published"
        )
        other_catchment = Catchment.objects.create(
            name="Other Catchment",
            region=other_region,
            publication_status="published",
        )
        before = self.version()

        showcase = Showcase.objects.get(region=self.region)
        showcase.catchment = other_catchment
        showcase.save()

        self.assertNotEqual(self.version(), before)

    def _two_catchment_pilots(self):
        """Two showcases, each with its own published catchment; the first
        catchment carries the older modification time."""
        older, newer = (
            Catchment.objects.create(
                name=name, region=self.region, publication_status="published"
            )
            for name in ("Older Catchment", "Newer Catchment")
        )
        now = timezone.now()
        Catchment.objects.filter(pk=older.pk).update(
            lastmodified_at=now - timedelta(hours=2)
        )
        Catchment.objects.filter(pk=newer.pk).update(
            lastmodified_at=now - timedelta(hours=1)
        )
        Showcase.objects.filter(region=self.region).update(catchment=older)
        Showcase.objects.create(
            name="Second Showcase",
            region=self.region,
            catchment=newer,
            publication_status="published",
        )
        older.refresh_from_db()
        return older, newer

    def test_version_rotates_when_non_latest_catchment_changes(self):
        """Max aggregates miss edits to a row below the latest timestamp."""
        older, _ = self._two_catchment_pilots()
        before = self.version()

        with transaction.atomic():
            Catchment.objects.filter(pk=older.pk).update(
                name="Renamed Older Catchment",
                lastmodified_at=older.lastmodified_at + timedelta(minutes=1),
            )

        self.assertNotEqual(self.version(), before)

    def test_version_rotates_when_non_latest_fallback_region_changes(self):
        other_region = Region.objects.create(
            name="Other Region", publication_status="published"
        )
        Showcase.objects.create(
            name="Other Showcase",
            region=other_region,
            publication_status="published",
        )
        older_mod = timezone.now() - timedelta(hours=2)
        Region.objects.filter(pk=self.region.pk).update(lastmodified_at=older_mod)
        before = self.version()

        with transaction.atomic():
            Region.objects.filter(pk=self.region.pk).update(
                name="Renamed Region",
                lastmodified_at=older_mod + timedelta(minutes=1),
            )

        self.assertNotEqual(self.version(), before)

    def test_version_timestamp_carries_pilot_region_schema_salt(self):
        from ..viewsets import ShowcaseViewSet

        self.assertIn("pilot-regions-v1", ShowcaseViewSet()._version_timestamp({}))
