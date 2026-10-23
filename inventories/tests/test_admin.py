from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventories.models import (
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
)


class InventoryAlgorithmParameterValueAdminSearchTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser(
            username="inventory_admin_search",
            email="inventory-admin@example.com",
            password="pw",
        )
        parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Yield", short_name="yield"
        )
        cls.custom = InventoryAlgorithmParameterValue.objects.create(
            name="",
            parameter=parameter,
            value=3.5,
            source="User assumption",
            is_custom=True,
        )
        cls.other = InventoryAlgorithmParameterValue.objects.create(
            name="",
            parameter=parameter,
            value=7.25,
            source="User assumption",
            is_custom=True,
        )

    def autocomplete(self, term):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "inventories",
                "model_name": "scenarioinventoryconfiguration",
                "field_name": "inventory_value",
                "term": term,
            },
        )
        self.assertEqual(response.status_code, 200)
        return {int(result["id"]) for result in response.json()["results"]}

    def test_autocomplete_matches_custom_value_by_number(self):
        self.assertEqual(self.autocomplete("3.5"), {self.custom.pk})

    def test_autocomplete_matches_number_written_differently(self):
        self.assertEqual(self.autocomplete("3.50"), {self.custom.pk})

    def test_autocomplete_text_search_still_matches_source(self):
        self.assertEqual(
            self.autocomplete("User assumption"), {self.custom.pk, self.other.pk}
        )

    def test_autocomplete_ignores_non_finite_numbers(self):
        self.assertEqual(self.autocomplete("nan"), set())
