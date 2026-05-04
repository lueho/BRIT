"""View tests for the processes module.

Comprehensive tests for all CRUD views following BRIT testing patterns.
"""

from django.urls import reverse

from bibliography.models import Source
from materials.models import Material
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase

from ..models import Process, ProcessCategory, ProcessMaterial, ProcessReference


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
        "description": "",
    }
    update_object_data = {
        "name": "Updated Test Process",
        "short_description": "Updated short description",
        "mechanism": "Updated mechanism",
        "description": "Updated description",
    }

    @classmethod
    def create_related_objects(cls):
        """Create related ProcessCategory objects."""
        cls.test_category = ProcessCategory.objects.create(
            name="Test Category",
            publication_status="published",
            owner=cls.owner_user,
        )
        return {}

    def related_objects_post_data(self):
        """Override to handle many-to-many fields and inline formsets.

        Formset prefixes are based on the related_name attribute of ForeignKey fields:
        - ProcessMaterial: process_materials
        - ProcessOperatingParameter: operating_parameters
        - ProcessLink: links
        - ProcessInfoResource: info_resources
        - ProcessReference: references
        """
        return {
            "categories": [self.test_category.pk],
            # ProcessMaterialInline (related_name='process_materials')
            "process_materials-TOTAL_FORMS": "0",
            "process_materials-INITIAL_FORMS": "0",
            "process_materials-MIN_NUM_FORMS": "0",
            "process_materials-MAX_NUM_FORMS": "1000",
            # ProcessOperatingParameterInline (related_name='operating_parameters')
            "operating_parameters-TOTAL_FORMS": "0",
            "operating_parameters-INITIAL_FORMS": "0",
            "operating_parameters-MIN_NUM_FORMS": "0",
            "operating_parameters-MAX_NUM_FORMS": "1000",
            # ProcessLinkInline (related_name='links')
            "links-TOTAL_FORMS": "0",
            "links-INITIAL_FORMS": "0",
            "links-MIN_NUM_FORMS": "0",
            "links-MAX_NUM_FORMS": "1000",
            # ProcessInfoResourceInline (related_name='info_resources')
            "info_resources-TOTAL_FORMS": "0",
            "info_resources-INITIAL_FORMS": "0",
            "info_resources-MIN_NUM_FORMS": "0",
            "info_resources-MAX_NUM_FORMS": "1000",
            # ProcessReferenceInline (related_name='references')
            "references-TOTAL_FORMS": "0",
            "references-INITIAL_FORMS": "0",
            "references-MIN_NUM_FORMS": "0",
            "references-MAX_NUM_FORMS": "1000",
        }

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

    def test_detail_view_links_bibliography_references_to_modal(self):
        source = Source.objects.create(
            title="Reference Title",
            abbreviation="Ref01",
            owner=self.owner_user,
            publication_status="published",
        )
        ProcessReference.objects.create(process=self.published_object, source=source)
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("source-detail-modal", kwargs={"pk": source.pk}),
        )
        self.assertContains(response, "modal-link")
        self.assertContains(response, "Ref01")

    def test_detail_view_sorts_bibliography_alphabetically(self):
        zebra_source = Source.objects.create(
            title="Zebra Source",
            abbreviation="Zebra",
            owner=self.owner_user,
            publication_status="published",
        )
        alpha_source = Source.objects.create(
            title="Alpha Source",
            abbreviation="Alpha",
            owner=self.owner_user,
            publication_status="published",
        )
        ProcessReference.objects.create(
            process=self.published_object,
            source=zebra_source,
            order=1,
        )
        ProcessReference.objects.create(
            process=self.published_object,
            source=alpha_source,
            order=2,
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bibliography")
        self.assertNotContains(response, "<ol>")
        self.assertContains(response, '<ul class="list-unstyled">')
        self.assertLess(
            response.content.decode().index("Alpha"),
            response.content.decode().index("Zebra"),
        )

    def test_update_view_prefills_inline_select_values(self):
        material = Material.objects.create(
            name="Existing Material",
            owner=self.owner_user,
            publication_status="published",
        )
        ProcessMaterial.objects.create(
            process=self.unpublished_object,
            material=material,
            role=ProcessMaterial.Role.INPUT,
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_update_name, kwargs={"pk": self.unpublished_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="process-form"')
        self.assertContains(response, 'name="process_materials-TOTAL_FORMS"')
        self.assertContains(response, 'form="process-form"')
        self.assertContains(response, 'name="process_materials-0-material"')
        self.assertContains(response, "Existing Material")

    def test_update_view_posts_inline_management_forms(self):
        material = Material.objects.create(
            name="Existing POST Material",
            owner=self.owner_user,
            publication_status="published",
        )
        ProcessMaterial.objects.create(
            process=self.unpublished_object,
            material=material,
            role=ProcessMaterial.Role.INPUT,
        )
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse(self.view_update_name, kwargs={"pk": self.unpublished_object.pk}),
            {
                "name": self.unpublished_object.name,
                "short_description": self.unpublished_object.short_description,
                "mechanism": self.unpublished_object.mechanism,
                "description": self.unpublished_object.description,
                "categories": [self.test_category.pk],
                "process_materials-TOTAL_FORMS": "1",
                "process_materials-INITIAL_FORMS": "1",
                "process_materials-MIN_NUM_FORMS": "0",
                "process_materials-MAX_NUM_FORMS": "1000",
                "process_materials-0-material": material.pk,
                "process_materials-0-role": ProcessMaterial.Role.OUTPUT,
                "process_materials-0-order": "0",
                "process_materials-0-stage": "",
                "process_materials-0-stream_label": "",
                "process_materials-0-quantity_value": "",
                "process_materials-0-quantity_unit": "",
                "process_materials-0-notes": "",
                "process_materials-0-id": self.unpublished_object.process_materials.get().pk,
                "process_materials-0-process": self.unpublished_object.pk,
                "operating_parameters-TOTAL_FORMS": "0",
                "operating_parameters-INITIAL_FORMS": "0",
                "operating_parameters-MIN_NUM_FORMS": "0",
                "operating_parameters-MAX_NUM_FORMS": "1000",
                "links-TOTAL_FORMS": "0",
                "links-INITIAL_FORMS": "0",
                "links-MIN_NUM_FORMS": "0",
                "links-MAX_NUM_FORMS": "1000",
                "info_resources-TOTAL_FORMS": "0",
                "info_resources-INITIAL_FORMS": "0",
                "info_resources-MIN_NUM_FORMS": "0",
                "info_resources-MAX_NUM_FORMS": "1000",
                "references-TOTAL_FORMS": "0",
                "references-INITIAL_FORMS": "0",
                "references-MIN_NUM_FORMS": "0",
                "references-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertRedirects(
            response,
            reverse(self.view_detail_name, kwargs={"pk": self.unpublished_object.pk}),
        )
        self.unpublished_object.refresh_from_db()
        self.assertEqual(
            self.unpublished_object.process_materials.get().role,
            ProcessMaterial.Role.OUTPUT,
        )


class ProcessAutocompleteViewTestCase(ViewWithPermissionsTestCase):
    """Test Process autocomplete view."""

    def test_get_http_200_ok_for_authenticated(self):
        """Authenticated users can access autocomplete."""
        self.client.force_login(self.member)
        response = self.client.get(reverse("processes:process-autocomplete"))
        self.assertEqual(200, response.status_code)
