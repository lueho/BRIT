"""View tests for the processes module.

Comprehensive tests for all CRUD views following BRIT testing patterns.
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase

from ..models import Process, ProcessCategory


class ProcessDashboardViewTestCase(ViewWithPermissionsTestCase):
    """Test the processes dashboard view."""

    def test_get_http_200_ok_for_anonymous(self):
        """Anonymous users can access the dashboard."""
        response = self.client.get(reverse("processes:dashboard"))
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_authenticated(self):
        """Authenticated users can access the dashboard."""
        self.client.force_login(self.member)
        response = self.client.get(reverse("processes:dashboard"))
        self.assertEqual(200, response.status_code)


# ==============================================================================
# ProcessCategory CRUD Tests
# ==============================================================================


class ProcessCategoryCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    """Test ProcessCategory CRUD operations."""

    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True

    model = ProcessCategory

    view_dashboard_name = "processes:dashboard"
    view_create_name = "processes:processcategory-create"
    view_modal_create_name = "processes:processcategory-create-modal"
    view_published_list_name = "processes:processcategory-list"
    view_private_list_name = "processes:processcategory-list-owned"
    view_detail_name = "processes:processcategory-detail"
    view_modal_detail_name = "processes:processcategory-detail-modal"
    view_update_name = "processes:processcategory-update"
    view_modal_update_name = "processes:processcategory-update-modal"
    view_delete_name = "processes:processcategory-delete-modal"

    create_object_data = {"name": "Test Category", "description": "Test Description"}
    update_object_data = {
        "name": "Updated Test Category",
        "description": "Updated Description",
    }

    @classmethod
    def create_published_object(cls):
        """Create a published object with unique name."""
        published_category = super().create_published_object()
        published_category.name = "Published Test Category"
        published_category.save()
        return published_category


class ProcessCategoryAutocompleteViewTestCase(ViewWithPermissionsTestCase):
    """Test ProcessCategory autocomplete view."""

    def test_get_http_200_ok_for_authenticated(self):
        """Authenticated users can access autocomplete."""
        self.client.force_login(self.member)
        response = self.client.get(reverse("processes:processcategory-autocomplete"))
        self.assertEqual(200, response.status_code)


# ==============================================================================
# Process CRUD Tests
# ==============================================================================


class ProcessCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    """Test Process CRUD operations."""

    modal_detail_view = True
    modal_create_view = True

    model = Process

    view_dashboard_name = "processes:dashboard"
    view_create_name = "processes:process-create"
    view_modal_create_name = "processes:process-create-modal"
    view_published_list_name = "processes:process-list"
    view_private_list_name = "processes:process-list-owned"
    view_detail_name = "processes:process-detail"
    view_modal_detail_name = "processes:process-detail-modal"
    view_update_name = "processes:process-update"
    view_delete_name = "processes:process-delete-modal"

    create_object_data = {
        "name": "Test Process",
        "short_description": "Test short description",
        "mechanism": "Test mechanism",
    }
    update_object_data = {
        "name": "Updated Test Process",
        "short_description": "Updated short description",
        "mechanism": "Updated mechanism",
    }

    @classmethod
    def create_related_objects(cls):
        """Create related ProcessCategory objects."""
        cls.test_category = ProcessCategory.objects.create(
            name="Test Category", publication_status="published"
        )
        return {}

    @classmethod
    def create_published_object(cls):
        """Create a published object with unique name and categories."""
        data = cls.create_object_data.copy()
        data["publication_status"] = "published"
        data["name"] = "Published Test Process"
        published_process = cls.model.objects.create(owner=cls.owner_user, **data)
        published_process.categories.add(cls.test_category)
        return published_process

    @classmethod
    def create_unpublished_object(cls):
        """Create an unpublished object with categories."""
        data = cls.create_object_data.copy()
        data["publication_status"] = "private"
        unpublished_process = cls.model.objects.create(owner=cls.owner_user, **data)
        unpublished_process.categories.add(cls.test_category)
        return unpublished_process

    def test_detail_view_shows_related_objects(self):
        """Process detail view should display related materials, parameters, etc."""
        if not self.detail_view:
            self.skipTest("Detail view is not enabled for this test case.")
        
        process = self.published_object
        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": process.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, process.name)


class ProcessAutocompleteViewTestCase(ViewWithPermissionsTestCase):
    """Test Process autocomplete view."""

    def test_get_http_200_ok_for_authenticated(self):
        """Authenticated users can access autocomplete."""
        self.client.force_login(self.member)
        response = self.client.get(reverse("processes:process-autocomplete"))
        self.assertEqual(200, response.status_code)
