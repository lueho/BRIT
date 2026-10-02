"""ViewSet tests for the processes module API."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from rest_framework import status
from rest_framework.test import APITestCase

from materials.models import Material
from utils.properties.models import Unit

from ..models import (
    Process,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
)


class ProcessCategoryViewSetTestCase(APITestCase):
    """Test ProcessCategory API endpoints."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.category1 = ProcessCategory.objects.create(
            name="Thermochemical",
            description="Test description",
            owner=self.owner,
            publication_status="published",
        )
        self.category2 = ProcessCategory.objects.create(
            name="Biochemical",
            owner=self.owner,
            publication_status="published",
        )

    def test_list_categories(self):
        """API should list published categories."""
        response = self.client.get("/processes/api/categories/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_retrieve_category(self):
        """API should retrieve a single category."""
        response = self.client.get(f"/processes/api/categories/{self.category1.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Thermochemical")

    def test_search_categories(self):
        """API should support searching categories."""
        response = self.client.get("/processes/api/categories/?search=Thermo")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_category_processes_action(self):
        """API should return processes in a category."""
        process = Process.objects.create(
            name="Test Process",
            owner=self.owner,
            publication_status="published",
        )
        process.categories.add(self.category1)

        response = self.client.get(
            f"/processes/api/categories/{self.category1.pk}/processes/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ProcessViewSetTestCase(APITestCase):
    """Test Process API endpoints."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        self.category = ProcessCategory.objects.create(
            name="Thermochemical",
            owner=self.owner,
            publication_status="published",
        )

        self.process1 = Process.objects.create(
            name="Pyrolysis",
            short_description="Thermal decomposition",
            mechanism="Thermal Decomposition",
            owner=self.owner,
            publication_status="published",
        )
        self.process1.categories.add(self.category)

        self.process2 = Process.objects.create(
            name="Gasification",
            mechanism="Partial Oxidation",
            owner=self.owner,
            publication_status="published",
        )

        # Add materials
        self.material_in = Material.objects.create(
            name="Wood Chips",
            owner=self.owner,
            publication_status="published",
        )
        self.material_out = Material.objects.create(
            name="Bio-oil",
            owner=self.owner,
            publication_status="published",
        )

        ProcessMaterial.objects.create(
            process=self.process1,
            material=self.material_in,
            role=ProcessMaterial.Role.INPUT,
        )
        ProcessMaterial.objects.create(
            process=self.process1,
            material=self.material_out,
            role=ProcessMaterial.Role.OUTPUT,
        )

        # Add operating parameters
        self.unit = Unit.objects.create(
            name="°C",
            owner=self.owner,
            publication_status="published",
        )

        ProcessOperatingParameter.objects.create(
            process=self.process1,
            parameter=ProcessOperatingParameter.Parameter.TEMPERATURE,
            value_min=Decimal("400"),
            value_max=Decimal("700"),
            unit=self.unit,
        )

    def test_list_processes(self):
        """API should list published processes."""
        response = self.client.get("/processes/api/processes/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_retrieve_process(self):
        """API should retrieve a single process with full details."""
        response = self.client.get(f"/processes/api/processes/{self.process1.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Pyrolysis")
        self.assertIn("input_materials", response.data)
        self.assertIn("output_materials", response.data)

    def test_search_processes(self):
        """API should support searching processes."""
        response = self.client.get("/processes/api/processes/?search=Pyro")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_materials_action(self):
        """API should return process materials."""
        response = self.client.get(
            f"/processes/api/processes/{self.process1.pk}/materials/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("inputs", response.data)
        self.assertIn("outputs", response.data)
        self.assertEqual(len(response.data["inputs"]), 1)
        self.assertEqual(len(response.data["outputs"]), 1)

    def test_parameters_action(self):
        """API should return operating parameters."""
        response = self.client.get(
            f"/processes/api/processes/{self.process1.pk}/parameters/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_parameters_by_type_action(self):
        """API should return parameters grouped by type."""
        response = self.client.get(
            f"/processes/api/processes/{self.process1.pk}/parameters_by_type/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Temperature", response.data)

    def test_by_category_action(self):
        """API should group processes by category."""
        response = self.client.get("/processes/api/processes/by_category/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))

    def test_by_mechanism_action(self):
        """API should group processes by mechanism."""
        response = self.client.get("/processes/api/processes/by_mechanism/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Thermal Decomposition", response.data)
        self.assertIn("Partial Oxidation", response.data)

    def test_variants_action(self):
        """API should return process variants."""
        Process.objects.create(
            name="Fast Pyrolysis",
            parent=self.process1,
            owner=self.owner,
            publication_status="published",
        )

        response = self.client.get(
            f"/processes/api/processes/{self.process1.pk}/variants/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Fast Pyrolysis")


class ProcessAPIPermissionsTestCase(APITestCase):
    """Write access on the processes API must follow the object policy."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="api_owner")
        cls.member = get_user_model().objects.create_user(username="api_member")
        cls.member.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="processes",
                codename__in=["add_process", "add_processcategory"],
            )
        )
        cls.published_process = Process.objects.create(
            name="Published Process",
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_process = Process.objects.create(
            name="Private Process",
            owner=cls.owner,
        )
        cls.published_category = ProcessCategory.objects.create(
            name="Published Category",
            owner=cls.owner,
            publication_status="published",
        )

    def test_anonymous_cannot_create_process(self):
        response = self.client.post(
            "/processes/api/processes/", {"name": "Anon"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Process.objects.filter(name="Anon").exists())

    def test_anonymous_cannot_create_category(self):
        response = self.client.post(
            "/processes/api/categories/", {"name": "Anon"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(ProcessCategory.objects.filter(name="Anon").exists())

    def test_anonymous_cannot_patch_process(self):
        response = self.client.patch(
            f"/processes/api/processes/{self.published_process.pk}/",
            {"name": "Defaced", "publication_status": "archived"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.published_process.refresh_from_db()
        self.assertEqual(self.published_process.name, "Published Process")
        self.assertEqual(self.published_process.publication_status, "published")

    def test_anonymous_cannot_delete_process(self):
        response = self.client.delete(
            f"/processes/api/processes/{self.published_process.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Process.objects.filter(pk=self.published_process.pk).exists())

    def test_anonymous_cannot_delete_category(self):
        response = self.client.delete(
            f"/processes/api/categories/{self.published_category.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(
            ProcessCategory.objects.filter(pk=self.published_category.pk).exists()
        )

    def test_authenticated_without_add_permission_cannot_create(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            "/processes/api/processes/", {"name": "NoPerm"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Process.objects.filter(name="NoPerm").exists())

    def test_member_create_process_becomes_private_and_owned(self):
        self.client.force_login(self.member)
        response = self.client.post(
            "/processes/api/processes/",
            {"name": "Member Process", "publication_status": "published"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        process = Process.objects.get(name="Member Process")
        self.assertEqual(process.owner, self.member)
        # publication_status must not be client-settable; new objects start private
        self.assertEqual(process.publication_status, "private")

    def test_owner_cannot_patch_published_process(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            f"/processes/api/processes/{self.published_process.pk}/",
            {"name": "Renamed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_patch_private_process(self):
        self.client.force_login(self.owner)
        response = self.client.patch(
            f"/processes/api/processes/{self.private_process.pk}/",
            {"name": "Renamed Private"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_process.refresh_from_db()
        self.assertEqual(self.private_process.name, "Renamed Private")

    def test_non_owner_cannot_patch_private_process(self):
        self.client.force_login(self.member)
        response = self.client.patch(
            f"/processes/api/processes/{self.private_process.pk}/",
            {"name": "Hijack"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.private_process.refresh_from_db()
        self.assertEqual(self.private_process.name, "Private Process")

    def test_anonymous_can_read_detail_actions_on_published_process(self):
        for suffix in ("materials", "parameters", "variants", "sources"):
            response = self.client.get(
                f"/processes/api/processes/{self.published_process.pk}/{suffix}/"
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                msg=f"anonymous GET {suffix} should be allowed",
            )

    def test_anonymous_can_read_collection_actions(self):
        for suffix in ("by_category", "by_mechanism"):
            response = self.client.get(f"/processes/api/processes/{suffix}/")
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                msg=f"anonymous GET {suffix} should be allowed",
            )

    def test_anonymous_cannot_read_private_process(self):
        response = self.client.get(
            f"/processes/api/processes/{self.private_process.pk}/"
        )
        self.assertIn(
            response.status_code,
            (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ),
        )

    def test_owner_can_read_own_private_process(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            f"/processes/api/processes/{self.private_process.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ProcessAPIRelatedVisibilityTestCase(APITestCase):
    """Custom read actions must apply the same read policy as the HTML UI.

    Anonymous users only see published related objects; authenticated users
    additionally see their own non-published objects, matching
    ``filter_queryset_for_user`` semantics used by the list/detail views.
    """

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="vis_owner")
        cls.other = user_model.objects.create_user(username="vis_other")
        cls.category = ProcessCategory.objects.create(
            name="Shared Category",
            owner=cls.other,
            publication_status="published",
        )
        cls.published_process = Process.objects.create(
            name="Published Member",
            owner=cls.other,
            publication_status="published",
        )
        cls.published_process.categories.add(cls.category)
        cls.own_private_process = Process.objects.create(
            name="My Private Member",
            owner=cls.owner,
            publication_status="private",
        )
        cls.own_private_process.categories.add(cls.category)
        cls.foreign_private_process = Process.objects.create(
            name="Foreign Private Member",
            owner=cls.other,
            publication_status="private",
        )
        cls.foreign_private_process.categories.add(cls.category)
        cls.own_private_variant = Process.objects.create(
            name="My Private Variant",
            parent=cls.published_process,
            owner=cls.owner,
            publication_status="private",
        )
        cls.foreign_private_variant = Process.objects.create(
            name="Foreign Private Variant",
            parent=cls.published_process,
            owner=cls.other,
            publication_status="private",
        )

    def _member_names(self, response):
        return {entry["name"] for entry in response.data}

    def test_category_processes_anonymous_sees_only_published(self):
        response = self.client.get(
            f"/processes/api/categories/{self.category.pk}/processes/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._member_names(response), {"Published Member"})

    def test_category_processes_owner_sees_own_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            f"/processes/api/categories/{self.category.pk}/processes/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._member_names(response),
            {"Published Member", "My Private Member"},
        )

    def test_variants_anonymous_sees_only_published(self):
        response = self.client.get(
            f"/processes/api/processes/{self.published_process.pk}/variants/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_variants_owner_sees_own_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            f"/processes/api/processes/{self.published_process.pk}/variants/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._member_names(response), {"My Private Variant"})

    def test_by_category_anonymous_excludes_private(self):
        response = self.client.get("/processes/api/processes/by_category/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {
            process["name"]
            for entry in response.data
            for process in entry["processes"]
        }
        self.assertEqual(names, {"Published Member"})

    def test_by_category_owner_includes_own_private(self):
        self.client.force_login(self.owner)
        response = self.client.get("/processes/api/processes/by_category/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {
            process["name"]
            for entry in response.data
            for process in entry["processes"]
        }
        self.assertEqual(names, {"Published Member", "My Private Member"})


class ProcessAPIQueryCountTestCase(APITestCase):
    """Grouping endpoints must not issue a query per category or per process."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="perf_owner")

    def _add_category_with_process(self, index):
        category = ProcessCategory.objects.create(
            name=f"Perf Category {index}",
            owner=self.owner,
            publication_status="published",
        )
        process = Process.objects.create(
            name=f"Perf Process {index}",
            mechanism=f"Mechanism {index}",
            owner=self.owner,
            publication_status="published",
        )
        process.categories.add(category)

    def test_by_category_query_count_is_constant(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._add_category_with_process(1)
        with CaptureQueriesContext(connection) as baseline:
            self.client.get("/processes/api/processes/by_category/")
        for index in range(2, 6):
            self._add_category_with_process(index)
        with CaptureQueriesContext(connection) as scaled:
            self.client.get("/processes/api/processes/by_category/")
        self.assertEqual(len(scaled), len(baseline))

    def test_by_mechanism_query_count_is_constant(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._add_category_with_process(1)
        with CaptureQueriesContext(connection) as baseline:
            self.client.get("/processes/api/processes/by_mechanism/")
        for index in range(2, 6):
            self._add_category_with_process(index)
        with CaptureQueriesContext(connection) as scaled:
            self.client.get("/processes/api/processes/by_mechanism/")
        self.assertEqual(len(scaled), len(baseline))
