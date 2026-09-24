"""Contract for the optional extended collection list representation."""

from datetime import date

from django.contrib.auth.models import Group, User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from maps.models import (
    LauRegion,
    NutsRegion,
    Region,
    RegionAttributeValue,
    RegionProperty,
)
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
)
from sources.waste_collection.tests import test_viewsets as fixtures
from sources.waste_collection.viewsets import CollectionViewSet
from utils.properties.models import Property, Unit


class CollectionAnalysisApiTests(APITestCase):
    setUpTestData = classmethod(
        fixtures.CollectionViewSetTestCase.setUpTestData.__func__
    )
    _create_collection = classmethod(
        fixtures.CollectionViewSetTestCase._create_collection.__func__
    )

    def setUp(self):
        super().setUp()
        self.analysis_group = Group.objects.get_or_create(
            name=CollectionViewSet.analysis_group_name
        )[0]
        self.analyst = User.objects.create_user(username="analyst")
        self.analyst.groups.add(self.analysis_group)
        self.regular_user.groups.add(self.analysis_group)
        self.client.force_authenticate(self.analyst)

    def endpoint(self):
        return reverse("api-waste-collection-list")

    def get_extended(self, params=None):
        return self.client.get(self.endpoint(), {"view": "extended", **(params or {})})

    def test_extended_view_requires_analysis_group(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.get_extended().status_code, 401)
        outsider = User.objects.create_user(username="outsider")
        self.client.force_authenticate(outsider)
        self.assertEqual(self.get_extended().status_code, 403)
        self.assertEqual(
            self.client.get(self.endpoint(), {"page_size": 1}).status_code, 200
        )
        self.client.force_authenticate(self.staff_user)
        self.assertEqual(self.get_extended().status_code, 200)

    def test_default_list_remains_lean(self):
        prop = Property.objects.get_or_create(name="Connection rate")[0]
        unit = Unit.objects.get_or_create(name="%")[0]
        CollectionPropertyValue.objects.create(
            collection=self.published_collection,
            property=prop,
            unit=unit,
            year=2024,
            average=42,
            owner=self.regular_user,
            publication_status="published",
        )
        response = self.client.get(self.endpoint(), {"page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("schema_version", response.data)
        self.assertNotIn("generated_at", response.data)
        self.assertNotIn("snapshot_isolation", response.data)
        self.assertNotIn("connection_rate_2024", response.data["results"][0])
        self.client.force_authenticate(self.regular_user)
        self.assertEqual(
            self.client.get(self.endpoint(), {"scope": "all"}).status_code, 400
        )

    def test_unknown_view_is_rejected(self):
        response = self.client.get(self.endpoint(), {"view": "unknown"})
        self.assertEqual(response.status_code, 400)

    def test_public_page_has_versioned_contract_and_stable_identifiers(self):
        response = self.get_extended({"page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["schema_version"], "1.0")
        self.assertEqual(response.data["count"], 2)
        self.assertIsNotNone(response.data["next"])
        row = response.data["results"][0]
        self.assertEqual(row["id"], self.published_collection.pk)
        self.assertEqual(row["publication_status"], "published")
        self.assertIn("catchment", row)
        self.assertIn("valid_from", row)
        self.assertIn("bibliography_sources", row)

    def test_all_pages_are_disjoint_and_use_same_contract(self):
        first = self.get_extended({"page_size": 1}).data
        second = self.client.get(first["next"]).data
        self.assertEqual(second["schema_version"], first["schema_version"])
        self.assertNotEqual(first["results"][0]["id"], second["results"][0]["id"])
        self.assertIsNone(second["next"])

    def test_collection_filter_is_applied(self):
        response = self.get_extended({"id": self.published_collection.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"], self.published_collection.pk
        )

    def test_anonymous_cannot_request_non_public_scope(self):
        self.client.force_authenticate(None)
        for scope in ("private", "review", "all"):
            with self.subTest(scope=scope):
                response = self.get_extended({"scope": scope})
                self.assertIn(response.status_code, (401, 403))

    def test_owner_scope_does_not_expose_other_owners_private_data(self):
        self.client.force_authenticate(self.regular_user)
        response = self.get_extended({"scope": "private"})
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(self.private_collection.pk, ids)
        self.assertNotIn(self.other_user_private_collection.pk, ids)

    def test_password_login_token_can_read_own_private_analysis(self):
        self.client.force_authenticate(None)
        self.regular_user.set_password("test-password")
        self.regular_user.save(update_fields=["password"])
        login = self.client.post(
            reverse("api-token-auth"),
            {"username": self.regular_user.username, "password": "test-password"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("token", login.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
        response = self.get_extended({"scope": "private"})
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(self.private_collection.pk, ids)
        self.assertNotIn(self.other_user_private_collection.pk, ids)
        all_visible = self.get_extended({"scope": "all"})
        self.assertEqual(all_visible.status_code, 200)
        visible_ids = {row["id"] for row in all_visible.data["results"]}
        self.assertIn(self.published_collection.pk, visible_ids)
        self.assertIn(self.private_collection.pk, visible_ids)
        self.assertNotIn(self.other_user_private_collection.pk, visible_ids)

    def test_metrics_keep_zero_and_units_but_hide_private_values(self):
        prop = Property.objects.get_or_create(name="Connection rate")[0]
        unit = Unit.objects.get_or_create(name="%")[0]
        for year, value, state in ((2024, 0, "published"), (2025, 99, "private")):
            CollectionPropertyValue.objects.create(
                collection=self.published_collection,
                property=prop,
                unit=unit,
                year=year,
                average=value,
                owner=self.regular_user,
                publication_status=state,
            )
        response = self.get_extended({"id": self.published_collection.pk})
        self.assertEqual(response.status_code, 200)
        row = response.data["results"][0]
        self.assertEqual(row["connection_rate_2024"], 0)
        self.assertEqual(row["connection_rate_2024_unit"], "%")
        self.assertNotIn("connection_rate_2025", row)

    def _create_regional_collection(self, name, region_name, region=None):
        if region is None:
            region = Region.objects.create(name=region_name, country="DE")
        catchment = CollectionCatchment.objects.create(name=name, region=region)
        collection = Collection.objects.create(
            name=name,
            owner=self.regular_user,
            catchment=catchment,
            waste_category=self.waste_category,
            collection_system=self.collection_system,
            publication_status="published",
            collector=self.collector,
        )
        return region, collection

    def test_private_region_attribute_values_are_hidden_from_other_users(self):
        region, collection = self._create_regional_collection("Regional", "Region A")
        population = RegionProperty.objects.get_or_create(name="Population")[0]
        for year, state in ((2023, "private"), (2024, "published")):
            RegionAttributeValue.objects.create(
                name=f"Population {year}",
                region=region,
                property=population,
                date=date(year, 1, 1),
                value=1000 + year,
                owner=self.staff_user,
                publication_status=state,
            )
        row = self.get_extended({"id": collection.pk}).data["results"][0]
        self.assertEqual(row["population_2024"], 3024)
        self.assertNotIn("population_2023", row)

    def test_metrics_with_different_units_are_all_kept(self):
        prop = Property.objects.get_or_create(name="total waste collected")[0]
        for unit_name, value in (("Mg/a", 5), ("kg/a", 5000)):
            CollectionPropertyValue.objects.create(
                collection=self.published_collection,
                property=prop,
                unit=Unit.objects.get_or_create(name=unit_name)[0],
                year=2024,
                average=value,
                owner=self.regular_user,
                publication_status="published",
            )
        row = self.get_extended({"id": self.published_collection.pk}).data["results"][0]
        self.assertNotIn("total_waste_collected_2024", row)
        self.assertEqual(row["total_waste_collected_2024_kg_a"], 5000)
        self.assertEqual(row["total_waste_collected_2024_kg_a_unit"], "kg/a")
        self.assertEqual(row["total_waste_collected_2024_mg_a"], 5)
        self.assertEqual(row["total_waste_collected_2024_mg_a_unit"], "Mg/a")

    def test_query_count_does_not_grow_with_page_size(self):
        prop = Property.objects.get_or_create(name="Connection rate")[0]
        total = Property.objects.get_or_create(name="total waste collected")[0]
        unit = Unit.objects.get_or_create(name="%")[0]
        population = RegionProperty.objects.get_or_create(name="Population")[0]
        nuts0 = NutsRegion.objects.create(
            name="Germany", country="DE", nuts_id="DE", levl_code=0
        )
        ids = []
        for index in range(4):
            nuts1 = NutsRegion.objects.create(
                name=f"Land {index}",
                country="DE",
                nuts_id=f"DE{index}",
                levl_code=1,
                parent=nuts0,
            )
            nuts2 = NutsRegion.objects.create(
                name=f"Bezirk {index}",
                country="DE",
                nuts_id=f"DE{index}1",
                levl_code=2,
                parent=nuts1,
            )
            nuts3 = NutsRegion.objects.create(
                name=f"Kreis {index}",
                country="DE",
                nuts_id=f"DE{index}11",
                levl_code=3,
                parent=nuts2,
            )
            if index % 2:
                lau = LauRegion.objects.create(
                    name=f"Gemeinde {index}",
                    country="DE",
                    lau_id=f"0{index}",
                    nuts_parent=nuts3,
                )
                region = lau.region_ptr
            else:
                region = nuts3.region_ptr
            region, collection = self._create_regional_collection(
                f"Regional {index}", f"Region {index}", region=region
            )
            successor = Collection.objects.create(
                name=f"Regional {index} v2",
                owner=self.regular_user,
                catchment=collection.catchment,
                waste_category=self.waste_category,
                collection_system=self.collection_system,
                publication_status="published",
                collector=self.collector,
                valid_from=date(2025, 1, 1),
            )
            successor.predecessors.add(collection)
            CollectionPropertyValue.objects.create(
                collection=collection,
                property=prop,
                unit=unit,
                year=2024,
                average=index,
                owner=self.regular_user,
                publication_status="published",
            )
            aggregated = AggregatedCollectionPropertyValue.objects.create(
                property=total,
                unit=unit,
                year=2024,
                average=10 + index,
                owner=self.regular_user,
                publication_status="published",
            )
            aggregated.collections.add(collection)
            RegionAttributeValue.objects.create(
                name=f"Population {index}",
                region=region,
                property=population,
                date=date(2024, 1, 1),
                value=100 + index,
                owner=self.regular_user,
                publication_status="published",
            )
            ids.append(successor.pk)

        self.get_extended({"id": ids[:1], "page_size": 1})
        with CaptureQueriesContext(connection) as single:
            one = self.get_extended({"id": ids[:1], "page_size": 1})
        with CaptureQueriesContext(connection) as several:
            many = self.get_extended({"id": ids, "page_size": 4})

        self.assertEqual(one.status_code, 200)
        self.assertEqual(many.status_code, 200)
        self.assertEqual(len(many.data["results"]), 4)
        for index, row in enumerate(many.data["results"]):
            self.assertEqual(row["connection_rate_2024"], index)
            self.assertEqual(row["total_waste_collected_2024"], 10 + index)
            self.assertTrue(row["aggregated"])
            self.assertEqual(row["population_2024"], 100 + index)
            self.assertEqual(row["nuts_0_id"], "DE")
            self.assertEqual(row["nuts_3_id"], f"DE{index}11")
        self.assertEqual(len(several), len(single))

    def test_empty_result_still_has_a_versioned_envelope(self):
        response = self.get_extended({"publication_status": "private"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["schema_version"], "1.0")
        self.assertEqual(response.data["results"], [])
