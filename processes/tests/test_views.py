"""View tests for the processes module.

Comprehensive tests for all CRUD views following BRIT testing patterns.
"""

import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape

from bibliography.models import Author, Source
from materials.models import Material
from utils.properties.models import Unit
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase

from ..forms import PROCESS_SECTIONS
from ..models import (
    Process,
    ProcessCategory,
    ProcessInfoResource,
    ProcessMaterial,
    ProcessOperatingParameter,
    ProcessSource,
)


class ProcessMaintenanceViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="process-maintainer")
        cls.other = get_user_model().objects.create_user(username="other-maintainer")
        permissions = Permission.objects.filter(
            content_type__app_label="processes",
            codename__in=["add_process", "change_process"],
        )
        cls.owner.user_permissions.add(*permissions)
        cls.other.user_permissions.add(*permissions)
        cls.process = Process.objects.create(
            owner=cls.owner,
            name="Pilot",
            description="Keep this description",
            mechanism="Keep this mechanism",
        )
        cls.material = Material.objects.create(
            name="Workshop substrate", owner=cls.owner, publication_status="published"
        )
        cls.input = ProcessMaterial.objects.create(
            process=cls.process, material=cls.material, role="input"
        )
        cls.output = ProcessMaterial.objects.create(
            process=cls.process, material=cls.material, role="output"
        )
        cls.parameter = ProcessOperatingParameter.objects.create(
            process=cls.process, parameter="temperature", nominal_value=40
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def section_url(self, section="overview", process=None):
        return f"{reverse('processes:process-update', kwargs={'pk': (process or self.process).pk})}?section={section}"

    def material_data(self, link=None):
        link = link or self.input
        return {
            "process_materials-TOTAL_FORMS": "1",
            "process_materials-INITIAL_FORMS": "1",
            "process_materials-0-id": str(link.pk),
            "process_materials-0-material": str(self.material.pk),
            "process_materials-0-notes": "Updated input only",
        }

    def test_create_shows_only_three_fields_without_formsets(self):
        response = self.client.get(reverse("processes:process-create"))
        self.assertEqual(
            set(response.context["form"].fields),
            {"name", "categories", "short_description"},
        )
        self.assertNotContains(response, "TOTAL_FORMS")
        self.assertContains(response, "Save private draft")

    def test_create_with_name_only_saves_private_owned_draft(self):
        response = self.client.post(
            reverse("processes:process-create"), {"name": "New workshop process"}
        )
        self.assertEqual(response.status_code, 302)
        process = Process.objects.get(name="New workshop process")
        self.assertEqual(process.owner, self.owner)
        self.assertEqual(process.publication_status, "private")
        self.assertRedirects(
            response,
            f"{process.get_absolute_url()}?mode=edit",
            fetch_redirect_response=False,
        )

    def test_edit_workspace_has_empty_section_actions_but_no_loaded_forms(self):
        response = self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        self.assertContains(response, "data-workspace")
        self.assertContains(response, "Inputs")
        self.assertContains(response, "References and contributors")
        self.assertNotContains(response, "TOTAL_FORMS")
        self.assertNotContains(response, 'name="parent"')

    def test_title_has_a_direct_edit_action_and_clear_field_label(self):
        response = self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        self.assertContains(response, "Edit title")
        self.assertContains(response, 'data-workspace-focus="name"')
        response = self.client.get(self.section_url())
        self.assertEqual(response.context["form"].fields["name"].label, "Title")

    def test_title_change_is_persisted_and_returned_for_the_heading(self):
        response = self.client.post(
            self.section_url(),
            {"name": "Renamed process"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["saved"])
        self.assertEqual(response.json()["title"], "Renamed process")
        self.process.refresh_from_db()
        self.assertEqual(self.process.name, "Renamed process")

    def test_image_editor_is_near_the_title_and_separate_from_other_sections(self):
        response = self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        content = response.content.decode()
        self.assertIn('data-workspace-section="image"', content)
        self.assertLess(
            content.index('data-workspace-section="image"'),
            content.index('data-workspace-section="technology"'),
        )
        response = self.client.get(self.section_url("image"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.context["form"].fields),
            {
                "image",
                "image_alt_text",
                "image_caption",
                "image_rights_notice",
            },
        )
        self.assertFalse(response.context["inlines"])
        response = self.client.get(self.section_url("resources"))
        self.assertEqual(
            set(response.context["form"].fields), {"supplementary_document"}
        )
        self.assertNotContains(response, 'name="image"')
        self.assertNotContains(response, 'name="process_sources-TOTAL_FORMS"')

    def test_image_metadata_can_be_saved_without_submitting_other_sections(self):
        response = self.client.post(
            self.section_url("image"),
            {
                "image_alt_text": "Process reactor",
                "image_caption": "Pilot plant",
                "image_rights_notice": "Contributor",
                "name": "Must not change the title",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.process.refresh_from_db()
        self.assertEqual(self.process.image_caption, "Pilot plant")
        self.assertEqual(self.process.name, "Pilot")
        self.assertEqual(self.process.process_materials.count(), 2)

    def test_bibliography_source_labels_in_both_modes(self):
        source = Source.objects.create(
            owner=self.owner,
            title="Full descriptive publication title",
            abbreviation="Example2020",
            publication_status="published",
        )
        self.process.sources.add(source)
        response = self.client.get(self.process.get_absolute_url())
        self.assertContains(
            response,
            f'<a href="{reverse("source-detail-modal", kwargs={"pk": source.pk})}" '
            'class="modal-link text-break">'
            f'<strong class="d-block">{source.title}</strong>'
            '<span class="small text-muted">Example2020</span></a>',
            html=True,
        )
        response = self.client.get(self.process.get_absolute_url() + "?mode=edit")
        self.assertContains(response, ">Example2020</a>")
        response = self.client.get(self.section_url("references"))
        self.assertContains(response, ">Example2020</option>")
        self.assertContains(response, "label=abbreviation")
        response = self.client.get(
            reverse("source-autocomplete"),
            {"q": "Example2020", "label": "abbreviation"},
        )
        result = next(
            item for item in response.json()["results"] if item["id"] == source.pk
        )
        self.assertEqual(result["label"], "Example2020")

    def test_supporting_files_link_through_brit_in_details_and_editors(self):
        self.process.supplementary_document = (
            "processes/supplementary_documents/report.pdf"
        )
        self.process.save()
        resource = ProcessInfoResource.objects.create(
            process=self.process,
            title="Supporting report",
            resource_type="document",
            document="processes/info_resources/report.pdf",
        )
        document_url = reverse(
            "processes:process-supplementary-document", kwargs={"pk": self.process.pk}
        )
        resource_url = reverse(
            "processes:process-info-resource-document",
            kwargs={"pk": self.process.pk, "resource_pk": resource.pk},
        )
        for url in (
            self.process.get_absolute_url(),
            f"{self.process.get_absolute_url()}?mode=edit",
            self.section_url("resources"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, f'href="{document_url}"')
                self.assertContains(response, f'href="{resource_url}"')
                self.assertNotContains(response, 'href="/media/processes/')

    def test_overview_save_does_not_change_other_sections_or_publication(self):
        response = self.client.post(
            self.section_url(),
            {
                "name": "Updated pilot",
                "short_description": "Short summary",
                "publication_status": "published",
                "description": "Must not be accepted",
                "operating_parameters-TOTAL_FORMS": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.process.refresh_from_db()
        self.assertEqual(self.process.name, "Updated pilot")
        self.assertEqual(self.process.description, "Keep this description")
        self.assertEqual(self.process.mechanism, "Keep this mechanism")
        self.assertEqual(self.process.publication_status, "private")
        self.assertTrue(
            ProcessOperatingParameter.objects.filter(pk=self.parameter.pk).exists()
        )
        self.assertEqual(self.process.process_materials.count(), 2)

    def test_detail_view_shows_one_sided_parameter_bounds(self):
        ProcessOperatingParameter.objects.create(
            process=self.process, parameter="pressure", value_min=Decimal("2")
        )
        ProcessOperatingParameter.objects.create(
            process=self.process, parameter="yield", value_max=Decimal("39")
        )
        response = self.client.get(self.process.get_absolute_url())
        self.assertContains(response, "at least 2")
        self.assertContains(response, "at most 39")
        self.assertNotContains(response, "2 – -")
        self.assertNotContains(response, "- – 39")

    def test_edit_workspace_summary_shows_one_sided_parameter_bounds(self):
        ProcessOperatingParameter.objects.create(
            process=self.process, parameter="pressure", value_min=Decimal("0")
        )
        ProcessOperatingParameter.objects.create(
            process=self.process, parameter="yield", value_max=Decimal("39")
        )
        response = self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        self.assertContains(response, "at least 0")
        self.assertContains(response, "at most 39")
        self.assertNotContains(response, "0 – —")
        self.assertNotContains(response, "— – 39")

    def test_edit_workspace_summary_shows_single_bound_with_nominal(self):
        ProcessOperatingParameter.objects.create(
            process=self.process,
            parameter="pressure",
            nominal_value=Decimal("5"),
            value_min=Decimal("1"),
        )
        response = self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        self.assertContains(response, "(at least 1)")
        self.assertNotContains(response, "(range:")

    def test_edit_workspace_summary_keeps_range_label_for_two_sided_bounds(self):
        ProcessOperatingParameter.objects.create(
            process=self.process,
            parameter="pressure",
            nominal_value=Decimal("5"),
            value_min=Decimal("1"),
            value_max=Decimal("9"),
        )
        response = self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        self.assertContains(response, "(range: 1 – 9)")

    def test_detail_view_shows_material_stage_stream_and_optional_badges(self):
        self.input.stage = "Pretreatment hall"
        self.input.stream_label = "Feed stream A"
        self.input.optional = True
        self.input.save()
        self.output.stage = "Product recovery"
        self.output.stream_label = "Product stream B"
        self.output.optional = True
        self.output.save()
        for url in (
            self.process.get_absolute_url(),
            f"{self.process.get_absolute_url()}?mode=edit",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "Stage: Pretreatment hall")
                self.assertContains(response, "Stream: Feed stream A")
                self.assertContains(response, "Stage: Product recovery")
                self.assertContains(response, "Stream: Product stream B")
                self.assertContains(
                    response, '<span class="badge text-bg-light">Optional</span>'
                )

    def test_detail_view_omits_blank_material_metadata(self):
        response = self.client.get(self.process.get_absolute_url())
        self.assertNotContains(response, "Stage:")
        self.assertNotContains(response, "Stream:")
        self.assertNotContains(response, ">Optional</span>")

    def test_detail_view_shows_range_label_for_nominal_with_two_sided_bounds(self):
        ProcessOperatingParameter.objects.create(
            process=self.process,
            parameter="pressure",
            nominal_value=Decimal("5"),
            value_min=Decimal("1"),
            value_max=Decimal("9"),
        )
        ProcessOperatingParameter.objects.create(
            process=self.process,
            parameter="yield",
            nominal_value=Decimal("50"),
            value_min=Decimal("40"),
            value_max=Decimal("60"),
        )
        response = self.client.get(self.process.get_absolute_url())
        self.assertContains(response, "(range: 1 – 9)")
        self.assertContains(response, "(range: 40 – 60)")

    def test_detail_view_shows_one_sided_bounds_with_nominal(self):
        ProcessOperatingParameter.objects.create(
            process=self.process,
            parameter="pressure",
            nominal_value=Decimal("5"),
            value_min=Decimal("0"),
        )
        ProcessOperatingParameter.objects.create(
            process=self.process,
            parameter="yield",
            nominal_value=Decimal("50"),
            value_max=Decimal("60"),
        )
        response = self.client.get(self.process.get_absolute_url())
        self.assertContains(response, "(at least 0)")
        self.assertContains(response, "(at most 60)")
        self.assertNotContains(response, "(range:")

    def test_detail_view_range_only_parameters_render_once_without_range_label(self):
        ProcessOperatingParameter.objects.create(
            process=self.process,
            parameter="pressure",
            value_min=Decimal("1"),
            value_max=Decimal("9"),
        )
        response = self.client.get(self.process.get_absolute_url())
        self.assertContains(response, "1 – 9", count=1)
        self.assertNotContains(response, "(range:")

    def test_detail_descriptive_fields_keep_single_line_breaks_and_paragraphs(self):
        self.process.description = "First line\nSecond line\n\nNew paragraph"
        self.process.process_technology = "First step\nSecond step\n\nNew stage"
        self.process.save()
        response = self.client.get(self.process.get_absolute_url())
        self.assertContains(response, "<p>First line<br>Second line</p>", html=True)
        self.assertContains(response, "<p>New paragraph</p>", html=True)
        self.assertContains(response, "<p>First step<br>Second step</p>", html=True)
        self.assertContains(response, "<p>New stage</p>", html=True)

    def test_input_editor_does_not_render_outputs_or_parameters(self):
        response = self.client.get(self.section_url("inputs"))
        self.assertContains(response, "Workshop substrate")
        self.assertNotContains(response, "operating_parameters-TOTAL_FORMS")
        self.assertNotContains(response, 'name="name"')
        self.assertEqual(len(response.context["inlines"][0].initial_forms), 1)
        self.assertNotIn("role", response.context["inlines"][0].forms[0].fields)
        self.assertNotIn("order", response.context["inlines"][0].forms[0].fields)

    def test_input_save_preserves_outputs_and_ignores_forged_role(self):
        data = self.material_data()
        data["process_materials-0-role"] = "output"
        response = self.client.post(self.section_url("inputs"), data)
        self.assertEqual(response.status_code, 302)
        self.input.refresh_from_db()
        self.output.refresh_from_db()
        self.assertEqual(self.input.notes, "Updated input only")
        self.assertEqual(self.input.role, "input")
        self.assertEqual(self.output.notes, "")

    def test_input_row_id_must_belong_to_current_section(self):
        response = self.client.post(
            self.section_url("inputs"), self.material_data(self.output)
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context["inlines"][0].errors
            or response.context["inlines"][0].non_form_errors()
        )
        self.output.refresh_from_db()
        self.assertEqual(self.output.notes, "")

    def test_input_row_id_must_belong_to_current_process(self):
        other_process = Process.objects.create(owner=self.other, name="Other process")
        other_link = ProcessMaterial.objects.create(
            process=other_process, material=self.material, role="input"
        )
        response = self.client.post(
            self.section_url("inputs"), self.material_data(other_link)
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context["inlines"][0].errors
            or response.context["inlines"][0].non_form_errors()
        )
        other_link.refresh_from_db()
        self.assertEqual(other_link.notes, "")

    def test_invalid_quantity_retains_input_and_does_not_save(self):
        data = self.material_data()
        data["process_materials-0-quantity_value"] = "12.5"
        response = self.client.post(self.section_url("inputs"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a unit")
        self.assertContains(response, "Updated input only")
        self.input.refresh_from_db()
        self.assertEqual(self.input.notes, "")

    def test_private_material_reference_is_rejected(self):
        material = Material.objects.create(
            name="Inaccessible material", owner=self.other
        )
        data = self.material_data()
        data["process_materials-0-material"] = material.pk
        response = self.client.post(self.section_url("inputs"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["inlines"][0].errors)
        self.input.refresh_from_db()
        self.assertEqual(self.input.material, self.material)

    def test_unknown_section_is_not_a_full_edit_fallback(self):
        self.assertEqual(self.client.get(self.section_url("unknown")).status_code, 404)
        self.assertEqual(
            self.client.post(self.section_url("unknown"), {"name": "Bad"}).status_code,
            404,
        )

    def test_non_owner_cannot_read_or_save_section(self):
        self.client.force_login(self.other)
        for section in (
            "overview",
            "technology",
            "inputs",
            "outputs",
            "parameters",
            "references",
            "resources",
        ):
            with self.subTest(section=section):
                self.assertEqual(
                    self.client.get(self.section_url(section)).status_code, 403
                )
                self.assertEqual(
                    self.client.post(self.section_url(section), {}).status_code, 403
                )

    def test_owner_cannot_edit_published_process(self):
        self.process.publication_status = "published"
        self.process.save()
        self.assertEqual(
            self.client.post(
                self.section_url("inputs"), self.material_data()
            ).status_code,
            403,
        )
        response = self.client.get(f"{self.process.get_absolute_url()}?mode=edit")
        self.assertNotContains(response, "data-workspace")

    def test_fragment_get_and_save_return_only_requested_section(self):
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        response = self.client.get(self.section_url(), **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["section"], "overview")
        self.assertIn('name="name"', response.json()["html"])
        self.assertNotIn("<html", response.json()["html"])
        response = self.client.post(
            self.section_url(), {"name": "Saved inline"}, **headers
        )
        self.assertTrue(response.json()["saved"])
        self.assertIn("Saved inline", response.json()["html"])
        self.assertNotIn('name="name"', response.json()["html"])

    def test_fragment_validation_error_returns_bound_form(self):
        response = self.client.post(
            self.section_url(),
            {"name": "", "short_description": "Keep typed text"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json()["saved"])
        self.assertIn("Keep typed text", response.json()["html"])
        self.assertIn("This field is required", response.json()["html"])

    def test_reference_widgets_load_only_selected_options(self):
        Material.objects.create(
            name="Unselected published material",
            owner=self.owner,
            publication_status="published",
        )
        response = self.client.get(self.section_url("inputs"))
        self.assertContains(response, "Workshop substrate")
        self.assertNotContains(response, "Unselected published material")
        self.assertContains(
            response, f'data-autocomplete-url="{reverse("material-autocomplete")}"'
        )

    def test_workspace_query_count_does_not_grow_per_material_row(self):
        url = f"{self.process.get_absolute_url()}?mode=edit"
        self.client.get(url)
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(url)
        ProcessMaterial.objects.bulk_create(
            [
                ProcessMaterial(
                    process=self.process,
                    material=self.material,
                    role="input",
                    stream_label=f"Stream {index}",
                )
                for index in range(30)
            ]
        )
        with CaptureQueriesContext(connection) as populated:
            response = self.client.get(url)
        self.assertLessEqual(len(populated), len(baseline) + 1)
        self.assertNotContains(response, "TOTAL_FORMS")

    def test_overview_editor_does_not_query_inline_tables(self):
        with CaptureQueriesContext(connection) as queries:
            self.client.get(self.section_url())
        for table in (
            "processes_processmaterial",
            "processes_processoperatingparameter",
            "processes_processsource",
            "processes_processauthor",
        ):
            self.assertFalse(
                any(f'FROM "{table}"' in query["sql"] for query in queries), table
            )

    def test_inaccessible_category_is_rejected(self):
        category = ProcessCategory.objects.create(
            name="Private category", owner=self.other
        )
        for data in (
            {"categories": [category.pk]},
            {"categories": [999999]},
        ):
            with self.subTest(data=data):
                response = self.client.post(
                    self.section_url(), {"name": "Must not save", **data}
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.process.refresh_from_db()
                self.assertEqual(self.process.name, "Pilot")

    def test_invalid_reference_rolls_back_other_reference_changes(self):
        author = Author.objects.create(first_names="Ada", last_names="Example")
        source = Source.objects.create(title="Not accessible", owner=self.other)
        response = self.client.post(
            self.section_url("references"),
            {
                "process_authors-TOTAL_FORMS": "1",
                "process_authors-INITIAL_FORMS": "0",
                "process_authors-0-author": author.pk,
                "process_sources-TOTAL_FORMS": "1",
                "process_sources-INITIAL_FORMS": "0",
                "process_sources-0-source": source.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.process.process_authors.exists())
        self.assertFalse(self.process.process_sources.exists())

    def test_missing_management_form_does_not_clear_existing_rows(self):
        response = self.client.post(self.section_url("inputs"), {})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["inlines"][0].non_form_errors())
        self.assertTrue(
            self.process.process_materials.filter(pk=self.input.pk).exists()
        )

    def test_new_input_defaults_role_and_order_without_requesting_them(self):
        response = self.client.post(
            self.section_url("inputs"),
            {
                "process_materials-TOTAL_FORMS": "1",
                "process_materials-INITIAL_FORMS": "0",
                "process_materials-0-material": self.material.pk,
                "process_materials-0-notes": "New input",
            },
        )
        self.assertEqual(response.status_code, 302)
        row = self.process.process_materials.get(notes="New input")
        self.assertEqual(row.role, "input")
        self.assertGreater(row.order, 0)


class ProcessDiscoveryRedirectTestCase(TestCase):
    """Legacy dashboard/explorer URLs redirect to the category catalogue."""

    def test_dashboard_redirects_to_category_catalogue(self):
        response = self.client.get(reverse("processes:dashboard"))
        self.assertEqual(302, response.status_code)
        self.assertEqual(
            reverse("processes:processcategory-list"), response["Location"]
        )

    def test_explorer_redirects_to_category_catalogue(self):
        response = self.client.get(reverse("processes:processes-explorer"))
        self.assertEqual(302, response.status_code)
        self.assertEqual(
            reverse("processes:processcategory-list"), response["Location"]
        )

    def test_redirects_preserve_query_params(self):
        for url_name in ("processes:dashboard", "processes:processes-explorer"):
            with self.subTest(url_name=url_name):
                response = self.client.get(
                    reverse(url_name), {"scope": "review", "name": "digestion"}
                )
                self.assertEqual(302, response.status_code)
                location = response["Location"]
                self.assertTrue(
                    location.startswith(f"{reverse('processes:processcategory-list')}?")
                )
                self.assertIn("scope=review", location)
                self.assertIn("name=digestion", location)


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
    add_scope_query_param_to_list_urls = True

    model = ProcessCategory

    dashboard_view = False

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

    def test_detail_shows_related_categories(self):
        """Detail page should show categories connected through shared processes."""
        process = Process.objects.create(
            name="Shared process",
            owner=self.owner_user,
            publication_status="published",
        )
        related_category = ProcessCategory.objects.create(
            name="Related Category",
            owner=self.owner_user,
            publication_status="published",
        )
        process.categories.add(self.published_object, related_category)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Related Category")
        self.assertContains(response, "Shared process")
        self.assertIn(related_category, response.context["related_categories"])

    def test_detail_shows_supplementary_pdf_download(self):
        """Detail page should link the category supplementary PDF when present."""
        self.published_object.supplementary_document = SimpleUploadedFile(
            "category-summary.pdf",
            b"%PDF-1.4 category summary",
            content_type="application/pdf",
        )
        self.published_object.save()

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Download combined process information")
        self.assertContains(
            response, self.published_object.supplementary_document_download_url
        )

    def test_detail_shows_process_gallery_with_images(self):
        """Detail page should display category processes as image cards."""
        process = Process.objects.create(
            name="Illustrated process",
            owner=self.owner_user,
            publication_status="published",
            image=SimpleUploadedFile(
                "process-image.jpg",
                b"image content",
                content_type="image/jpeg",
            ),
            image_alt_text="Process reactor with feedstock",
        )
        process.categories.add(self.published_object)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "row-cols-md-2")
        self.assertContains(response, "card-img-top")
        self.assertContains(response, "process-image")
        self.assertContains(response, 'alt="Process reactor with feedstock"')

    def test_detail_shows_process_image_caption_and_rights_notice(self):
        process = Process.objects.create(
            name="Process with image metadata",
            owner=self.owner_user,
            publication_status="published",
            image=SimpleUploadedFile(
                "process-detail.jpg",
                b"image content",
                content_type="image/jpeg",
            ),
        )
        process.image_alt_text = "Process equipment"
        process.image_caption = "Pilot-scale process equipment."
        process.image_rights_notice = "Image: BRIT team, CC BY 4.0."
        process.save()

        response = self.client.get(
            reverse("processes:process-detail", kwargs={"pk": process.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alt="Process equipment"')
        self.assertContains(response, "Pilot-scale process equipment.")
        self.assertContains(response, "Image: BRIT team, CC BY 4.0.")

    def test_list_shows_categories_without_process_counts(self):
        """The category catalogue lists categories without discovery counters."""
        published_process = Process.objects.create(
            name="Published category process",
            owner=self.owner_user,
            publication_status="published",
        )
        private_process = Process.objects.create(
            name="Private category process",
            owner=self.owner_user,
            publication_status="private",
        )
        published_process.categories.add(self.published_object)
        private_process.categories.add(self.published_object)

        response = self.client.get(reverse(self.view_published_list_name))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published Test Category")
        self.assertNotContains(response, "1 process<")
        self.assertNotContains(response, "2 processes")

    def test_private_detail_shows_private_processes(self):
        """Private category detail should show associated private processes."""
        private_process = Process.objects.create(
            name="Private category process",
            owner=self.owner_user,
            publication_status="private",
        )
        private_process.categories.add(self.unpublished_object)

        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.unpublished_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Processes in This Category")
        self.assertContains(response, "Private category process")


class ProcessListEmptyStateTestCase(ViewWithPermissionsTestCase):
    """Regression tests for issue #150: the shared empty state must not claim
    "No items match your current filters" on an unfiltered empty scope."""

    def test_empty_published_scope_shows_creation_hint_only(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your first process to get started.")
        self.assertNotContains(response, "No items match your current filters.")

    def test_filtered_empty_list_shows_filter_message_and_reset(self):
        Process.objects.create(
            name="Existing process",
            owner=self.staff,
            publication_status="published",
        )
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("processes:process-list"),
            {"scope": "published", "name": "no-match-token"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No processes match your current filters.")
        self.assertContains(response, ">Reset filters</a>")


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
    add_scope_query_param_to_list_urls = True

    model = Process

    dashboard_view = False

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
        - ProcessAuthor: process_authors
        - ProcessSource: process_sources
        - ProcessLink: links
        - ProcessInfoResource: info_resources
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
            # ProcessAuthorInline (related_name='process_authors')
            "process_authors-TOTAL_FORMS": "0",
            "process_authors-INITIAL_FORMS": "0",
            "process_authors-MIN_NUM_FORMS": "0",
            "process_authors-MAX_NUM_FORMS": "1000",
            # ProcessSourceInline (related_name='process_sources')
            "process_sources-TOTAL_FORMS": "0",
            "process_sources-INITIAL_FORMS": "0",
            "process_sources-MIN_NUM_FORMS": "0",
            "process_sources-MAX_NUM_FORMS": "1000",
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
        material = Material.objects.create(
            name="Display Feedstock",
            owner=self.owner_user,
            publication_status="published",
        )
        unit = Unit.objects.create(
            name="kg",
            owner=self.owner_user,
            publication_status="published",
        )
        ProcessMaterial.objects.create(
            process=process,
            material=material,
            role=ProcessMaterial.Role.INPUT,
            quantity_value=Decimal("2.5000"),
            quantity_unit=unit,
            notes="Visible input note",
        )
        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": process.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, process.name)
        self.assertContains(response, "Display Feedstock")
        self.assertContains(response, "2.5 kg")
        self.assertContains(response, "Visible input note")

    def test_delete_confirmation_identifies_process_and_offers_cancel(self):
        process = self.unpublished_object
        process.name = 'BioCH4 & <pilot> "A"'
        process.save()
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_delete_name, kwargs={"pk": process.pk})
        )

        self.assertContains(response, f"Delete “{escape(process.name)}”?")
        self.assertContains(response, "This cannot be undone.")
        self.assertContains(
            response,
            '<button type="button" class="btn btn-secondary" '
            'data-bs-dismiss="modal">Cancel</button>',
            html=True,
        )
        self.assertContains(
            response,
            '<button type="submit" class="btn btn-danger">Delete</button>',
            html=True,
        )
        self.assertTrue(Process.objects.filter(pk=process.pk).exists())

    def test_detail_title_preserves_entered_casing_as_page_heading(self):
        self.published_object.name = "BioCH4: aerobic Composting & <pilot>"
        self.published_object.save()

        for user in (None, self.owner_user):
            with self.subTest(user=user):
                if user:
                    self.client.force_login(user)
                response = self.client.get(
                    reverse(
                        self.view_detail_name, kwargs={"pk": self.published_object.pk}
                    )
                )

                self.assertContains(
                    response,
                    '<h1 class="sdv2-hero-title">'
                    f"{escape(self.published_object.name)}</h1>",
                    count=1,
                    html=True,
                )

    def test_detail_view_follows_pdf_information_order(self):
        process = self.published_object
        process.description = "Detailed process background"
        process.process_technology = "Technology and equipment explanation"
        process.image = "processes/process_images/equipment.png"
        process.image_alt_text = "Extraction equipment"
        process.image_caption = "Equipment caption"
        process.image_rights_notice = "Equipment attribution"
        process.save()
        process.authors.add(
            Author.objects.create(
                last_names="Process contributor",
                institution="Research institute",
                contact_email="author@example.com",
                owner=self.owner_user,
            )
        )
        for role in (ProcessMaterial.Role.INPUT, ProcessMaterial.Role.OUTPUT):
            ProcessMaterial.objects.create(
                process=process,
                material=Material.objects.create(
                    name=f"PDF {role} material", owner=self.owner_user
                ),
                role=role,
                quantity_value=Decimal("0"),
            )
        ProcessOperatingParameter.objects.create(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.TEMPERATURE,
            nominal_value=Decimal("0"),
            notes="Operating conditions note",
        )
        ProcessOperatingParameter.objects.create(
            process=process,
            parameter=ProcessOperatingParameter.Parameter.YIELD,
            value_min=Decimal("0"),
            value_max=Decimal("39"),
            basis="dry basis",
            notes="Depending on feedstock type",
        )
        process.sources.add(
            Source.objects.create(title="PDF bibliography", owner=self.owner_user)
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": process.pk})
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        ordered_content = [
            '<h1 class="sdv2-hero-title">',
            "Process contributor",
            process.short_description,
            'alt="Extraction equipment"',
            "Equipment caption",
            "Equipment attribution",
            process.mechanism,
            "Temperature",
            "Operating conditions note",
            ">Yield</dt>",
            "0 – 39",
            "dry basis",
            "Depending on feedstock type",
            "PDF input material",
            "PDF output material",
            "Detailed process background",
            ">Process Technology</h2>",
            "Technology and equipment explanation",
            ">Bibliography</h2>",
            "PDF bibliography",
        ]
        for text in ordered_content:
            self.assertContains(response, text)
        positions = [content.index(text) for text in ordered_content]
        self.assertEqual(positions, sorted(positions))
        hero = content.split('<header class="sdv2-hero ', 1)[1].split("</header>", 1)[0]
        self.assertIn("sdv2-hero-with-media", hero)
        self.assertIn('alt="Extraction equipment"', hero)
        self.assertIn("Equipment caption", hero)
        self.assertIn("Equipment attribution", hero)
        self.assertIn('fetchpriority="high"', hero)
        self.assertNotIn('loading="lazy"', hero)
        self.assertContains(response, 'alt="Extraction equipment"', count=1)
        self.assertContains(response, "Research institute")
        self.assertContains(response, 'href="mailto:author@example.com"')
        self.assertRegex(content, r"Temperature:</span>\s+0\s")
        self.assertContains(response, '<span class="text-muted ms-1">0</span>', count=2)
        self.assertEqual(
            [anchor["id"] for anchor in response.context["section_anchors"]],
            ["facts", "description", "technology", "bibliography"],
        )
        for anchor in response.context["section_anchors"]:
            self.assertContains(response, f'href="#{anchor["id"]}"')
            self.assertContains(response, f'id="{anchor["id"]}"')

    def test_detail_view_shows_image_without_technology_text(self):
        self.published_object.image = "processes/process_images/equipment.png"
        self.published_object.save()
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertNotContains(response, ">Process Technology</h2>")
        self.assertNotContains(response, 'href="#technology"')
        self.assertContains(response, "sdv2-hero-with-media")
        self.assertContains(response, 'class="sdv2-hero-media"', count=1)
        self.assertContains(response, "equipment.png")
        self.assertContains(response, f'alt="{self.published_object.name}"')

    def test_detail_view_omits_empty_sections(self):
        self.published_object.mechanism = ""
        self.published_object.save()
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertContains(response, "sdv2-hero-no-media")
        self.assertNotContains(response, 'class="sdv2-hero-media"')
        self.assertEqual(response.context["section_anchors"], [])
        for section in ("facts", "description", "technology", "bibliography"):
            self.assertNotContains(response, f'id="{section}"')
        self.assertNotContains(response, "Download supplementary PDF")

    def test_detail_view_hides_additional_resources_without_links(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Additional Resources")

    def test_detail_view_shows_pdf_download_button(self):
        self.published_object.supplementary_document = SimpleUploadedFile(
            "process-details.pdf",
            b"%PDF-1.4\n",
            content_type="application/pdf",
        )
        self.published_object.save()
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Download supplementary PDF")
        self.assertContains(
            response, self.published_object.supplementary_document_download_url
        )
        self.assertNotContains(
            response, f'href="{self.published_object.supplementary_document.url}"'
        )

    def test_detail_view_does_not_show_additional_resources_for_info_resource(self):
        ProcessInfoResource.objects.create(
            process=self.published_object,
            title="Process flow chart",
            resource_type=ProcessInfoResource.ResourceType.EXTERNAL,
            url="https://example.com/process-flow-chart.pdf",
        )
        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Additional Resources")
        self.assertContains(response, "Information Resources")
        self.assertContains(response, "Process flow chart")

    def test_detail_view_uses_sdv2_layout(self):
        """Process detail renders the sdv2 detail-page layout like samples."""
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('class="sdv2"', content)
        self.assertIn("sdv2-hero", content)
        self.assertIn("sdv2-hero-title", content)
        self.assertIn("sdv2-rail", content)
        self.assertIn("sample_detail_v2.min.css", content)
        self.assertNotIn("detail-layout-card", content)

    def test_detail_view_hides_action_rail_for_anonymous(self):
        """Anonymous readers get the minimalist layout without the action rail."""
        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "sdv2-rail")

    def test_review_detail_view_does_not_link_back_to_itself(self):
        """On the review page the rail must not offer a link back to itself."""
        declined_process = self.model.objects.create(
            name="Declined test process",
            owner=self.owner_user,
            publication_status="declined",
        )
        self.client.force_login(self.owner_user)
        review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(self.model).id,
                "object_id": declined_process.pk,
            },
        )

        response = self.client.get(review_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Review feedback")
        self.assertNotContains(response, f'href="{review_url}')

    def test_detail_view_section_headings_are_emphasized(self):
        self.published_object.description = "Visible description"
        self.published_object.process_technology = "Visible process technology"
        self.published_object.save()
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for heading in ("Description", "Process Technology"):
            self.assertIn(
                f'<h2 class="sdv2-section-title">{heading}</h2>',
                content,
            )

    def test_detail_view_links_bibliography_references_to_modal(self):
        source = Source.objects.create(
            title="Reference <Title> & methods",
            citation_key="Ref01",
            year=2024,
            owner=self.owner_user,
            publication_status="published",
        )
        self.published_object.sources.add(source)
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("source-detail-modal", kwargs={"pk": source.pk})}" '
            'class="modal-link text-break">'
            f'<strong class="d-block">{escape(source.title)}</strong>'
            '<span class="small text-muted">Ref01</span></a>',
            html=True,
        )

    def test_bibliography_citations_handle_missing_metadata(self):
        self.client.force_login(self.owner_user)
        for title, year, expected_body in (
            (
                "Undated reference",
                None,
                '<strong class="d-block">Undated reference</strong>'
                '<span class="small text-muted">LegacyRef</span>',
            ),
            (
                "",
                2020,
                '<strong class="d-block">LegacyRef</strong>',
            ),
            ("", None, '<strong class="d-block">LegacyRef</strong>'),
        ):
            with self.subTest(title=title, year=year):
                source = Source.objects.create(
                    title=title,
                    year=year,
                    citation_key="LegacyRef",
                    owner=self.owner_user,
                    publication_status="published",
                )
                self.published_object.sources.set([source])

                response = self.client.get(
                    reverse(
                        self.view_detail_name, kwargs={"pk": self.published_object.pk}
                    )
                )

                self.assertContains(
                    response,
                    f'<a href="{reverse("source-detail-modal", kwargs={"pk": source.pk})}" '
                    f'class="modal-link text-break">{expected_body}</a>',
                    html=True,
                )

    def test_detail_view_private_process_as_superuser_without_staff_flag(self):
        superuser = self.owner_user.__class__.objects.create_user(
            username="superuser-no-staff",
            is_superuser=True,
            is_staff=False,
        )
        self.client.force_login(superuser)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.unpublished_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.unpublished_object.name)

    def test_detail_view_sorts_bibliography_by_workspace_order(self):
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
        self.published_object.sources.add(zebra_source, alpha_source)
        self.published_object.process_sources.filter(source=zebra_source).update(
            order=1
        )
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(self.view_detail_name, kwargs={"pk": self.published_object.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bibliography")
        self.assertNotContains(response, "<ol>")
        self.assertContains(response, "list-unstyled")
        self.assertLess(
            response.content.decode().index("Alpha"),
            response.content.decode().index("Zebra"),
        )

    def test_modal_delete_ignores_detail_next_url(self):
        """Deleting from the detail modal must not redirect to the deleted object."""
        process = Process.objects.create(
            name="Detail modal delete target",
            owner=self.owner_user,
            publication_status="private",
        )
        detail_url = reverse(self.view_detail_name, kwargs={"pk": process.pk})
        delete_url = (
            f"{reverse(self.view_delete_name, kwargs={'pk': process.pk})}"
            f"?next={detail_url}"
        )

        self.client.force_login(self.owner_user)
        response = self.client.post(delete_url, {"next": detail_url})

        self.assertRedirects(
            response,
            f"{reverse(self.view_private_list_name)}?scope=private",
            fetch_redirect_response=False,
        )
        self.assertFalse(Process.objects.filter(pk=process.pk).exists())

    def get_update_success_url(self, pk):
        return f"{reverse(self.view_detail_name, kwargs={'pk': pk})}?mode=edit"

    def test_detail_view_unpublished_as_owner(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_detail_url(self.unpublished_object.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, self.get_update_success_url(self.unpublished_object.pk)
        )
        self.assertContains(response, self.get_delete_url(self.unpublished_object.pk))

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
            f"{reverse(self.view_update_name, kwargs={'pk': self.unpublished_object.pk})}?section=inputs"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="workspace-section-inputs-form"')
        self.assertContains(response, 'name="process_materials-TOTAL_FORMS"')
        self.assertContains(response, 'name="process_materials-0-material"')
        self.assertContains(response, "Existing Material")
        self.assertNotContains(response, 'name="operating_parameters-TOTAL_FORMS"')

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
            f"{reverse(self.view_update_name, kwargs={'pk': self.unpublished_object.pk})}?section=inputs",
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
                "process_materials-0-stage": "Updated stage",
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
                "process_authors-TOTAL_FORMS": "0",
                "process_authors-INITIAL_FORMS": "0",
                "process_authors-MIN_NUM_FORMS": "0",
                "process_authors-MAX_NUM_FORMS": "1000",
                "process_sources-TOTAL_FORMS": "0",
                "process_sources-INITIAL_FORMS": "0",
                "process_sources-MIN_NUM_FORMS": "0",
                "process_sources-MAX_NUM_FORMS": "1000",
                "links-TOTAL_FORMS": "0",
                "links-INITIAL_FORMS": "0",
                "links-MIN_NUM_FORMS": "0",
                "links-MAX_NUM_FORMS": "1000",
                "info_resources-TOTAL_FORMS": "0",
                "info_resources-INITIAL_FORMS": "0",
                "info_resources-MIN_NUM_FORMS": "0",
                "info_resources-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertRedirects(
            response,
            self.get_update_success_url(self.unpublished_object.pk),
        )
        self.unpublished_object.refresh_from_db()
        self.assertEqual(
            self.unpublished_object.process_materials.get().stage,
            "Updated stage",
        )

    def test_update_with_private_source_inline_succeeds(self):
        """Saving a process that already has a private source attached must not
        raise an 'invalid choice' validation error on the source inline."""
        private_source = Source.objects.create(
            title="Owner Private Source",
            abbreviation="OPS",
            owner=self.owner_user,
            publication_status="private",
        )
        ps = ProcessSource.objects.create(
            process=self.unpublished_object,
            source=private_source,
            order=0,
        )
        self.client.force_login(self.owner_user)

        response = self.client.post(
            f"{reverse(self.view_update_name, kwargs={'pk': self.unpublished_object.pk})}?section=references",
            {
                "name": self.unpublished_object.name,
                "short_description": self.unpublished_object.short_description,
                "mechanism": self.unpublished_object.mechanism,
                "description": self.unpublished_object.description or "",
                "categories": [self.test_category.pk],
                "process_materials-TOTAL_FORMS": "0",
                "process_materials-INITIAL_FORMS": "0",
                "process_materials-MIN_NUM_FORMS": "0",
                "process_materials-MAX_NUM_FORMS": "1000",
                "operating_parameters-TOTAL_FORMS": "0",
                "operating_parameters-INITIAL_FORMS": "0",
                "operating_parameters-MIN_NUM_FORMS": "0",
                "operating_parameters-MAX_NUM_FORMS": "1000",
                "process_authors-TOTAL_FORMS": "0",
                "process_authors-INITIAL_FORMS": "0",
                "process_authors-MIN_NUM_FORMS": "0",
                "process_authors-MAX_NUM_FORMS": "1000",
                "process_sources-TOTAL_FORMS": "1",
                "process_sources-INITIAL_FORMS": "1",
                "process_sources-MIN_NUM_FORMS": "0",
                "process_sources-MAX_NUM_FORMS": "1000",
                "process_sources-0-source": private_source.pk,
                "process_sources-0-order": "0",
                "process_sources-0-id": ps.pk,
                "process_sources-0-process": self.unpublished_object.pk,
                "links-TOTAL_FORMS": "0",
                "links-INITIAL_FORMS": "0",
                "links-MIN_NUM_FORMS": "0",
                "links-MAX_NUM_FORMS": "1000",
                "info_resources-TOTAL_FORMS": "0",
                "info_resources-INITIAL_FORMS": "0",
                "info_resources-MIN_NUM_FORMS": "0",
                "info_resources-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertRedirects(
            response,
            self.get_update_success_url(self.unpublished_object.pk),
        )
        self.assertTrue(
            ProcessSource.objects.filter(
                process=self.unpublished_object, source=private_source
            ).exists()
        )


class ProcessFilterUrlTestCase(TestCase):
    """Filter URLs must not leak CSRF tokens or stale parameters (issue #153)."""

    def _get_form_html(self, response):
        content = response.content.decode()
        return re.findall(
            r'<form[^>]*method="get"[^>]*>.*?</form>',
            content,
            re.DOTALL | re.IGNORECASE,
        )

    def test_get_filter_form_renders_no_csrf_token(self):
        response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )
        self.assertEqual(response.status_code, 200)
        get_forms = self._get_form_html(response)
        self.assertTrue(get_forms, "Expected a GET filter form on the list page")
        for form_html in get_forms:
            self.assertNotIn("csrfmiddlewaretoken", form_html)

    def test_stale_csrf_param_redirects_to_clean_url(self):
        response = self.client.get(
            reverse("processes:process-list"),
            {
                "scope": "published",
                "csrfmiddlewaretoken": "stale-token",
                "name": "compost",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], "/processes/list/?scope=published&name=compost"
        )

    def test_csrf_only_params_redirect_to_default_filters(self):
        response = self.client.get(
            reverse("processes:process-list"), {"csrfmiddlewaretoken": "stale-token"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/processes/list/?scope=published")

    def test_filter_url_without_csrf_is_not_redirected(self):
        response = self.client.get(
            reverse("processes:process-list"),
            {"scope": "published", "name": "compost"},
        )
        self.assertEqual(response.status_code, 200)


class ProcessAutocompleteViewTestCase(ViewWithPermissionsTestCase):
    """Test Process autocomplete view."""

    def test_get_http_200_ok_for_authenticated(self):
        """Authenticated users can access autocomplete."""
        self.client.force_login(self.member)
        response = self.client.get(reverse("processes:process-autocomplete"))
        self.assertEqual(200, response.status_code)


class ProcessDetailRelatedVisibilityTestCase(ViewWithPermissionsTestCase):
    """Related objects on the process detail page must follow the read policy.

    Private or in-review objects owned by someone else must not leak their
    names (or produce dead links) on a published process page.
    """

    member_permissions = ["add_process", "change_process"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.published = Process.objects.create(
            name="Public Process",
            owner=cls.owner,
            publication_status="published",
        )
        cls.secret_category = ProcessCategory.objects.create(
            name="Secret Category", owner=cls.outsider
        )
        cls.published.categories.add(cls.secret_category)
        cls.secret_material = Material.objects.create(
            name="Secret Material", owner=cls.outsider
        )
        ProcessMaterial.objects.create(
            process=cls.published,
            material=cls.secret_material,
            role=ProcessMaterial.Role.INPUT,
        )
        cls.secret_source = Source.objects.create(
            title="Secret Source", owner=cls.outsider
        )
        ProcessSource.objects.create(process=cls.published, source=cls.secret_source)
        cls.secret_author = Author.objects.create(
            last_names="Secretauthor",
            contact_email="secret-author@example.com",
            owner=cls.outsider,
        )
        cls.published.authors.add(cls.secret_author)

        cls.detail_url = reverse(
            "processes:process-detail", kwargs={"pk": cls.published.pk}
        )

    def test_anonymous_does_not_see_private_category(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Secret Category")

    def test_anonymous_does_not_see_private_material(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Secret Material")

    def test_anonymous_does_not_see_private_source(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Secret Source")

    def test_anonymous_does_not_see_private_author(self):
        """Private contributor names and contact emails must not leak."""
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Secretauthor")
        self.assertNotContains(response, "secret-author@example.com")

    def test_non_owner_member_does_not_see_private_related(self):
        self.client.force_login(self.member)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Secret Category")
        self.assertNotContains(response, "Secret Material")
        self.assertNotContains(response, "Secret Source")
        self.assertNotContains(response, "Secretauthor")

    def test_owner_sees_own_private_category(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Secret Category")

    def test_detail_page_has_no_hierarchy_sections(self):
        visible_category = ProcessCategory.objects.create(
            name="Visible Category",
            owner=self.owner,
            publication_status="published",
        )
        self.published.categories.add(visible_category)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        for label in ("Parent process", "Sibling processes", "Process variants"):
            self.assertNotContains(response, label)
        self.assertNotContains(response, "sdv2-related")
        self.assertContains(response, "Visible Category")

    def test_edit_workspace_has_no_parent_field(self):
        draft = Process.objects.create(name="Editable Draft", owner=self.owner)
        self.client.force_login(self.owner)
        response = self.client.get(f"{draft.get_absolute_url()}?mode=edit")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="parent"')
        self.assertNotContains(response, "Parent process")

    def test_list_page_has_no_parent_metadata(self):
        response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )
        self.assertNotContains(response, "Variant of")
        self.assertNotContains(response, "parent process")

    def test_review_page_has_no_hierarchy_labels(self):
        declined = Process.objects.create(
            name="Declined Process",
            owner=self.owner,
            publication_status="declined",
        )
        self.client.force_login(self.owner)
        review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Process).pk,
                "object_id": declined.pk,
            },
        )
        response = self.client.get(review_url)
        self.assertEqual(response.status_code, 200)
        for label in ("Parent process", "Sibling processes", "Process variants"):
            self.assertNotContains(response, label)


class ProcessDetailReviewPanelTestCase(ViewWithPermissionsTestCase):
    """The detail review panel must not be exposable to arbitrary readers."""

    member_permissions = ["add_process", "change_process"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.published = Process.objects.create(
            name="Reviewed Process",
            owner=cls.owner,
            publication_status="published",
        )
        cls.url = reverse("processes:process-detail", kwargs={"pk": cls.published.pk})

    def test_anonymous_cannot_open_review_panel(self):
        response = self.client.get(self.url, {"review": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["show_review_panel"])

    def test_unrelated_member_cannot_open_review_panel(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url, {"review": "1"})
        self.assertFalse(response.context["show_review_panel"])

    def test_owner_can_open_review_panel(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url, {"review": "1"})
        self.assertTrue(response.context["show_review_panel"])

    def test_staff_can_open_review_panel(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url, {"review": "1"})
        self.assertTrue(response.context["show_review_panel"])

    def test_no_param_no_panel(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertFalse(response.context["show_review_panel"])


class ProcessCategoryDetailVisibilityTestCase(ViewWithPermissionsTestCase):
    """Processes listed on a category detail page must follow the read policy."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.private_category = ProcessCategory.objects.create(
            name="Private Category", owner=cls.owner
        )
        cls.outsider_private_process = Process.objects.create(
            name="Outsider Secret Process", owner=cls.outsider
        )
        cls.outsider_private_process.categories.add(cls.private_category)
        cls.own_private_process = Process.objects.create(
            name="Own Secret Process", owner=cls.owner
        )
        cls.own_private_process.categories.add(cls.private_category)
        cls.category_url = reverse(
            "processes:processcategory-detail", kwargs={"pk": cls.private_category.pk}
        )

    def test_owner_does_not_see_other_users_private_processes(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.category_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Outsider Secret Process")
        self.assertContains(response, "Own Secret Process")

    def test_published_category_shows_own_private_process_to_owner(self):
        published_category = ProcessCategory.objects.create(
            name="Published Category",
            owner=self.owner,
            publication_status="published",
        )
        self.own_private_process.categories.add(published_category)
        url = reverse(
            "processes:processcategory-detail", kwargs={"pk": published_category.pk}
        )
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "Own Secret Process")

        other = get_user_model().objects.create(username="unrelated")
        self.client.force_login(other)
        response = self.client.get(url)
        self.assertNotContains(response, "Own Secret Process")


class ProcessCategoryReviewDetailTestCase(ViewWithPermissionsTestCase):
    """A category review page must list the processes in that category."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.moderator = get_user_model().objects.create_user(
            username="category_moderator"
        )
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="processes",
                codename="can_moderate_processcategory",
            )
        )
        cls.review_category = ProcessCategory.objects.create(
            name="Pulping",
            owner=cls.outsider,
            publication_status="review",
        )
        cls.review_process = Process.objects.create(
            name="Pulping Process",
            owner=cls.outsider,
            publication_status="published",
        )
        cls.review_process.categories.add(cls.review_category)
        cls.review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(
                    ProcessCategory
                ).pk,
                "object_id": cls.review_category.pk,
            },
        )

    def test_review_detail_shows_processes_in_category(self):
        self.client.force_login(self.moderator)
        response = self.client.get(self.review_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pulping Process")
        self.assertNotContains(response, "No processes in this category yet.")


class ProcessFilterViewQuerysetTests(TestCase):
    def test_filter_views_share_the_queryset_mixin(self):
        """The three process filter views share one queryset so related-object
        prefetching cannot drift between scopes."""
        from processes.views import (
            ProcessFilterViewMixin,
            ProcessPrivateFilterView,
            ProcessPublishedFilterView,
            ProcessReviewFilterView,
        )

        for view_class in (
            ProcessPublishedFilterView,
            ProcessPrivateFilterView,
            ProcessReviewFilterView,
        ):
            with self.subTest(view_class=view_class.__name__):
                self.assertTrue(issubclass(view_class, ProcessFilterViewMixin))


class ProcessWorkshopJourneyViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.participant = user_model.objects.create_user(
            username="workshop-participant"
        )
        cls.participant.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="processes",
                codename__in=["add_process", "change_process"],
            )
        )
        cls.participant.groups.add(Group.objects.get_or_create(name="process-team")[0])
        cls.observer = user_model.objects.create_user(username="workshop-observer")
        cls.moderator = user_model.objects.create_user(
            username="workshop-moderator", is_staff=True
        )
        cls.feed_material = Material.objects.create(
            name="Workshop feedstock",
            owner=cls.participant,
            publication_status="published",
        )
        cls.product_material = Material.objects.create(
            name="Workshop product",
            owner=cls.participant,
            publication_status="published",
        )

    def setUp(self):
        self.client.force_login(self.participant)

    def create_draft(self, name="Workshop draft process"):
        return Process.objects.create(
            owner=self.participant,
            name=name,
            short_description="Draft recorded during the workshop",
        )

    @staticmethod
    def section_url(process, section):
        update_url = reverse("processes:process-update", kwargs={"pk": process.pk})
        return f"{update_url}?section={section}"

    @staticmethod
    def material_payload(material):
        return {
            "process_materials-TOTAL_FORMS": "1",
            "process_materials-INITIAL_FORMS": "0",
            "process_materials-0-material": str(material.pk),
            "process_materials-0-quantity_value": "",
            "process_materials-0-quantity_unit": "",
        }

    def test_process_list_shows_prominent_add_process_action(self):
        response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add process")
        self.assertContains(response, f'href="{reverse("processes:process-create")}"')
        self.assertNotContains(response, 'id="options-tab"')
        self.assertNotContains(response, 'id="options-pane"')

    def test_add_process_hidden_for_anonymous_and_users_without_permission(self):
        url = reverse("processes:process-list")
        create_url = reverse("processes:process-create")

        self.client.logout()
        response = self.client.get(url, {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Add process")
        self.assertNotContains(response, create_url)

        self.client.force_login(self.observer)
        response = self.client.get(url, {"scope": "published"})
        self.assertNotContains(response, "Add process")
        self.assertNotContains(response, create_url)

    def test_list_heading_matches_scope(self):
        private_response = self.client.get(
            reverse("processes:process-list-owned"), {"scope": "private"}
        )
        self.assertContains(
            private_response, "<strong>My processes</strong>", html=True
        )

        published_response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )
        self.assertContains(published_response, "<strong>Processes</strong>", html=True)
        self.assertNotContains(published_response, "My processes")

        self.client.force_login(self.moderator)
        review_response = self.client.get(
            reverse("processes:process-list-review"), {"scope": "review"}
        )
        self.assertContains(
            review_response, "<strong>Processes in review</strong>", html=True
        )

    def test_detail_nav_shows_compact_discovery_links_for_all_readers(self):
        published = Process.objects.create(
            name="Published workshop process",
            owner=self.moderator,
            publication_status="published",
        )
        url = reverse("processes:process-detail", kwargs={"pk": published.pk})
        catalogue_url = reverse("processes:processcategory-list")

        for user in (self.participant, None):
            with self.subTest(user=user):
                if user is None:
                    self.client.logout()
                else:
                    self.client.force_login(user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'href="{catalogue_url}?scope=published"')
                self.assertContains(response, "Categories")
                self.assertNotContains(response, "processes-explorer")
                self.assertNotContains(response, "Explorer")
                self.assertNotContains(response, "My processes")

    def test_edit_workspace_jump_nav_matches_rendered_sections(self):
        process = self.create_draft()

        response = self.client.get(f"{process.get_absolute_url()}?mode=edit")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sdv2-anchor-nav")
        self.assertContains(response, 'aria-label="Jump to editing section"')
        self.assertContains(response, "sdv2-anchor-chip", count=len(PROCESS_SECTIONS))
        self.assertContains(response, "sdv2-anchor-target", count=len(PROCESS_SECTIONS))
        for key in PROCESS_SECTIONS:
            with self.subTest(section=key):
                self.assertContains(response, f'href="#workspace-section-{key}"')
                self.assertContains(response, f'id="workspace-section-{key}"')
        self.assertNotContains(response, "TOTAL_FORMS")

        reading_response = self.client.get(process.get_absolute_url())
        self.assertNotContains(reading_response, "Jump to editing section")

    def test_material_guidance_renders_in_section_forms_and_fragments(self):
        process = self.create_draft()
        guidance = (
            "Choose an existing material. Quantity and unit are optional; "
            "leave both blank if you are not recording an amount."
        )

        for section, add_label in (("inputs", "Add input"), ("outputs", "Add output")):
            with self.subTest(section=section):
                response = self.client.get(self.section_url(process, section))
                self.assertContains(response, guidance)
                self.assertContains(response, "data-workspace-empty")
                self.assertContains(response, add_label)

                fragment = self.client.get(
                    self.section_url(process, section),
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(fragment.status_code, 200)
                html = fragment.json()["html"]
                self.assertIn(guidance, html)
                self.assertIn("quantity_value", html)
                self.assertIn("quantity_unit", html)

    def test_empty_section_form_has_no_rows_and_add_controls(self):
        process = self.create_draft()

        for section, add_label in (("inputs", "Add input"), ("outputs", "Add output")):
            with self.subTest(section=section):
                response = self.client.get(self.section_url(process, section))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.context["inlines"][0].initial_forms), 0)
                self.assertContains(response, add_label)
                self.assertContains(response, "data-workspace-empty")

    def test_participant_ajax_journey(self):
        create_response = self.client.post(
            reverse("processes:process-create"),
            {
                "name": "Workshop AJAX process",
                "short_description": "Draft recorded during the workshop",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        process = Process.objects.get(name="Workshop AJAX process")
        self.assertEqual(process.owner, self.participant)
        self.assertEqual(process.publication_status, "private")

        ajax = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        response = self.client.post(
            self.section_url(process, "inputs"),
            self.material_payload(self.feed_material),
            **ajax,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["saved"])
        self.assertEqual(payload["section"], "inputs")
        self.assertIn("Workshop feedstock", payload["html"])
        self.assertNotIn("Workshop product", payload["html"])

        response = self.client.post(
            self.section_url(process, "outputs"),
            self.material_payload(self.product_material),
            **ajax,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["saved"])
        self.assertEqual(payload["section"], "outputs")
        self.assertIn("Workshop product", payload["html"])
        self.assertNotIn("Workshop feedstock", payload["html"])

        process.refresh_from_db()
        self.assertEqual(process.owner, self.participant)
        self.assertEqual(process.publication_status, "private")
        input_link = process.process_materials.get(role="input")
        output_link = process.process_materials.get(role="output")
        self.assertEqual(input_link.material, self.feed_material)
        self.assertEqual(output_link.material, self.product_material)
        for link in (input_link, output_link):
            self.assertIsNone(link.quantity_value)
            self.assertIsNone(link.quantity_unit)

        reading_response = self.client.get(process.get_absolute_url())
        self.assertContains(reading_response, "Draft recorded during the workshop")
        self.assertContains(reading_response, "Workshop feedstock")
        self.assertContains(reading_response, "Workshop product")

        owned_response = self.client.get(
            reverse("processes:process-list-owned"), {"scope": "private"}
        )
        self.assertContains(owned_response, "Workshop AJAX process")
        published_response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )
        self.assertNotContains(published_response, "Workshop AJAX process")
        self.assertNotIn(process, published_response.context["object_list"])

    def test_participant_full_page_journey(self):
        create_response = self.client.post(
            reverse("processes:process-create"),
            {
                "name": "Workshop full-page process",
                "short_description": "Draft recorded during the workshop",
            },
        )
        process = Process.objects.get(name="Workshop full-page process")
        self.assertRedirects(
            create_response,
            f"{process.get_absolute_url()}?mode=edit",
            fetch_redirect_response=False,
        )
        self.assertEqual(process.owner, self.participant)
        self.assertEqual(process.publication_status, "private")

        response = self.client.post(
            self.section_url(process, "inputs"),
            self.material_payload(self.feed_material),
        )
        self.assertRedirects(
            response,
            f"{process.get_absolute_url()}?mode=edit",
            fetch_redirect_response=False,
        )
        response = self.client.post(
            self.section_url(process, "outputs"),
            self.material_payload(self.product_material),
        )
        self.assertRedirects(
            response,
            f"{process.get_absolute_url()}?mode=edit",
            fetch_redirect_response=False,
        )

        process.refresh_from_db()
        self.assertEqual(process.owner, self.participant)
        self.assertEqual(process.publication_status, "private")
        self.assertEqual(
            process.short_description, "Draft recorded during the workshop"
        )
        input_link = process.process_materials.get(role="input")
        output_link = process.process_materials.get(role="output")
        self.assertEqual(input_link.material, self.feed_material)
        self.assertEqual(output_link.material, self.product_material)
        for link in (input_link, output_link):
            self.assertIsNone(link.quantity_value)
            self.assertIsNone(link.quantity_unit)

        reading_response = self.client.get(process.get_absolute_url())
        self.assertContains(reading_response, "Workshop full-page process")
        self.assertContains(reading_response, "Draft recorded during the workshop")
        self.assertContains(reading_response, "Workshop feedstock")
        self.assertContains(reading_response, "Workshop product")
        self.assertContains(reading_response, "sdv2-status-private")

        owned_response = self.client.get(
            reverse("processes:process-list-owned"), {"scope": "private"}
        )
        self.assertContains(owned_response, "Workshop full-page process")
        self.assertContains(owned_response, f'href="{process.get_absolute_url()}')
        reopened_response = self.client.get(process.get_absolute_url())
        self.assertEqual(reopened_response.status_code, 200)
        self.assertContains(reopened_response, "Workshop full-page process")

        published_response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )
        self.assertNotContains(published_response, "Workshop full-page process")
        self.assertNotIn(process, published_response.context["object_list"])


class ProcessCategoryOptionsViewTestCase(ViewWithPermissionsTestCase):
    """The options endpoint must answer 200 and respect the read policy."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.published_category = ProcessCategory.objects.create(
            name="Options Published Category",
            owner=cls.outsider,
            publication_status="published",
        )
        cls.private_category = ProcessCategory.objects.create(
            name="Options Private Category", owner=cls.outsider
        )
        cls.archived_category = ProcessCategory.objects.create(
            name="Options Archived Category",
            owner=cls.owner,
            publication_status="archived",
        )
        cls.url = reverse("processes:processcategory-options")

    def test_options_endpoint_does_not_500(self):
        """Missing permission_required used to raise ImproperlyConfigured."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_options_exclude_foreign_private_and_archived(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Options Published Category")
        self.assertNotContains(response, "Options Private Category")
        self.assertNotContains(response, "Options Archived Category")

    def test_options_show_own_private_to_owner(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertContains(response, "Options Private Category")

    def test_options_exclude_own_archived(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Options Archived Category")


class ProcessListBulkAccessTestCase(ViewWithPermissionsTestCase):
    """Bulk manage-access controls on the private process list."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.process = Process.objects.create(name="Bulk target", owner=cls.owner)

    def test_private_list_renders_bulk_toolbar_and_checkboxes(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("processes:process-list-owned"), {"scope": "private"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="bulk-access-form"')
        self.assertContains(response, 'name="items"')

    def test_rows_are_keyboard_navigable(self):
        Process.objects.create(
            name="Keyboard target",
            owner=self.owner,
            publication_status="published",
        )
        response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="link"')
        self.assertContains(response, 'tabindex="0"')

    def test_published_list_hides_bulk_controls(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )
        self.assertNotContains(response, 'id="bulk-access-form"')
        self.assertNotContains(response, 'name="items"')


class ProcessCategoryModalDeleteRedirectTestCase(ViewWithPermissionsTestCase):
    """Deleting a category from its own detail page must not redirect back to it."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = ProcessCategory.objects.create(
            name="Doomed Category", owner=cls.owner
        )

    def test_delete_with_next_to_own_detail_redirects_to_scoped_list(self):
        self.client.force_login(self.owner)
        detail_url = self.category.get_absolute_url()
        delete_url = f"{self.category.modal_delete_url}?next={detail_url}"
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            response["Location"].startswith(detail_url),
            "delete redirect must not point back at the deleted object",
        )
        self.assertEqual(
            response["Location"],
            f"{reverse('processes:processcategory-list-owned')}?scope=private",
        )

    def test_delete_with_absolute_next_to_own_detail_redirects_to_scoped_list(self):
        self.client.force_login(self.owner)
        detail_url = f"http://testserver{self.category.get_absolute_url()}?tab=info"
        response = self.client.post(
            self.category.modal_delete_url, {"next": detail_url}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"{reverse('processes:processcategory-list-owned')}?scope=private",
        )

    def test_delete_with_unrelated_next_redirects_there(self):
        other = ProcessCategory.objects.create(name="Survivor", owner=self.owner)
        self.client.force_login(self.owner)
        next_url = f"http://testserver{other.get_absolute_url()}"
        response = self.client.post(self.category.modal_delete_url, {"next": next_url})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)


class ListRowNavigationTestCase(ViewWithPermissionsTestCase):
    """Clickable list rows must not navigate when a nested control is used."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.process = Process.objects.create(name="Row process", owner=cls.owner)
        cls.category = ProcessCategory.objects.create(
            name="Row category", owner=cls.owner
        )

    def _row_handlers(self, response):
        html = response.content.decode()
        return re.findall(r'<tr tabindex="0"[^>]*>', html)

    def test_rows_ignore_clicks_and_keys_from_nested_controls(self):
        self.client.force_login(self.owner)
        for url in (
            reverse("processes:process-list-owned"),
            reverse("processes:processcategory-list-owned"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url, {"scope": "private"})
                self.assertEqual(response.status_code, 200)
                rows = self._row_handlers(response)
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertIn(
                    "onclick=\"if(!event.target.closest('a,button,input,select,"
                    "textarea,label,form,.dropdown-menu'))",
                    row,
                )
                self.assertIn('onkeydown="if(event.target===this&&', row)
                self.assertNotIn('onclick="window.location', row)


class ProcessDashboardRecentOrderingTestCase(TestCase):
    def test_recent_processes_are_most_recently_modified_first(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from django.utils import timezone

        from ..views import ProcessDashboardView

        owner = get_user_model().objects.create(username="dash-owner")
        older = Process.objects.create(
            name="AAA older", owner=owner, publication_status="published"
        )
        newer = Process.objects.create(
            name="ZZZ newer", owner=owner, publication_status="published"
        )
        Process.objects.filter(pk=older.pk).update(
            lastmodified_at=timezone.now() - timezone.timedelta(days=2)
        )
        Process.objects.filter(pk=newer.pk).update(lastmodified_at=timezone.now())
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        view = ProcessDashboardView()
        view.setup(request)
        context = view.get_context_data()
        self.assertEqual([newer, older], list(context["recent_processes"]))


class ProcessDetailOrderingAndGroupingTestCase(ViewWithPermissionsTestCase):
    """Stable parameter grouping and editor-defined bibliography order."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.process = Process.objects.create(
            name="Ordered Process",
            owner=cls.owner,
            publication_status="published",
        )
        cls.url = reverse("processes:process-detail", kwargs={"pk": cls.process.pk})

    def test_parameters_by_type_uses_stable_enum_keys(self):
        """Context keys must be raw parameter values, not translated labels."""
        ProcessOperatingParameter.objects.create(
            process=self.process,
            parameter=ProcessOperatingParameter.Parameter.YIELD,
            value_min=Decimal("10"),
            value_max=Decimal("20"),
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            ProcessOperatingParameter.Parameter.YIELD,
            response.context["parameters_by_type"],
        )
        self.assertContains(response, ">Yield</dt>")

    def test_bibliography_keeps_workspace_order(self):
        """Sources render in the explicit order maintained in the editor."""
        source_b = Source.objects.create(
            title="B Source",
            abbreviation="B",
            owner=self.owner,
            publication_status="published",
        )
        source_a = Source.objects.create(
            title="A Source",
            abbreviation="A",
            owner=self.owner,
            publication_status="published",
        )
        ProcessSource.objects.create(process=self.process, source=source_b, order=1)
        ProcessSource.objects.create(process=self.process, source=source_a, order=2)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["bibliography_sources"], [source_b, source_a])
