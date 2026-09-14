from django.urls import reverse

from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase

from ..models import Property, Unit

# ----------- Unit CRUD ------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class UnitCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Unit

    view_dashboard_name = "properties-dashboard"
    view_create_name = "unit-create"
    view_published_list_name = "unit-list"
    view_private_list_name = "unit-list-owned"
    view_detail_name = "unit-detail"
    view_update_name = "unit-update"
    view_delete_name = "unit-delete-modal"

    create_object_data = {"name": "Test Unit"}
    update_object_data = {"name": "Updated Test Unit"}

    @classmethod
    def create_published_object(cls):
        # Change the name of the published object to avoid unique constraint violation
        unit = super().create_published_object()
        unit.name = "Test Unit 2"
        unit.save()
        return unit


class UnitAutocompleteViewTestCase(ViewWithPermissionsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.matching_unit = Unit.objects.create(
            name="Kilogram",
            publication_status="published",
        )
        Unit.objects.create(
            name="Litre",
            publication_status="published",
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("unit-autocomplete"))
        self.assertEqual(response.status_code, 200)

    def test_get_returns_results_including_created_unit(self):
        response = self.client.get(reverse("unit-autocomplete"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.json())
        result_ids = {item["id"] for item in response.json()["results"]}
        self.assertIn(self.matching_unit.pk, result_ids)

    def test_search_by_name_returns_matching_unit(self):
        """A `q` query should filter results by unit name and exclude non-matches."""
        response = self.client.get(reverse("unit-autocomplete"), {"q": "Kilogram"})
        self.assertEqual(response.status_code, 200)
        result_ids = {item["id"] for item in response.json()["results"]}
        self.assertIn(self.matching_unit.pk, result_ids)
        # Non-matching units must be filtered out by the search query.
        litre = Unit.objects.get(name="Litre")
        self.assertNotIn(litre.pk, result_ids)

    def test_search_by_symbol_returns_matching_unit(self):
        """A `q` query should filter results by unit symbol."""
        unit_with_symbol = Unit.objects.create(
            name="Test Symbol Unit",
            symbol="tsu_sym",
            publication_status="published",
        )
        try:
            response = self.client.get(reverse("unit-autocomplete"), {"q": "tsu_sym"})
            self.assertEqual(response.status_code, 200)
            result_ids = {item["id"] for item in response.json()["results"]}
            self.assertIn(unit_with_symbol.pk, result_ids)
            # Non-matching units must be filtered out by the search query.
            self.assertNotIn(self.matching_unit.pk, result_ids)
        finally:
            unit_with_symbol.delete()

    def test_search_returns_private_unit_for_owner(self):
        """An owner should find their private unit via autocomplete search."""
        private_unit = Unit.objects.create(
            name="Owner Private Unit",
            owner=self.owner,
            publication_status="private",
        )
        try:
            self.client.force_login(self.owner)
            response = self.client.get(
                reverse("unit-autocomplete"), {"q": "Owner Private"}
            )
            self.assertEqual(response.status_code, 200)
            result_ids = {item["id"] for item in response.json()["results"]}
            self.assertIn(private_unit.pk, result_ids)
            # Non-matching units must be filtered out by the search query.
            self.assertNotIn(self.matching_unit.pk, result_ids)
        finally:
            private_unit.delete()


# ----------- Property CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PropertyCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Property

    view_dashboard_name = "properties-dashboard"
    view_create_name = "property-create"
    view_published_list_name = "property-list"
    view_private_list_name = "property-list-owned"
    view_detail_name = "property-detail"
    view_update_name = "property-update"
    view_delete_name = "property-delete-modal"

    create_object_data = {"name": "Test Property"}
    update_object_data = {"name": "Updated Test Property"}

    @classmethod
    def create_related_objects(cls):
        return {
            "unit": Unit.objects.create(
                name="Test Unit", publication_status="published"
            )
        }

    def related_objects_post_data(self):
        data = super().related_objects_post_data()
        data["allowed_units"] = [self.related_objects["unit"].pk]
        return data


# ----------- Property Utils -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class PropertyUnitOptionsViewTestCase(ViewWithPermissionsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        allowed_unit_1 = Unit.objects.create(name="Allowed Unit 1")
        allowed_unit_2 = Unit.objects.create(name="Allowed Unit 2")
        Unit.objects.create(name="Not Allowed Unit")
        cls.prop = Property.objects.create(name="Test Property")
        cls.prop.allowed_units.set([allowed_unit_1, allowed_unit_2])

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(
            reverse("property-unit-options", kwargs={"pk": self.prop.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("property-unit-options", kwargs={"pk": self.prop.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_response_options_contains_only_allowed_options(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("property-unit-options", kwargs={"pk": self.prop.pk})
        )
        self.assertEqual(response.status_code, 200)
        options = response.json()["options"]
        for unit in Unit.objects.all():
            option = f'<option value="{unit.id}"'
            if unit in self.prop.allowed_units.all():
                self.assertIn(option, options)
            else:
                self.assertNotIn(option, options)
