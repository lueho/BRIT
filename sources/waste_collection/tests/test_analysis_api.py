"""Contract for the paginated, permission-aware R analysis interface."""

from django.urls import reverse
from rest_framework.test import APITestCase

from sources.waste_collection.models import CollectionPropertyValue
from sources.waste_collection.tests import test_viewsets as fixtures
from utils.properties.models import Property, Unit


class CollectionAnalysisApiTests(APITestCase):
    setUpTestData = classmethod(
        fixtures.CollectionViewSetTestCase.setUpTestData.__func__
    )
    _create_collection = classmethod(
        fixtures.CollectionViewSetTestCase._create_collection.__func__
    )

    def endpoint(self):
        return reverse("api-waste-collection-analysis")

    def test_public_page_has_versioned_contract_and_stable_identifiers(self):
        response = self.client.get(self.endpoint(), {"page_size": 1})
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
        first = self.client.get(self.endpoint(), {"page_size": 1}).data
        second = self.client.get(first["next"]).data
        self.assertEqual(second["schema_version"], first["schema_version"])
        self.assertNotEqual(first["results"][0]["id"], second["results"][0]["id"])
        self.assertIsNone(second["next"])

    def test_collection_filter_is_applied(self):
        response = self.client.get(
            self.endpoint(), {"id": self.published_collection.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"], self.published_collection.pk
        )

    def test_anonymous_cannot_request_non_public_scope(self):
        for scope in ("private", "review", "all"):
            with self.subTest(scope=scope):
                response = self.client.get(self.endpoint(), {"scope": scope})
                self.assertIn(response.status_code, (401, 403))

    def test_owner_scope_does_not_expose_other_owners_private_data(self):
        self.client.force_authenticate(self.regular_user)
        response = self.client.get(self.endpoint(), {"scope": "private"})
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(self.private_collection.pk, ids)
        self.assertNotIn(self.other_user_private_collection.pk, ids)

    def test_password_login_token_can_read_own_private_analysis(self):
        self.regular_user.set_password("test-password")
        self.regular_user.save(update_fields=["password"])
        login = self.client.post(
            reverse("api-token-auth"),
            {"username": self.regular_user.username, "password": "test-password"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("token", login.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
        response = self.client.get(self.endpoint(), {"scope": "private"})
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(self.private_collection.pk, ids)
        self.assertNotIn(self.other_user_private_collection.pk, ids)
        all_visible = self.client.get(self.endpoint(), {"scope": "all"})
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
        response = self.client.get(
            self.endpoint(), {"id": self.published_collection.pk}
        )
        self.assertEqual(response.status_code, 200)
        row = response.data["results"][0]
        self.assertEqual(row["connection_rate_2024"], 0)
        self.assertEqual(row["connection_rate_2024_unit"], "%")
        self.assertNotIn("connection_rate_2025", row)

    def test_empty_result_still_has_a_versioned_envelope(self):
        response = self.client.get(self.endpoint(), {"publication_status": "private"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["schema_version"], "1.0")
        self.assertEqual(response.data["results"], [])

    def test_read_only_action(self):
        self.client.force_authenticate(self.staff_user)
        self.assertEqual(self.client.post(self.endpoint(), {}).status_code, 405)
