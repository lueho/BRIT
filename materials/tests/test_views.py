import json
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.signals import post_save, pre_save
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from factory.django import mute_signals

from bibliography.models import Source
from distributions.models import TemporalDistribution, Timestep
from utils.object_management.models import ReviewAction, UserCreatedObject
from utils.object_management.views import SubmitForReviewView
from utils.properties.models import Unit
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase

from ..models import (
    AnalyticalMethod,
    ComponentMeasurement,
    Composition,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    SampleSeries,
    get_sample_substrate_category_name,
)

User = get_user_model()


class MaterialDashboardViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "change_material"

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("materials-explorer"))
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("materials-explorer"))
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("materials-explorer"))
        self.assertEqual(200, response.status_code)


class BaseMaterialProxyAutocompleteViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.material = Material.objects.create(
            name="Shared search material",
            publication_status="published",
        )
        cls.component = MaterialComponent.objects.create(
            name="Shared search component",
            publication_status="published",
        )

    def test_material_autocomplete_excludes_components(self):
        response = self.client.get(reverse("material-autocomplete"), {"q": "Shared"})

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()["results"]]
        self.assertIn(self.material.name, names)
        self.assertNotIn(self.component.name, names)

    def test_component_autocomplete_excludes_materials(self):
        response = self.client.get(
            reverse("materialcomponent-autocomplete"),
            {"q": "Shared"},
        )

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()["results"]]
        self.assertIn(self.component.name, names)
        self.assertNotIn(self.material.name, names)


class SampleSubstrateMaterialAutocompleteViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        substrate_category_name = get_sample_substrate_category_name()
        category, _ = MaterialCategory.objects.get_or_create(
            name=substrate_category_name
        )

        substrate = Material.objects.create(
            name="Food waste mix",
            publication_status="published",
        )
        substrate.categories.add(category)

        non_substrate = Material.objects.create(
            name="Amino Acids",
            publication_status="published",
        )

        component = MaterialComponent.objects.create(
            name="Carbon",
            publication_status="published",
        )
        component.categories.add(category)

        cls.substrate_name = substrate.name
        cls.non_substrate_name = non_substrate.name
        cls.component_name = component.name

    def test_autocomplete_returns_only_complex_substrate_materials(self):
        response = self.client.get(
            reverse("sample-substrate-material-autocomplete"),
            {"q": "a"},
        )

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()["results"]]

        self.assertIn(self.substrate_name, names)
        self.assertNotIn(self.non_substrate_name, names)
        self.assertNotIn(self.component_name, names)


class SampleSubstrateMaterialQuickCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["add_material"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.substrate_category, _ = MaterialCategory.objects.get_or_create(
            name=get_sample_substrate_category_name()
        )

    def test_post_redirects_anonymous_user_to_login(self):
        response = self.client.post(
            reverse("sample-substrate-material-quick-create"),
            data=json.dumps({"name": "Wood"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 302)

    def test_post_returns_403_without_add_material_permission(self):
        self.client.force_login(self.outsider)

        response = self.client.post(
            reverse("sample-substrate-material-quick-create"),
            data=json.dumps({"name": "Wood"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_post_returns_400_when_name_is_blank(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("sample-substrate-material-quick-create"),
            data=json.dumps({"name": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_post_creates_material_and_attaches_substrate_category(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("sample-substrate-material-quick-create"),
            data=json.dumps({"name": "Wood"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        material = Material.objects.get(pk=payload["id"])

        self.assertEqual(material.owner, self.member)
        self.assertEqual(material.name, "Wood")
        self.assertEqual(material.type, "material")
        self.assertIn(self.substrate_category, material.categories.all())

    def test_post_reuses_existing_owner_material_and_attaches_substrate_category(self):
        existing = Material.objects.create(owner=self.member, name="Wood")
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("sample-substrate-material-quick-create"),
            data=json.dumps({"name": " wood  "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        existing.refresh_from_db()
        self.assertIn(self.substrate_category, existing.categories.all())

    def test_post_blocks_name_matching_published_material(self):
        Material.objects.create(name="Wood", publication_status="published")
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("sample-substrate-material-quick-create"),
            data=json.dumps({"name": "wood"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("published material", response.json()["error"])


class AnalyticalMethodReviewCascadeTest(TestCase):
    """Ensure analytical method review actions cascade to linked sources."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="method_owner")
        cls.other_owner = User.objects.create_user(username="source_owner")
        cls.factory = RequestFactory()

        cls.analytical_method = AnalyticalMethod.objects.create(
            owner=cls.owner,
            name="Method A",
            publication_status="private",
        )
        cls.owner_source = Source.objects.create(
            owner=cls.owner,
            abbreviation="S-OWN",
            title="Owner Source",
            publication_status="private",
        )
        cls.owner_declined_source = Source.objects.create(
            owner=cls.owner,
            abbreviation="S-DECL",
            title="Declined Source",
            publication_status="declined",
        )
        cls.other_source = Source.objects.create(
            owner=cls.other_owner,
            abbreviation="S-OTHER",
            title="Other Source",
            publication_status="private",
        )
        cls.published_source = Source.objects.create(
            owner=cls.owner,
            abbreviation="S-PUB",
            title="Published Source",
            publication_status="published",
        )

        cls.analytical_method.sources.add(
            cls.owner_source,
            cls.owner_declined_source,
            cls.other_source,
            cls.published_source,
        )

    def test_submit_cascades_to_all_sources(self):
        """Submit for review cascades to all linked private/declined sources."""
        request = self.factory.post("/")
        request.user = self.owner

        view = SubmitForReviewView()
        view.request = request
        view.object = self.analytical_method
        view.action_attr_name = "submit_for_review"

        view.post_action_hook(request, "private")

        self.owner_source.refresh_from_db()
        self.owner_declined_source.refresh_from_db()
        self.other_source.refresh_from_db()
        self.published_source.refresh_from_db()

        self.assertEqual(self.owner_source.publication_status, "review")
        self.assertEqual(self.owner_declined_source.publication_status, "review")
        self.assertEqual(self.other_source.publication_status, "review")
        self.assertEqual(self.published_source.publication_status, "published")

    def test_withdraw_cascades_to_sources_in_review(self):
        """Withdraw cascades to all linked sources in review."""
        Source.objects.filter(
            pk__in=[
                self.owner_source.pk,
                self.owner_declined_source.pk,
                self.other_source.pk,
            ]
        ).update(publication_status="review")

        request = self.factory.post("/")
        request.user = self.owner

        view = SubmitForReviewView()
        view.request = request
        view.object = self.analytical_method
        view.action_attr_name = "withdraw_from_review"

        view.post_action_hook(request, "review")

        self.owner_source.refresh_from_db()
        self.owner_declined_source.refresh_from_db()
        self.other_source.refresh_from_db()
        self.published_source.refresh_from_db()

        self.assertEqual(self.owner_source.publication_status, "private")
        self.assertEqual(self.owner_declined_source.publication_status, "private")
        self.assertEqual(self.other_source.publication_status, "private")
        self.assertEqual(self.published_source.publication_status, "published")

    def test_approve_cascades_to_sources_in_review(self):
        """Approve cascades to all linked sources in review."""
        Source.objects.filter(
            pk__in=[
                self.owner_source.pk,
                self.owner_declined_source.pk,
                self.other_source.pk,
            ]
        ).update(publication_status="review")

        request = self.factory.post("/")
        request.user = self.owner

        view = SubmitForReviewView()
        view.request = request
        view.object = self.analytical_method
        view.action_attr_name = "approve"

        view.post_action_hook(request, "review")

        self.owner_source.refresh_from_db()
        self.owner_declined_source.refresh_from_db()
        self.other_source.refresh_from_db()
        self.published_source.refresh_from_db()

        self.assertEqual(self.owner_source.publication_status, "published")
        self.assertEqual(self.owner_declined_source.publication_status, "published")
        self.assertEqual(self.other_source.publication_status, "published")
        self.assertEqual(self.owner_source.approved_by, self.owner)
        self.assertEqual(self.owner_declined_source.approved_by, self.owner)
        self.assertEqual(self.other_source.approved_by, self.owner)
        self.assertEqual(self.published_source.publication_status, "published")

    def test_reject_cascades_to_sources_in_review(self):
        """Reject cascades to all linked sources in review."""
        Source.objects.filter(
            pk__in=[
                self.owner_source.pk,
                self.owner_declined_source.pk,
                self.other_source.pk,
            ]
        ).update(publication_status="review")

        request = self.factory.post("/")
        request.user = self.owner

        view = SubmitForReviewView()
        view.request = request
        view.object = self.analytical_method
        view.action_attr_name = "reject"

        view.post_action_hook(request, "review")

        self.owner_source.refresh_from_db()
        self.owner_declined_source.refresh_from_db()
        self.other_source.refresh_from_db()
        self.published_source.refresh_from_db()

        self.assertEqual(self.owner_source.publication_status, "declined")
        self.assertEqual(self.owner_declined_source.publication_status, "declined")
        self.assertEqual(self.other_source.publication_status, "declined")
        self.assertEqual(self.published_source.publication_status, "published")

    def test_submit_with_no_sources(self):
        """Submit cascade is a no-op when no sources are linked."""
        method = AnalyticalMethod.objects.create(
            owner=self.owner,
            name="Method Empty",
            publication_status="private",
        )
        request = self.factory.post("/")
        request.user = self.owner

        view = SubmitForReviewView()
        view.request = request
        view.object = method
        view.action_attr_name = "submit_for_review"

        view.post_action_hook(request, "private")

        self.assertEqual(method.sources.count(), 0)

    def test_submit_ignores_review_archived_and_unlinked_sources(self):
        """Submit cascade only affects linked private/declined sources."""
        method = AnalyticalMethod.objects.create(
            owner=self.owner,
            name="Method Extra",
            publication_status="private",
        )
        private_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-PRIV",
            title="Private Source",
            publication_status="private",
        )
        declined_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-DEC2",
            title="Declined Source",
            publication_status="declined",
        )
        review_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-REV2",
            title="Review Source",
            publication_status="review",
        )
        archived_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-ARCH",
            title="Archived Source",
            publication_status="archived",
        )
        unlinked_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-UNLINK",
            title="Unlinked Source",
            publication_status="private",
        )

        method.sources.add(
            private_source,
            declined_source,
            review_source,
            archived_source,
        )

        request = self.factory.post("/")
        request.user = self.owner

        view = SubmitForReviewView()
        view.request = request
        view.object = method
        view.action_attr_name = "submit_for_review"

        view.post_action_hook(request, "private")

        private_source.refresh_from_db()
        declined_source.refresh_from_db()
        review_source.refresh_from_db()
        archived_source.refresh_from_db()
        unlinked_source.refresh_from_db()

        self.assertEqual(private_source.publication_status, "review")
        self.assertEqual(declined_source.publication_status, "review")
        self.assertEqual(review_source.publication_status, "review")
        self.assertEqual(archived_source.publication_status, "archived")
        self.assertEqual(unlinked_source.publication_status, "private")

    def test_withdraw_leaves_non_review_sources_unchanged(self):
        """Withdraw cascade only affects linked sources in review."""
        method = AnalyticalMethod.objects.create(
            owner=self.owner,
            name="Method Withdraw",
            publication_status="review",
        )
        review_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-REV3",
            title="Review Source",
            publication_status="review",
        )
        private_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-PRIV2",
            title="Private Source",
            publication_status="private",
        )
        declined_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-DEC3",
            title="Declined Source",
            publication_status="declined",
        )
        published_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-PUB2",
            title="Published Source",
            publication_status="published",
        )
        archived_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-ARCH2",
            title="Archived Source",
            publication_status="archived",
        )

        method.sources.add(
            review_source,
            private_source,
            declined_source,
            published_source,
            archived_source,
        )

        request = self.factory.post("/")
        request.user = self.owner

        view = SubmitForReviewView()
        view.request = request
        view.object = method
        view.action_attr_name = "withdraw_from_review"

        view.post_action_hook(request, "review")

        review_source.refresh_from_db()
        private_source.refresh_from_db()
        declined_source.refresh_from_db()
        published_source.refresh_from_db()
        archived_source.refresh_from_db()

        self.assertEqual(review_source.publication_status, "private")
        self.assertEqual(private_source.publication_status, "private")
        self.assertEqual(declined_source.publication_status, "declined")
        self.assertEqual(published_source.publication_status, "published")
        self.assertEqual(archived_source.publication_status, "archived")

    def test_approve_leaves_non_review_sources_unchanged(self):
        """Approve cascade only affects linked sources in review."""
        method = AnalyticalMethod.objects.create(
            owner=self.owner,
            name="Method Approve",
            publication_status="review",
        )
        review_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-REV4",
            title="Review Source",
            publication_status="review",
        )
        collaborator_review = Source.objects.create(
            owner=self.other_owner,
            abbreviation="S-REV5",
            title="Collaborator Review",
            publication_status="review",
        )
        private_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-PRIV3",
            title="Private Source",
            publication_status="private",
        )
        declined_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-DEC4",
            title="Declined Source",
            publication_status="declined",
        )
        published_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-PUB3",
            title="Published Source",
            publication_status="published",
        )
        archived_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-ARCH3",
            title="Archived Source",
            publication_status="archived",
        )

        method.sources.add(
            review_source,
            collaborator_review,
            private_source,
            declined_source,
            published_source,
            archived_source,
        )

        request = self.factory.post("/")
        request.user = self.owner

        view = SubmitForReviewView()
        view.request = request
        view.object = method
        view.action_attr_name = "approve"

        view.post_action_hook(request, "review")

        review_source.refresh_from_db()
        collaborator_review.refresh_from_db()
        private_source.refresh_from_db()
        declined_source.refresh_from_db()
        published_source.refresh_from_db()
        archived_source.refresh_from_db()

        self.assertEqual(review_source.publication_status, "published")
        self.assertEqual(collaborator_review.publication_status, "published")
        self.assertEqual(review_source.approved_by, self.owner)
        self.assertEqual(collaborator_review.approved_by, self.owner)
        self.assertEqual(private_source.publication_status, "private")
        self.assertEqual(declined_source.publication_status, "declined")
        self.assertEqual(published_source.publication_status, "published")
        self.assertEqual(archived_source.publication_status, "archived")

    def test_reject_leaves_non_review_sources_unchanged(self):
        """Reject cascade only affects linked sources in review."""
        method = AnalyticalMethod.objects.create(
            owner=self.owner,
            name="Method Reject",
            publication_status="review",
        )
        review_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-REV6",
            title="Review Source",
            publication_status="review",
        )
        collaborator_review = Source.objects.create(
            owner=self.other_owner,
            abbreviation="S-REV7",
            title="Collaborator Review",
            publication_status="review",
        )
        private_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-PRIV4",
            title="Private Source",
            publication_status="private",
        )
        declined_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-DEC5",
            title="Declined Source",
            publication_status="declined",
        )
        published_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-PUB4",
            title="Published Source",
            publication_status="published",
        )
        archived_source = Source.objects.create(
            owner=self.owner,
            abbreviation="S-ARCH4",
            title="Archived Source",
            publication_status="archived",
        )

        method.sources.add(
            review_source,
            collaborator_review,
            private_source,
            declined_source,
            published_source,
            archived_source,
        )

        request = self.factory.post("/")
        request.user = self.owner

        view = SubmitForReviewView()
        view.request = request
        view.object = method
        view.action_attr_name = "reject"

        view.post_action_hook(request, "review")

        review_source.refresh_from_db()
        collaborator_review.refresh_from_db()
        private_source.refresh_from_db()
        declined_source.refresh_from_db()
        published_source.refresh_from_db()
        archived_source.refresh_from_db()

        self.assertEqual(review_source.publication_status, "declined")
        self.assertEqual(collaborator_review.publication_status, "declined")
        self.assertEqual(private_source.publication_status, "private")
        self.assertEqual(declined_source.publication_status, "declined")
        self.assertEqual(published_source.publication_status, "published")
        self.assertEqual(archived_source.publication_status, "archived")


# ----------- Material Category CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialCategoryCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True
    add_scope_query_param_to_list_urls = True

    model = MaterialCategory

    view_dashboard_name = "materials-explorer"
    view_create_name = "materialcategory-create"
    view_modal_create_name = "materialcategory-create-modal"
    view_published_list_name = "materialcategory-list"
    view_private_list_name = "materialcategory-list-owned"
    view_detail_name = "materialcategory-detail"
    view_modal_detail_name = "materialcategory-detail-modal"
    view_update_name = "materialcategory-update"
    view_modal_update_name = "materialcategory-update-modal"
    view_delete_name = "materialcategory-delete-modal"

    create_object_data = {"name": "Test Category"}
    update_object_data = {"name": "Updated Test Category"}


# ----------- Material CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True
    add_scope_query_param_to_list_urls = True

    model = Material

    view_dashboard_name = "materials-explorer"
    view_create_name = "material-create"
    view_modal_create_name = "material-create-modal"
    view_published_list_name = "material-list"
    view_private_list_name = "material-list-owned"
    view_detail_name = "material-detail"
    view_modal_detail_name = "material-detail-modal"
    view_update_name = "material-update"
    view_modal_update_name = "material-update-modal"
    view_delete_name = "material-delete-modal"

    create_object_data = {"name": "Test Material"}
    update_object_data = {"name": "Updated Test Material"}

    @classmethod
    def create_published_object(cls):
        published_material = super().create_published_object()
        # Change the name in order to prevent unique key constraint violation
        published_material.name = "Published Test Material"
        published_material.save()
        return published_material


# ----------- Material Component CRUD ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialComponentCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True
    add_scope_query_param_to_list_urls = True

    model = MaterialComponent

    view_dashboard_name = "materials-explorer"
    view_create_name = "materialcomponent-create"
    view_modal_create_name = "materialcomponent-create-modal"
    view_published_list_name = "materialcomponent-list"
    view_private_list_name = "materialcomponent-list-owned"
    view_detail_name = "materialcomponent-detail"
    view_modal_detail_name = "materialcomponent-detail-modal"
    view_update_name = "materialcomponent-update"
    view_modal_update_name = "materialcomponent-update-modal"
    view_delete_name = "materialcomponent-delete-modal"

    create_object_data = {"name": "Test Component"}
    update_object_data = {"name": "Updated Test Component"}

    @classmethod
    def create_published_object(cls):
        published_component = super().create_published_object()
        # Change the name in order to prevent unique key constraint violation
        published_component.name = "Published Test Component"
        published_component.save()
        return published_component


# ----------- Material Component Group CRUD ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialComponentGroupCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True
    add_scope_query_param_to_list_urls = True

    model = MaterialComponentGroup

    view_dashboard_name = "materials-explorer"
    view_create_name = "materialcomponentgroup-create"
    view_modal_create_name = "materialcomponentgroup-create-modal"
    view_published_list_name = "materialcomponentgroup-list"
    view_private_list_name = "materialcomponentgroup-list-owned"
    view_detail_name = "materialcomponentgroup-detail"
    view_modal_detail_name = "materialcomponentgroup-detail-modal"
    view_update_name = "materialcomponentgroup-update"
    view_modal_update_name = "materialcomponentgroup-update-modal"
    view_delete_name = "materialcomponentgroup-delete-modal"

    create_object_data = {"name": "Test Group"}
    update_object_data = {"name": "Updated Test Group"}

    @classmethod
    def create_published_object(cls):
        published_group = super().create_published_object()
        # Change the name in order to prevent unique key constraint violation
        published_group.name = "Published Test Group"
        published_group.save()
        return published_group


# ----------- Material Property CRUD ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialPropertyCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True
    add_scope_query_param_to_list_urls = True

    model = MaterialProperty

    view_dashboard_name = "materials-explorer"
    view_create_name = "materialproperty-create"
    view_modal_create_name = "materialproperty-create-modal"
    view_published_list_name = "materialproperty-list"
    view_private_list_name = "materialproperty-list-owned"
    view_detail_name = "materialproperty-detail"
    view_modal_detail_name = "materialproperty-detail-modal"
    view_update_name = "materialproperty-update"
    view_modal_update_name = "materialproperty-update-modal"
    view_delete_name = "materialproperty-delete-modal"

    create_object_data = {"name": "Test Property", "unit": "Test Unit"}
    update_object_data = {"name": "Updated Test Property", "unit": "Test Unit"}


# ----------- Material Property Value CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialPropertyValueModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "delete_materialpropertyvalue"
    url_name = "materialpropertyvalue-delete-modal"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        prop = MaterialProperty.objects.create(
            owner=cls.member, name="Test Property", unit="Test Unit"
        )
        material = Material.objects.create(
            name="Test Material",
        )
        sample = Sample.objects.create(
            owner=cls.member,
            name="Test Sample",
            material=material,
        )
        cls.value = MaterialPropertyValue.objects.create(
            owner=cls.member,
            sample=sample,
            property=prop,
            average=123.312,
            standard_deviation=0.1337,
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={"pk": self.value.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name, kwargs={"pk": self.value.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse(self.url_name, kwargs={"pk": self.value.pk}))
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse(self.url_name, kwargs={"pk": self.value.pk}))
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={"pk": self.value.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.value.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        sample = self.value.sample
        sample = Sample.objects.get(name="Test Sample")
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.value.pk})
        )
        sample = Sample.objects.get(name="Test Sample")
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": sample.pk})
        )
        with self.assertRaises(MaterialPropertyValue.DoesNotExist):
            MaterialPropertyValue.objects.get(pk=self.value.pk)

    def test_post_success_and_http_302_redirect_for_fk_only_members(self):
        self.client.force_login(self.member)
        sample = Sample.objects.get(name="Test Sample")
        value = MaterialPropertyValue.objects.create(
            owner=self.member,
            sample=sample,
            property=self.value.property,
            average=Decimal("98.1"),
            standard_deviation=Decimal("0.2"),
        )

        response = self.client.post(reverse(self.url_name, kwargs={"pk": value.pk}))

        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": sample.pk})
        )
        with self.assertRaises(MaterialPropertyValue.DoesNotExist):
            MaterialPropertyValue.objects.get(pk=value.pk)


class MaterialPropertyValueUpdateViewTestCase(ViewWithPermissionsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_materialpropertyvalue")
        )
        cls.unit = Unit.objects.create(name="mg/L", owner=cls.owner)
        cls.default_basis = MaterialComponent.objects.create(
            owner=cls.owner,
            name="Dry Matter",
            publication_status="published",
        )
        cls.alt_basis = MaterialComponent.objects.create(
            owner=cls.owner,
            name="Volatile Solids",
            publication_status="published",
        )
        cls.property = MaterialProperty.objects.create(
            owner=cls.owner,
            name="Dry Matter",
            unit="mg/L",
            default_basis_component=cls.default_basis,
            publication_status="published",
        )
        cls.property.allowed_units.add(cls.unit)
        cls.material = Material.objects.create(
            owner=cls.owner,
            name="Digestate",
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner,
            name="Sample with properties",
            material=cls.material,
            publication_status="published",
        )
        cls.value = MaterialPropertyValue.objects.create(
            owner=cls.owner,
            sample=cls.sample,
            property=cls.property,
            basis_component=cls.default_basis,
            unit=cls.unit,
            average=Decimal("12.5"),
            standard_deviation=Decimal("0.5"),
            publication_status="private",
        )

    def test_sample_detail_shows_property_edit_link_for_private_sample_owner(self):
        self.sample.publication_status = "private"
        self.sample.save(update_fields=["publication_status"])
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
            {"mode": "edit"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("materialpropertyvalue-update", kwargs={"pk": self.value.pk}),
        )

    def test_sample_detail_hides_property_edit_link_for_outsider(self):
        self.client.force_login(self.outsider)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            reverse("materialpropertyvalue-update", kwargs={"pk": self.value.pk}),
        )

    def test_property_value_absolute_url_points_to_sample_detail(self):
        self.assertEqual(
            self.value.get_absolute_url(),
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )

    def test_sample_detail_shows_canonical_property_mapping_for_properties(self):
        canonical_property = MaterialProperty.objects.create(
            owner=self.owner,
            name="Organic matter",
            unit="%",
            publication_status="published",
        )
        aliased_property = MaterialProperty.objects.create(
            owner=self.owner,
            name="Volatile solids",
            unit="%",
            comparable_property=canonical_property,
            publication_status="published",
        )
        MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=self.sample,
            property=aliased_property,
            unit=self.unit,
            average=Decimal("61.0"),
            standard_deviation=Decimal("0.5"),
            publication_status="private",
        )

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Volatile solids")
        self.assertContains(response, "Canonical: Organic matter")

    def test_sample_detail_shows_value_level_basis_for_properties(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.value.basis_component.name)

    def test_sample_detail_hides_missing_property_standard_deviation(self):
        value = MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=self.sample,
            property=self.property,
            basis_component=self.default_basis,
            unit=self.unit,
            average=Decimal("61.25"),
            standard_deviation=None,
            publication_status="private",
        )

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "61.25")
        self.assertNotContains(response, "61.25 ±")
        self.assertEqual(value.standard_deviation, None)

    def test_update_view_redirects_back_to_sample_detail(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("materialpropertyvalue-update", kwargs={"pk": self.value.pk}),
            data={
                "property": self.property.pk,
                "basis_component": self.alt_basis.pk,
                "unit": self.unit.pk,
                "analytical_method": "",
                "sources": [],
                "average": "14.25",
                "standard_deviation": "0.75",
            },
        )

        self.assertRedirects(
            response,
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )
        self.value.refresh_from_db()
        self.assertEqual(self.value.average, Decimal("14.25"))
        self.assertEqual(self.value.standard_deviation, Decimal("0.75"))
        self.assertEqual(self.value.basis_component, self.alt_basis)


class MaterialPropertyValueCreateAndDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_materialpropertyvalue"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = Unit.objects.create(name="g/L", owner=cls.member)
        cls.default_basis = MaterialComponent.objects.create(
            owner=cls.member,
            name="Dry Matter",
        )
        cls.property = MaterialProperty.objects.create(
            owner=cls.member,
            name="Dry Matter",
            unit="g/L",
            default_basis_component=cls.default_basis,
            publication_status="published",
        )
        cls.property.allowed_units.add(cls.unit)
        cls.material = Material.objects.create(
            owner=cls.member,
            name="Digestate",
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            owner=cls.member,
            name="Sample for property creation",
            material=cls.material,
            publication_status="private",
        )
        cls.value = MaterialPropertyValue.objects.create(
            owner=cls.member,
            sample=cls.sample,
            property=cls.property,
            basis_component=cls.default_basis,
            unit=cls.unit,
            average=Decimal("12.5"),
            standard_deviation=Decimal("0.5"),
            publication_status="private",
        )

    def test_create_view_creates_value_for_related_sample_and_redirects(self):
        self.client.force_login(self.member)

        response = self.client.post(
            f"{reverse('materialpropertyvalue-create')}?sample={self.sample.pk}",
            data={
                "property": self.property.pk,
                "basis_component": self.default_basis.pk,
                "unit": self.unit.pk,
                "analytical_method": "",
                "sources": [],
                "average": "18.25",
                "standard_deviation": "0.75",
            },
        )

        self.assertRedirects(
            response,
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )
        value = MaterialPropertyValue.objects.get(average=Decimal("18.25"))
        self.assertEqual(value.owner, self.member)
        self.assertEqual(value.sample, self.sample)
        self.assertIn(value, self.sample.property_values.all())

    def test_create_view_allows_missing_standard_deviation(self):
        self.client.force_login(self.member)

        response = self.client.post(
            f"{reverse('materialpropertyvalue-create')}?sample={self.sample.pk}",
            data={
                "property": self.property.pk,
                "basis_component": self.default_basis.pk,
                "unit": self.unit.pk,
                "analytical_method": "",
                "sources": [],
                "average": "19.5",
                "standard_deviation": "",
            },
        )

        self.assertRedirects(
            response,
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )
        value = MaterialPropertyValue.objects.get(average=Decimal("19.5"))
        self.assertIsNone(value.standard_deviation)

    def test_detail_view_redirects_to_related_sample_detail(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse("materialpropertyvalue-detail", kwargs={"pk": self.value.pk})
        )

        self.assertRedirects(
            response,
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )


class ComponentMeasurementUpdateViewTestCase(ViewWithPermissionsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_componentmeasurement")
        )
        cls.unit = Unit.objects.filter(name="%").first()
        if cls.unit is None:
            cls.unit = Unit.objects.create(
                name="%",
                symbol="percent",
                owner=cls.owner,
                publication_status="published",
            )
        elif not cls.unit.symbol or cls.unit.publication_status != "published":
            cls.unit.symbol = "percent"
            cls.unit.publication_status = "published"
            cls.unit.save(update_fields=["symbol", "publication_status"])

        cls.group = MaterialComponentGroup.objects.create(
            owner=cls.owner,
            name="Composition group",
            publication_status="published",
        )
        cls.component = MaterialComponent.objects.create(
            owner=cls.owner,
            name="Carbon",
            publication_status="published",
        )
        cls.material = Material.objects.create(
            owner=cls.owner,
            name="Digestate",
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner,
            name="Sample with measurements",
            material=cls.material,
            publication_status="published",
        )
        cls.measurement = ComponentMeasurement.objects.create(
            owner=cls.owner,
            sample=cls.sample,
            group=cls.group,
            component=cls.component,
            unit=cls.unit,
            average=Decimal("12.5"),
            standard_deviation=Decimal("0.5"),
            publication_status="private",
        )

    def test_sample_detail_shows_measurement_edit_link_for_private_sample_owner(self):
        self.sample.publication_status = "private"
        self.sample.save(update_fields=["publication_status"])
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
            {"mode": "edit"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse(
                "componentmeasurement-update",
                kwargs={"pk": self.measurement.pk},
            ),
        )

    def test_sample_detail_hides_measurement_edit_link_for_outsider(self):
        self.client.force_login(self.outsider)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            reverse(
                "componentmeasurement-update",
                kwargs={"pk": self.measurement.pk},
            ),
        )

    def test_measurement_absolute_url_points_to_sample_detail(self):
        self.assertEqual(
            self.measurement.get_absolute_url(),
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )

    def test_sample_detail_hides_missing_measurement_standard_deviation(self):
        measurement = ComponentMeasurement.objects.create(
            owner=self.owner,
            sample=self.sample,
            group=self.group,
            component=self.component,
            unit=self.unit,
            average=Decimal("7.25"),
            standard_deviation=None,
            publication_status="private",
        )

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "7.25")
        self.assertNotContains(response, "7.25 ±")
        self.assertEqual(measurement.standard_deviation, None)

    def test_update_view_redirects_back_to_sample_detail(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("componentmeasurement-update", kwargs={"pk": self.measurement.pk}),
            data={
                "group": self.group.pk,
                "component": self.component.pk,
                "basis_component": "",
                "analytical_method": "",
                "sources": [],
                "unit": self.unit.pk,
                "average": "14.25",
                "standard_deviation": "0.75",
                "sample_size": "3",
                "comment": "Updated from sample detail",
            },
        )

        self.assertRedirects(
            response,
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.average, Decimal("14.25"))
        self.assertEqual(self.measurement.sample_size, 3)
        self.assertEqual(self.measurement.comment, "Updated from sample detail")


class ComponentMeasurementCreateAndDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_componentmeasurement"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = Unit.objects.filter(name="%").first()
        if cls.unit is None:
            cls.unit = Unit.objects.create(
                name="%",
                symbol="percent",
                owner=cls.member,
                publication_status="published",
            )
        elif not cls.unit.symbol or cls.unit.publication_status != "published":
            cls.unit.symbol = "percent"
            cls.unit.publication_status = "published"
            cls.unit.save(update_fields=["symbol", "publication_status"])

        cls.group = MaterialComponentGroup.objects.create(
            owner=cls.member,
            name="Composition group",
            publication_status="published",
        )
        cls.component = MaterialComponent.objects.create(
            owner=cls.member,
            name="Carbon",
            publication_status="published",
        )
        cls.material = Material.objects.create(
            owner=cls.member,
            name="Digestate",
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            owner=cls.member,
            name="Sample for measurement creation",
            material=cls.material,
            publication_status="private",
        )
        cls.measurement = ComponentMeasurement.objects.create(
            owner=cls.member,
            sample=cls.sample,
            group=cls.group,
            component=cls.component,
            unit=cls.unit,
            average=Decimal("12.5"),
            standard_deviation=Decimal("0.5"),
            publication_status="private",
        )

    def test_sample_detail_shows_measurement_create_link_for_sample_owner(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
            {"mode": "edit"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"{reverse('componentmeasurement-create')}?sample={self.sample.pk}",
        )

    def test_create_view_creates_measurement_for_related_sample_and_redirects(self):
        self.client.force_login(self.member)

        response = self.client.post(
            f"{reverse('componentmeasurement-create')}?sample={self.sample.pk}",
            data={
                "group": self.group.pk,
                "component": self.component.pk,
                "basis_component": "",
                "analytical_method": "",
                "sources": [],
                "unit": self.unit.pk,
                "average": "18.25",
                "standard_deviation": "0.75",
                "sample_size": "3",
                "comment": "Created from dedicated route",
            },
        )

        self.assertRedirects(
            response,
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )
        measurement = ComponentMeasurement.objects.get(
            average=Decimal("18.25"),
            comment="Created from dedicated route",
        )
        self.assertEqual(measurement.owner, self.member)
        self.assertEqual(measurement.sample, self.sample)

    def test_create_view_allows_missing_standard_deviation(self):
        self.client.force_login(self.member)

        response = self.client.post(
            f"{reverse('componentmeasurement-create')}?sample={self.sample.pk}",
            data={
                "group": self.group.pk,
                "component": self.component.pk,
                "basis_component": "",
                "analytical_method": "",
                "sources": [],
                "unit": self.unit.pk,
                "average": "21.0",
                "standard_deviation": "",
                "sample_size": "",
                "comment": "Without spread",
            },
        )

        self.assertRedirects(
            response,
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )
        measurement = ComponentMeasurement.objects.get(
            average=Decimal("21.0"),
            comment="Without spread",
        )
        self.assertIsNone(measurement.standard_deviation)

    def test_detail_view_redirects_to_related_sample_detail(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse("componentmeasurement-detail", kwargs={"pk": self.measurement.pk})
        )

        self.assertRedirects(
            response,
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
        )


# ----------- Analytical Method CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AnalyticalMethodCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    add_scope_query_param_to_list_urls = True

    model = AnalyticalMethod

    view_dashboard_name = "materials-explorer"
    view_create_name = "analyticalmethod-create"
    view_published_list_name = "analyticalmethod-list"
    view_private_list_name = "analyticalmethod-list-owned"
    view_detail_name = "analyticalmethod-detail"
    view_modal_detail_name = "analyticalmethod-detail-modal"
    view_update_name = "analyticalmethod-update"
    view_delete_name = "analyticalmethod-delete-modal"

    create_object_data = {"name": "Test Method"}
    update_object_data = {"name": "Updated Test Method"}


class AnalyticalMethodDetailViewSamplesTestCase(ViewWithPermissionsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.method = AnalyticalMethod.objects.create(
            owner=cls.owner,
            name="Combustion analysis",
            publication_status="published",
        )
        cls.material = Material.objects.create(
            owner=cls.owner,
            name="Digestate",
            publication_status="published",
        )
        cls.property = MaterialProperty.objects.create(
            owner=cls.owner,
            name="Dry matter",
            unit="%",
            publication_status="published",
        )
        cls.group = MaterialComponentGroup.objects.create(
            owner=cls.owner,
            name="Chemical elements",
            publication_status="published",
        )
        cls.component = MaterialComponent.objects.create(
            owner=cls.owner,
            name="Carbon",
            publication_status="published",
        )
        cls.unit = Unit.objects.filter(name="%").first()
        if cls.unit is None:
            cls.unit = Unit.objects.create(name="%", symbol="percent", owner=cls.owner)
        elif not cls.unit.symbol:
            cls.unit.symbol = "percent"
            cls.unit.save(update_fields=["symbol"])

        cls.visible_sample = Sample.objects.create(
            owner=cls.owner,
            name="Published linked sample",
            material=cls.material,
            publication_status="published",
        )
        MaterialPropertyValue.objects.create(
            owner=cls.owner,
            sample=cls.visible_sample,
            property=cls.property,
            unit=cls.unit,
            analytical_method=cls.method,
            average=Decimal("42.0"),
            standard_deviation=Decimal("0.0"),
        )
        ComponentMeasurement.objects.create(
            owner=cls.owner,
            sample=cls.visible_sample,
            group=cls.group,
            component=cls.component,
            analytical_method=cls.method,
            unit=cls.unit,
            average=Decimal("1.0"),
        )

        cls.private_sample = Sample.objects.create(
            owner=cls.owner,
            name="Private linked sample",
            material=cls.material,
            publication_status="private",
        )
        ComponentMeasurement.objects.create(
            owner=cls.owner,
            sample=cls.private_sample,
            group=cls.group,
            component=cls.component,
            analytical_method=cls.method,
            unit=cls.unit,
            average=Decimal("2.0"),
        )

    def test_detail_view_lists_visible_related_samples_once_for_non_owner(self):
        self.client.force_login(self.outsider)

        response = self.client.get(
            reverse("analyticalmethod-detail", kwargs={"pk": self.method.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Samples:")
        self.assertContains(response, "Published linked sample", count=1)
        self.assertContains(
            response,
            reverse("sample-detail", kwargs={"pk": self.visible_sample.pk}),
        )
        self.assertNotContains(response, "Private linked sample")

    def test_detail_view_includes_private_related_samples_for_owner(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("analyticalmethod-detail", kwargs={"pk": self.method.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published linked sample")
        self.assertContains(response, "Private linked sample")


# ----------- Sample Series CRUD ---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleSeriesCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_create_view = True
    add_scope_query_param_to_list_urls = True

    model = SampleSeries

    view_dashboard_name = "materials-explorer"
    view_create_name = "sampleseries-create"
    view_modal_create_name = "sampleseries-create-modal"
    view_published_list_name = "sampleseries-list"
    view_private_list_name = "sampleseries-list-owned"
    view_detail_name = "sampleseries-detail"
    view_modal_detail_name = "sampleseries-detail-modal"
    view_update_name = "sampleseries-update"
    view_delete_name = "sampleseries-delete-modal"

    create_object_data = {"name": "Test Series"}
    update_object_data = {"name": "Updated Test Series"}

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(
            name="Test Material", publication_status="published"
        )
        return {"material": material}


# ----------- Sample Series Utilities ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleSeriesCreateDuplicateViewTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    create_view = False
    public_list_view = False
    private_list_view = False
    detail_view = False
    delete_view = False

    model = SampleSeries

    view_detail_name = "sampleseries-detail"
    view_update_name = "sampleseries-duplicate"

    create_object_data = {"name": "Test Series"}
    update_object_data = {"name": "Updated Test Series", "description": "New Duplicate"}

    @classmethod
    def create_related_objects(cls):
        return {
            "material": Material.objects.create(
                name="Test Material", publication_status="published"
            )
        }


# ----------- Back URL Navigation Tests ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class BackURLNavigationTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    """Test that back URL parameter is properly passed from list/detail navigation.

    Uses the standard CRUD test infrastructure so that objects are created via the
    proper fixtures/helpers that satisfy signal requirements.
    """

    create_view = False
    public_list_view = False
    private_list_view = False
    update_view = False
    delete_view = False

    model = SampleSeries

    view_detail_name = "sampleseries-detail"
    view_published_list_name = "sampleseries-list"

    create_object_data = {"name": "Back Nav Test Series"}
    update_object_data = {"name": "Updated Back Nav Test Series"}

    @classmethod
    def create_related_objects(cls):
        return {
            "material": Material.objects.create(
                name="Back Nav Test Material", publication_status="published"
            )
        }

    def test_sampleseries_detail_shows_back_to_results_button(self):
        """Detail page shows 'Back to results' button when back parameter is present."""
        self.client.force_login(self.non_owner_user)
        list_url = f"{reverse('sampleseries-list')}?scope=published"
        detail_url = (
            f"{reverse('sampleseries-detail', kwargs={'pk': self.published_object.pk})}"
            f"?back={quote(list_url, safe='')}"
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Back to results")
        self.assertContains(response, f'href="{list_url}"')

    def test_sampleseries_list_back_param_present_in_detail_links(self):
        """Sample series list links contain ?back= pointing to the current list URL."""
        self.client.force_login(self.staff_user)
        list_url = f"{reverse('sampleseries-list')}?scope=published"
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "?back=")

    def test_sampleseries_list_with_filters_back_param_contains_filters(self):
        """The back param on detail links encodes active filter/sort state."""
        self.client.force_login(self.staff_user)
        list_url = f"{reverse('sampleseries-list')}?scope=published"
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        expected_back_fragment = quote(list_url, safe="")
        self.assertContains(response, f"back={expected_back_fragment}")

    def test_review_objects_use_next_parameter_not_back(self):
        """Objects in review status use ?next= for review flow, not ?back=."""
        review_object = SampleSeries.objects.create(
            name="Back Nav Review Series",
            publication_status="review",
            owner=self.non_owner_user,
            **self.related_objects,
        )

        self.client.force_login(self.staff_user)
        list_url = reverse("sampleseries-list-review")
        response = self.client.get(list_url, follow=True)
        self.assertEqual(response.status_code, 200)

        review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(SampleSeries).id,
                "object_id": review_object.pk,
            },
        )
        self.assertContains(response, f"{review_url}?next=")
        self.assertNotContains(response, f"{review_url}?back=")


# ----------- Sample CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class FeaturedSampleListViewTestCase(ViewWithPermissionsTestCase):
    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("sample-list-featured"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse("sample-gallery"))

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("sample-list-featured"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse("sample-gallery"))


class SampleRepresentationViewsTestCase(ViewWithPermissionsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(
            owner=cls.owner,
            name="Test Material",
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner,
            name="Test Sample",
            publication_status="published",
            material=cls.material,
            standalone=True,
        )
        cls.percent, _ = Unit.objects.get_or_create(
            owner=cls.owner, name="%", defaults={"symbol": "%"}
        )

    def test_public_list_includes_gallery_switch(self):
        response = self.client.get(reverse("sample-list"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("sample-gallery"))
        self.assertContains(response, self.sample.name)

    def test_public_list_includes_export_button(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("sample-list"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "export-modal-sample-list-export")
        self.assertContains(response, "Export data")

    def test_public_gallery_renders_and_links_back_to_list(self):
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("sample-list"))
        # The whole card links to the detail page; no redundant CTA button.
        self.assertNotContains(response, ">Open sample</a>")
        self.assertContains(response, self.material.name)

    def test_private_gallery_renders_for_owner(self):
        self.sample.publication_status = "private"
        self.sample.save(update_fields=["publication_status"])
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("sample-gallery-owned"), {"scope": "private"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("sample-list-owned"))
        self.assertContains(response, "Edit metadata")

    def test_public_gallery_uses_series_image_when_sample_image_missing(self):
        series = SampleSeries.objects.create(
            owner=self.owner,
            name="Series With Image",
            material=self.material,
            image="materials_sampleseries/series-image.jpg",
        )
        sample = Sample.objects.create(
            owner=self.owner,
            name="Series-backed Sample",
            publication_status="published",
            material=self.material,
            series=series,
        )
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "materials_sampleseries/series-image.jpg")
        self.assertContains(response, 'loading="lazy"')
        self.assertContains(response, 'decoding="async"')
        self.assertContains(response, 'width="800"')
        self.assertContains(response, 'height="450"')
        self.assertContains(response, sample.name)

    def _add_sample_data(self):
        """Attach two measurements in one group plus one property value."""
        group = MaterialComponentGroup.objects.create(
            owner=self.owner,
            name="Chemical elements",
            publication_status="published",
        )
        wood = MaterialComponent.objects.create(
            owner=self.owner,
            name="Wood",
            publication_status="published",
        )
        ash = MaterialComponent.objects.create(
            owner=self.owner,
            name="Ash",
            publication_status="published",
        )
        ComponentMeasurement.objects.create(
            owner=self.owner,
            sample=self.sample,
            group=group,
            component=wood,
            unit=self.percent,
            average=Decimal("60.0"),
        )
        ComponentMeasurement.objects.create(
            owner=self.owner,
            sample=self.sample,
            group=group,
            component=ash,
            unit=self.percent,
            average=Decimal("10.0"),
        )
        moisture = MaterialProperty.objects.create(
            owner=self.owner,
            name="Moisture",
            publication_status="published",
        )
        MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=self.sample,
            property=moisture,
            average=Decimal("5.0"),
            publication_status="published",
        )

    def _card_for(self, response):
        return response.context["sample_cards"][self.sample.pk]

    def test_public_list_provides_sample_card_data(self):
        self._add_sample_data()
        response = self.client.get(reverse("sample-list"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        card = self._card_for(response)
        self.assertEqual(card["measurement_count"], 2)
        self.assertEqual(card["property_value_count"], 1)
        self.assertEqual(card["component_preview"], ["Wood", "Ash"])
        self.assertEqual(card["component_preview_overflow"], 0)

    def test_public_gallery_provides_sample_card_data(self):
        self._add_sample_data()
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        card = self._card_for(response)
        self.assertEqual(card["measurement_count"], 2)
        self.assertEqual(card["property_value_count"], 1)
        self.assertEqual(card["component_preview"], ["Wood", "Ash"])

    def test_sample_card_component_preview_limits_to_three_with_overflow(self):
        group = MaterialComponentGroup.objects.create(
            owner=self.owner,
            name="Chemical elements",
            publication_status="published",
        )
        names = ["Carbon", "Hydrogen", "Nitrogen", "Oxygen"]
        components = [
            MaterialComponent.objects.create(
                owner=self.owner, name=name, publication_status="published"
            )
            for name in names
        ]
        for index, component in enumerate(components):
            ComponentMeasurement.objects.create(
                owner=self.owner,
                sample=self.sample,
                group=group,
                component=component,
                unit=self.percent,
                average=Decimal(index + 1),
            )
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        card = self._card_for(response)
        self.assertEqual(card["component_preview"], ["Oxygen", "Nitrogen", "Hydrogen"])
        self.assertEqual(card["component_preview_overflow"], 1)

    def test_sample_card_component_preview_survives_repeated_measurements(self):
        group = MaterialComponentGroup.objects.create(
            owner=self.owner,
            name="Chemical elements",
            publication_status="published",
        )
        carbon = MaterialComponent.objects.create(
            owner=self.owner, name="Carbon", publication_status="published"
        )
        for _ in range(15):
            ComponentMeasurement.objects.create(
                owner=self.owner,
                sample=self.sample,
                group=group,
                component=carbon,
                unit=self.percent,
                average=Decimal("50.0"),
            )
        for name, average in (("Hydrogen", "6"), ("Oxygen", "40"), ("Ash", "4")):
            component = MaterialComponent.objects.create(
                owner=self.owner, name=name, publication_status="published"
            )
            ComponentMeasurement.objects.create(
                owner=self.owner,
                sample=self.sample,
                group=group,
                component=component,
                unit=self.percent,
                average=Decimal(average),
            )
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        card = self._card_for(response)
        self.assertEqual(card["measurement_count"], 18)
        self.assertEqual(card["component_preview"], ["Carbon", "Oxygen", "Hydrogen"])
        self.assertEqual(card["component_preview_overflow"], 1)

    def test_sample_card_component_preview_ranks_by_converted_weight_share(self):
        group = MaterialComponentGroup.objects.create(
            owner=self.owner, name="Chemical elements", publication_status="published"
        )
        g_per_kg = Unit.objects.create(owner=self.owner, name="g/kg", symbol="g/kg")
        for name, average, unit in (
            ("Nitrogen", "40", self.percent),
            ("Carbon", "300", g_per_kg),
            ("Zinc", "50", g_per_kg),
        ):
            component = MaterialComponent.objects.create(
                owner=self.owner, name=name, publication_status="published"
            )
            ComponentMeasurement.objects.create(
                owner=self.owner,
                sample=self.sample,
                group=group,
                component=component,
                average=Decimal(average),
                unit=unit,
            )
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        card = self._card_for(response)
        self.assertEqual(card["component_preview"], ["Nitrogen", "Carbon", "Zinc"])

    def test_sample_card_preview_does_not_leak_into_empty_samples(self):
        self._add_sample_data()
        empty = Sample.objects.create(
            owner=self.owner,
            name="Empty sample",
            material=self.sample.material,
            publication_status="published",
        )
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        cards = response.context["sample_cards"]
        self.assertEqual(cards[self.sample.pk]["component_preview"], ["Wood", "Ash"])
        self.assertEqual(cards[empty.pk]["component_preview"], [])
        self.assertEqual(cards[empty.pk]["measurement_count"], 0)

    def test_gallery_renders_card_data_signals(self):
        self._add_sample_data()
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        self.assertContains(response, "data-sample-card-signals")
        self.assertContains(response, "Wood")

    def test_empty_sample_card_has_zeroed_signals(self):
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        card = self._card_for(response)
        self.assertEqual(card["measurement_count"], 0)
        self.assertEqual(card["property_value_count"], 0)
        self.assertEqual(card["component_preview"], [])
        self.assertEqual(card["component_preview_overflow"], 0)

    def test_detail_view_uses_series_image_when_sample_image_missing(self):
        series = SampleSeries.objects.create(
            owner=self.owner,
            name="Series With Image",
            material=self.material,
            image="materials_sampleseries/series-image.jpg",
        )
        sample = Sample.objects.create(
            owner=self.owner,
            name="Series-backed Sample",
            publication_status="published",
            material=self.material,
            series=series,
        )
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "materials_sampleseries/series-image.jpg")
        self.assertContains(response, "Showing the image from the linked sample series")
        self.assertContains(response, sample.name)

    def test_list_marks_list_segment_active(self):
        response = self.client.get(reverse("sample-list"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        # Representation switcher is present.
        self.assertContains(response, 'aria-label="View toggle"')
        # The list segment is the active/current one on the list page.
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'title="View as list"')
        # The featured (gallery) view is reachable as a peer.
        self.assertContains(response, 'title="View as featured gallery"')
        self.assertContains(response, reverse("sample-gallery"))

    def test_gallery_marks_featured_segment_active(self):
        response = self.client.get(reverse("sample-gallery"), {"scope": "published"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="View toggle"')
        # Active segment links to the current path (gallery), list is a peer link.
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, reverse("sample-list"))

    def test_detail_exposes_switcher_with_no_active_segment(self):
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 200)
        # The same peer-view switcher appears on the detail header.
        self.assertContains(response, 'aria-label="Sample navigation"')
        self.assertContains(response, reverse("sample-list"))
        self.assertContains(response, reverse("sample-gallery"))
        # Detail is not a list representation, so no segment is marked active.
        self.assertNotContains(response, 'aria-pressed="true"')

    def test_detail_keeps_explorer_separate_from_switcher(self):
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 200)
        # Explorer remains reachable as a distinct, secondary affordance and is
        # not folded into the representation switcher.
        self.assertContains(response, reverse("materials-explorer"))
        self.assertContains(response, "Materials explorer")


class SampleCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_create_view = True

    model = Sample

    view_dashboard_name = "materials-explorer"
    view_create_name = "sample-create"
    view_modal_create_name = "sample-create-modal"
    view_published_list_name = "sample-list"
    view_private_list_name = "sample-list-owned"
    view_detail_name = "sample-detail"
    view_update_name = "sample-update"
    view_delete_name = "sample-delete-modal"

    allow_create_for_any_authenticated_user = True
    add_scope_query_param_to_list_urls = True

    create_object_data = {"name": "Test Sample", "standalone": True}
    update_object_data = {"name": "Updated Test Sample", "standalone": True}

    @classmethod
    def create_related_objects(cls):
        substrate_category, _ = MaterialCategory.objects.get_or_create(
            name=get_sample_substrate_category_name()
        )
        material = Material.objects.create(
            name="Test Material", publication_status="published"
        )
        material.categories.add(substrate_category)
        cls.property = MaterialProperty.objects.create(
            name="Test Property", unit="Test Unit", publication_status="published"
        )
        return {"material": material}

    @classmethod
    def create_published_object(cls):
        published_sample = super().create_published_object()
        MaterialPropertyValue.objects.create(
            sample=published_sample,
            property=cls.property,
            average=123.3,
            standard_deviation=0.13,
            publication_status="published",
        )
        return published_sample

    @classmethod
    def create_unpublished_object(cls):
        unpublished_sample = super().create_unpublished_object()
        MaterialPropertyValue.objects.create(
            sample=unpublished_sample,
            property=cls.property,
            average=123.3,
            standard_deviation=0.13,
            publication_status=unpublished_sample.publication_status,
        )
        return unpublished_sample

    def test_review_detail_view_does_not_link_back_to_itself(self):
        """On the review page the rail must not offer a link back to itself."""
        declined_sample = self.model.objects.create(
            name="Declined test sample",
            owner=self.owner_user,
            publication_status="declined",
            **self.related_objects,
        )
        self.client.force_login(self.owner_user)
        review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(self.model).id,
                "object_id": declined_sample.pk,
            },
        )

        response = self.client.get(review_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Review feedback")
        self.assertNotContains(response, f'href="{review_url}')

    def test_update_view_prefills_material_autocomplete_with_material_name(self):
        substrate_category, _ = MaterialCategory.objects.get_or_create(
            name=get_sample_substrate_category_name()
        )
        material = Material.objects.create(
            owner=self.owner_user,
            name="Prefill Material Without Abbreviation",
            abbreviation="",
            publication_status="private",
        )
        material.categories.add(substrate_category)
        self.unpublished_object.material = material
        self.unpublished_object.save(update_fields=["material"])

        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_update_url(self.unpublished_object.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, material.name)

    def test_list_view_published_as_authenticated_owner(self):
        if not self.public_list_view:
            self.skipTest("List view is not enabled for this test case.")
        self.client.force_login(self.owner_user)
        response = self.client.get(
            self.get_list_url(publication_status="published"), follow=True
        )
        self.assertEqual(response.status_code, 200)
        if self.dashboard_view:
            self.assertContains(response, self.get_dashboard_url())
        if self.create_view:
            self.assertContains(
                response, self.get_create_url()
            )  # This is the difference to the original test function
        if self.private_list_view:
            self.assertContains(
                response, self.get_list_url(publication_status="private")
            )

    def test_list_view_published_as_authenticated_non_owner(self):
        if not self.public_list_view:
            self.skipTest("List view is not enabled for this test case.")
        self.client.force_login(self.non_owner_user)
        response = self.client.get(
            self.get_list_url(publication_status="published"), follow=True
        )
        self.assertEqual(response.status_code, 200)
        if self.dashboard_view:
            self.assertContains(response, self.get_dashboard_url())
        if self.create_view:
            self.assertContains(
                response, self.get_create_url()
            )  # This is the difference to the original test function
        if self.private_list_view:
            self.assertContains(
                response, self.get_list_url(publication_status="private")
            )

    def test_list_view_private_as_authenticated_owner(self):
        if not self.private_list_view:
            self.skipTest("List view is not enabled for this test case")
        self.client.force_login(self.owner_user)
        response = self.client.get(
            self.get_list_url(publication_status="private"), follow=True
        )
        self.assertEqual(response.status_code, 200)
        if self.dashboard_view:
            self.assertContains(response, self.get_dashboard_url())
        if self.create_view:
            self.assertContains(
                response, self.get_create_url()
            )  # This is the difference to the original test function
        if self.public_list_view:
            self.assertContains(
                response, self.get_list_url(publication_status="published")
            )

    def test_list_view_private_as_authenticated_non_owner(self):
        if not self.private_list_view:
            self.skipTest("List view is not enabled for this test case")
        self.client.force_login(self.non_owner_user)
        response = self.client.get(
            self.get_list_url(publication_status="private"), follow=True
        )
        self.assertEqual(response.status_code, 200)
        if self.dashboard_view:
            self.assertContains(response, self.get_dashboard_url())
        if self.create_view:
            self.assertContains(
                response, self.get_create_url()
            )  # This is the difference to the original test function
        if self.public_list_view:
            self.assertContains(
                response, self.get_list_url(publication_status="published")
            )


# ----------- Sample utilities -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleAddPropertyViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_materialpropertyvalue"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        content_type = ContentType.objects.get_for_model(MaterialPropertyValue)
        permission, _ = Permission.objects.get_or_create(
            codename="add_materialpropertyvalue",
            content_type=content_type,
            defaults={"name": "Can add material property value"},
        )
        cls.owner.user_permissions.add(permission)
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(
            owner=cls.owner, name="Test Series", material=material
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner, name="Test Sample", material=material, series=series
        )
        cls.default_basis = MaterialComponent.objects.create(
            owner=cls.owner,
            name="Dry Matter",
        )
        cls.selected_basis = MaterialComponent.objects.create(
            owner=cls.owner,
            name="Volatile Solids",
        )
        cls.property = MaterialProperty.objects.create(
            name="Test Property",
            unit="Test Unit",
            owner=cls.owner,
            default_basis_component=cls.default_basis,
        )
        cls.unit = Unit.objects.create(name="mg/L", owner=cls.owner)
        cls.property.allowed_units.add(cls.unit)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-add-property", kwargs={"pk": self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_owners(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk})
        )
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-add-property", kwargs={"pk": self.sample.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_owners(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": MaterialProperty.objects.get(name="Test Property").pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        response = self.client.post(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk}), data
        )
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

    def test_post_creates_value_and_adds_it_to_sample(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": MaterialProperty.objects.get(name="Test Property").pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        self.client.post(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk}), data
        )
        value = MaterialPropertyValue.objects.get(
            average=Decimal("123.321"), standard_deviation=Decimal("0.1337")
        )
        self.assertEqual(value.owner, self.sample.owner)
        self.assertIn(value, self.sample.property_values.all())

    def test_post_persists_selected_unit(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": self.property.pk,
            "unit": self.unit.pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        self.client.post(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk}), data
        )
        value = MaterialPropertyValue.objects.get(
            average=Decimal("123.321"),
            standard_deviation=Decimal("0.1337"),
        )
        self.assertEqual(value.unit, self.unit)

    def test_post_defaults_basis_component_from_property(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": self.property.pk,
            "unit": self.unit.pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        self.client.post(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk}), data
        )
        value = MaterialPropertyValue.objects.get(
            average=Decimal("123.321"),
            standard_deviation=Decimal("0.1337"),
        )
        self.assertEqual(value.basis_component, self.default_basis)

    def test_post_persists_selected_basis_component(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": self.property.pk,
            "basis_component": self.selected_basis.pk,
            "unit": self.unit.pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        self.client.post(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk}), data
        )
        value = MaterialPropertyValue.objects.get(
            average=Decimal("123.321"),
            standard_deviation=Decimal("0.1337"),
        )
        self.assertEqual(value.basis_component, self.selected_basis)

    def test_get_http_403_for_non_owner_with_permission(self):
        """Non-owner with add_materialpropertyvalue should be denied (#206)."""
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_403_for_non_owner_with_permission(self):
        """Non-owner with add_materialpropertyvalue should be denied on POST (#206)."""
        self.client.force_login(self.member)
        data = {
            "property": self.property.pk,
            "average": 99.0,
            "standard_deviation": 1.0,
        }
        response = self.client.post(
            reverse("sample-add-property", kwargs={"pk": self.sample.pk}), data
        )
        self.assertEqual(response.status_code, 403)


class SampleModalAddPropertyViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_materialpropertyvalue"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        content_type = ContentType.objects.get_for_model(MaterialPropertyValue)
        permission, _ = Permission.objects.get_or_create(
            codename="add_materialpropertyvalue",
            content_type=content_type,
            defaults={"name": "Can add material property value"},
        )
        cls.owner.user_permissions.add(permission)
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(
            owner=cls.owner, name="Test Series", material=material
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner, name="Test Sample", material=material, series=series
        )
        cls.default_basis = MaterialComponent.objects.create(
            owner=cls.owner,
            name="Dry Matter",
        )
        cls.selected_basis = MaterialComponent.objects.create(
            owner=cls.owner,
            name="Volatile Solids",
        )
        cls.property = MaterialProperty.objects.create(
            name="Test Property",
            unit="Test Unit",
            owner=cls.owner,
            default_basis_component=cls.default_basis,
        )
        cls.unit = Unit.objects.create(name="g/L", owner=cls.owner)
        cls.property.allowed_units.add(cls.unit)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_owners(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(
            reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(
            reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk})
        )
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_owners(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": MaterialProperty.objects.get(name="Test Property").pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        response = self.client.post(
            reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk}), data
        )
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

    def test_post_creates_value_and_adds_it_to_sample(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": MaterialProperty.objects.get(name="Test Property").pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        self.client.post(
            reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk}), data
        )
        value = MaterialPropertyValue.objects.get(
            average=Decimal("123.321"), standard_deviation=Decimal("0.1337")
        )
        self.assertIn(value, self.sample.property_values.all())

    def test_post_persists_selected_unit(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": self.property.pk,
            "unit": self.unit.pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        self.client.post(
            reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk}), data
        )
        value = MaterialPropertyValue.objects.get(
            average=Decimal("123.321"),
            standard_deviation=Decimal("0.1337"),
        )
        self.assertEqual(value.unit, self.unit)

    def test_post_defaults_basis_component_from_property(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": self.property.pk,
            "unit": self.unit.pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        self.client.post(
            reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk}), data
        )
        value = MaterialPropertyValue.objects.get(
            average=Decimal("123.321"),
            standard_deviation=Decimal("0.1337"),
        )
        self.assertEqual(value.basis_component, self.default_basis)

    def test_post_persists_selected_basis_component(self):
        self.client.force_login(self.sample.owner)
        data = {
            "property": self.property.pk,
            "basis_component": self.selected_basis.pk,
            "unit": self.unit.pk,
            "average": 123.321,
            "standard_deviation": 0.1337,
        }
        self.client.post(
            reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk}), data
        )
        value = MaterialPropertyValue.objects.get(
            average=Decimal("123.321"),
            standard_deviation=Decimal("0.1337"),
        )
        self.assertEqual(value.basis_component, self.selected_basis)


class SampleCreateDuplicateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_sample"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        substrate_category, _ = MaterialCategory.objects.get_or_create(
            name=get_sample_substrate_category_name()
        )
        cls.material = Material.objects.create(name="Test Material")
        cls.material.categories.add(substrate_category)
        cls.series = SampleSeries.objects.create(
            name="Test Series", material=cls.material
        )
        distribution = TemporalDistribution.objects.create(name="Test Distribution")
        timestep = Timestep.objects.create(
            name="Test Timestep 1", distribution=distribution
        )
        Timestep.objects.create(name="Test Timestep 2", distribution=distribution)
        cls.sample = Sample.objects.create(
            name="Test Sample",
            material=cls.material,
            series=cls.series,
            timestep=timestep,
        )
        cls.sample.owner.user_permissions.add(
            Permission.objects.get(codename="change_sample")
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-duplicate", kwargs={"pk": self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_get_http_200_ok_for_owner(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(
            reverse("sample-duplicate", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.sample.owner)
        response = self.client.get(
            reverse("sample-duplicate", kwargs={"pk": self.sample.pk})
        )
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-duplicate", kwargs={"pk": self.sample.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_post_success_and_http_302_redirect_for_owner(self):
        self.client.force_login(self.sample.owner)
        data = {
            "name": "Test Sample Duplicate",
            "material": self.material.pk,
            "series": self.series.pk,
            "timestep": Timestep.objects.get(name="Test Timestep 2").pk,
        }
        response = self.client.post(
            reverse("sample-duplicate", kwargs={"pk": self.sample.pk}),
            data,
            follow=True,
        )
        duplicate = Sample.objects.get(name="Test Sample Duplicate")
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": duplicate.pk})
        )

    def test_newly_created_sample_has_user_as_owner(self):
        self.client.force_login(self.sample.owner)
        data = {
            "name": "Test Sample Duplicate",
            "material": self.material.pk,
            "series": self.series.pk,
            "timestep": Timestep.objects.get(name="Test Timestep 2").pk,
        }
        self.client.post(
            reverse("sample-duplicate", kwargs={"pk": self.sample.pk}), data
        )
        self.assertEqual(
            Sample.objects.get(name="Test Sample Duplicate").owner, self.sample.owner
        )


# ----------- Composition CRUD -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CompositionCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True
    modal_create_view = True
    public_list_view = False
    private_list_view = False

    model = Composition

    view_dashboard_name = "materials-explorer"
    view_create_name = "composition-create"
    view_modal_create_name = "composition-create-modal"
    view_detail_name = "composition-detail"
    view_modal_detail_name = "composition-detail-modal"
    view_update_name = "composition-update"
    view_delete_name = "composition-delete-modal"

    create_object_data = {"name": "Test Composition"}
    update_object_data = {"name": "Updated Test Composition"}

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.m2m_objects = cls.create_m2m_objects()

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(name="Test Material")
        published_sample = Sample.objects.create(
            owner=cls.owner_user,
            name="Published Test Sample",
            material=material,
            publication_status="published",
        )
        unpublished_sample = Sample.objects.create(
            owner=cls.owner_user,
            name="Private Test Sample",
            material=material,
        )
        group = MaterialComponentGroup.objects.create(name="Test Group")
        return {
            "published_sample": published_sample,
            "unpublished_sample": unpublished_sample,
            "group": group,
        }

    @classmethod
    def create_published_object(cls):
        data = cls.create_object_data.copy()
        data["publication_status"] = "published"
        data.update(
            {
                "sample": cls.related_objects["published_sample"],
                "group": cls.related_objects["group"],
            }
        )
        return cls.model.objects.create(owner=cls.owner_user, **data)

    @classmethod
    def create_unpublished_object(cls):
        data = cls.create_object_data.copy()
        data["publication_status"] = "private"
        data.update(
            {
                "sample": cls.related_objects["unpublished_sample"],
                "group": cls.related_objects["group"],
            }
        )
        return cls.model.objects.create(owner=cls.owner_user, **data)

    @classmethod
    def create_m2m_objects(cls):
        component_1 = MaterialComponent.objects.create(name="Test Component 1")
        component_2 = MaterialComponent.objects.create(name="Test Component 2")
        return {"components": {"component_1": component_1, "component_2": component_2}}

    def related_objects_post_data(self):
        return {
            "name": "Updated Test Composition",
            "sample": self.related_objects["unpublished_sample"].pk,
            "group": self.related_objects["group"].pk,
            "fractions_of": self.m2m_objects["components"]["component_1"].pk,
        }

    def _assert_create_for_owned_sample(self, url):
        sample = Sample.objects.create(
            owner=self.user_with_add_perm,
            name=f"Owned sample for {url}",
            material=self.related_objects["unpublished_sample"].material,
            standalone=True,
        )
        data = self.create_object_data.copy()
        data.update(self.related_objects_post_data())
        data["sample"] = sample.pk
        initial_count = self.model.objects.count()
        self.client.force_login(self.user_with_add_perm)

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.model.objects.count(), initial_count + 1)
        new_object = self.model.objects.latest("pk")
        self.assertEqual(new_object.owner, self.user_with_add_perm)
        self.assertEqual(new_object.sample, sample)

    def test_create_view_post_as_authenticated_with_permission(self):
        self._assert_create_for_owned_sample(self.get_create_url())

    def test_modal_create_view_post_as_authenticated_with_permission(self):
        self._assert_create_for_owned_sample(self.get_modal_create_url())

    def test_create_view_rejects_sample_user_cannot_manage(self):
        self.client.force_login(self.user_with_add_perm)
        data = self.create_object_data.copy()
        data.update(self.related_objects_post_data())

        response = self.client.post(self.get_create_url(), data)

        self.assertEqual(response.status_code, 403)

    def test_modal_create_view_rejects_sample_user_cannot_manage(self):
        self.client.force_login(self.user_with_add_perm)
        data = self.create_object_data.copy()
        data.update(self.related_objects_post_data())

        response = self.client.post(self.get_modal_create_url(), data)

        self.assertEqual(response.status_code, 403)

    def test_update_view_rejects_new_sample_user_cannot_manage(self):
        target_sample = Sample.objects.create(
            owner=self.user_with_add_perm,
            name="Unauthorized update target",
            material=self.related_objects["unpublished_sample"].material,
            standalone=True,
        )
        data = self.related_objects_post_data()
        data["sample"] = target_sample.pk
        self.client.force_login(self.owner_user)

        response = self.client.post(
            self.get_update_url(self.unpublished_object.pk),
            data,
        )

        self.assertEqual(response.status_code, 403)
        self.unpublished_object.refresh_from_db()
        self.assertEqual(
            self.unpublished_object.sample,
            self.related_objects["unpublished_sample"],
        )

    def get_update_success_url(self, pk=None):
        return reverse(
            "sample-detail",
            kwargs={"pk": self.related_objects["unpublished_sample"].pk},
        )

    def get_delete_success_url(self, publication_status=None):
        if publication_status == "private":
            return reverse(
                "sample-detail",
                kwargs={"pk": self.related_objects["unpublished_sample"].pk},
            )
        return reverse(
            "sample-detail", kwargs={"pk": self.related_objects["published_sample"].pk}
        )

    def test_detail_view_published_as_anonymous(self):
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url, follow=True)
        redirect_url = reverse(
            "sample-detail", kwargs={"pk": self.published_object.sample.pk}
        )
        self.assertRedirects(response, redirect_url)

    def test_detail_view_published_as_authenticated_owner(self):
        self.client.force_login(self.owner_user)
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url, follow=True)
        redirect_url = reverse(
            "sample-detail", kwargs={"pk": self.published_object.sample.pk}
        )
        self.assertRedirects(response, redirect_url)

    def test_detail_view_published_as_authenticated_non_owner(self):
        self.client.force_login(self.non_owner_user)
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url, follow=True)
        redirect_url = reverse(
            "sample-detail", kwargs={"pk": self.published_object.sample.pk}
        )
        self.assertRedirects(response, redirect_url)

    def test_detail_view_unpublished_as_owner(self):
        self.client.force_login(self.owner_user)
        url = self.get_detail_url(self.unpublished_object.pk)
        response = self.client.get(url, follow=True)
        redirect_url = reverse(
            "sample-detail", kwargs={"pk": self.unpublished_object.sample.pk}
        )
        self.assertRedirects(response, redirect_url)

    def test_detail_view_unpublished_as_non_owner(self):
        self.client.force_login(self.non_owner_user)
        url = self.get_detail_url(self.unpublished_object.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, self.permission_denied_message, status_code=403)

    def test_detail_view_unpublished_as_anonymous(self):
        url = self.get_detail_url(self.unpublished_object.pk)
        response = self.client.get(url)
        redirect_url = reverse(
            "composition-detail", kwargs={"pk": self.unpublished_object.pk}
        )
        self.assertRedirects(response, f"{reverse('auth_login')}?next={redirect_url}")

    def test_detail_view_nonexistent_object(self):
        url = self.get_detail_url(pk=9999)  # Assuming this PK does not exist
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


# ----------- Composition utilities ------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RemoveSeasonalVariationViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "change_composition"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(owner=cls.member, name="Test Material")
        group = MaterialComponentGroup.objects.create(
            owner=cls.member, name="Test Group"
        )
        series = SampleSeries.objects.create(
            owner=cls.member, name="Test Series", material=material
        )
        sample = Sample.objects.get(series=series, timestep=Timestep.objects.default())
        cls.composition = Composition.objects.create(
            owner=cls.member,
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default(),
        )
        cls.distribution = TemporalDistribution.objects.create(
            owner=cls.member, name="Seasons & <months>"
        )
        Timestep.objects.create(
            owner=cls.member, name="Winter", distribution=cls.distribution
        )
        cls.composition.add_temporal_distribution(cls.distribution)

    def get_url(self):
        return reverse(
            "remove_seasonal_variation",
            kwargs={
                "pk": self.composition.pk,
                "distribution_pk": self.distribution.pk,
            },
        )

    def test_confirmation_identifies_distribution_and_offers_cancel(self):
        self.client.force_login(self.member)

        response = self.client.get(self.get_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"Remove “{escape(self.distribution.name)}” from this composition?",
        )
        self.assertNotContains(response, f"Delete “{escape(str(self.composition))}”?")
        self.assertContains(
            response,
            '<button type="submit" class="btn btn-danger">Remove</button>',
            html=True,
        )
        self.assertContains(
            response,
            '<button type="button" class="btn btn-secondary" '
            'data-bs-dismiss="modal">Cancel</button>',
            html=True,
        )

    def test_get_http_404_for_unknown_distribution(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "remove_seasonal_variation",
                kwargs={"pk": self.composition.pk, "distribution_pk": 9999},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_get_http_404_for_distribution_not_used_by_the_composition(self):
        unrelated = TemporalDistribution.objects.create(
            owner=self.member, name="Unrelated distribution"
        )
        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "remove_seasonal_variation",
                kwargs={
                    "pk": self.composition.pk,
                    "distribution_pk": unrelated.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_post_removes_only_the_selected_distribution(self):
        self.client.force_login(self.member)

        response = self.client.post(self.get_url())

        self.assertRedirects(response, self.composition.get_absolute_url())
        self.assertNotIn(
            self.distribution,
            self.composition.sample.series.temporal_distributions.all(),
        )
        self.assertTrue(Composition.objects.filter(pk=self.composition.pk).exists())


class ComponentOrderUpViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "change_composition"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="Test Material")
        cls.component_group = MaterialComponentGroup.objects.create(
            owner=cls.member, name="Test Group"
        )
        cls.series = SampleSeries.objects.create(
            owner=cls.member, name="Test Series", material=material
        )
        MaterialComponent.objects.create(name="Test Component")
        cls.default_component = MaterialComponent.objects.default()
        cls.sample = Sample.objects.get(
            series=cls.series, timestep=Timestep.objects.default()
        )

    def setUp(self):
        self.composition = Composition.objects.create(
            owner=self.member,
            sample=self.sample,
            group=self.component_group,
            fractions_of=self.default_component,
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_success_and_http_302_redirect_for_owner(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        self.assertTemplateUsed("sample-detail.html")

    def test_get_success_and_http_302_redirect_for_owner_with_derived_displays(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        self.assertTemplateUsed("sample-detail.html")

    def test_get_success_and_http_302_redirect_for_owner_with_derived_composition_reorder_actions(
        self,
    ):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        self.assertTemplateUsed("sample-detail.html")

    def test_get_success_and_http_302_redirect_for_owner_with_updated_dm_basis_expectations(
        self,
    ):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        self.assertTemplateUsed("sample-detail.html")


class ComponentOrderDownViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "change_composition"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(owner=cls.member, name="Test Material")
        cls.component_group = MaterialComponentGroup.objects.create(
            owner=cls.member, name="Test Group"
        )
        cls.series = SampleSeries.objects.create(
            owner=cls.member, name="Test Series", material=material
        )
        cls.default_component = MaterialComponent.objects.default()
        cls.sample = Sample.objects.get(
            series=cls.series, timestep=Timestep.objects.default()
        )

    def setUp(self):
        self.composition = Composition.objects.create(
            owner=self.member,
            sample=self.sample,
            group=self.component_group,
            fractions_of=self.default_component,
        )
        self.component = MaterialComponent.objects.create(
            owner=self.member, name="Test Component"
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("composition-order-down", kwargs={"pk": self.composition.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("composition-order-down", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_success_and_http_302_redirect_for_owner(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("composition-order-down", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        self.assertTemplateUsed("sample-detail.html")


class DerivedCompositionOrderViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "change_composition"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(owner=cls.member, name="Test Material")
        cls.sample = Sample.objects.create(
            owner=cls.member,
            name="Sample With Derived Groups",
            material=cls.material,
            publication_status="private",
        )
        cls.sample.compositions.all().delete()

        cls.unit_percent = Unit.objects.filter(name="%").first()
        if cls.unit_percent is None:
            cls.unit_percent = Unit.objects.create(
                name="%", symbol="percent", owner=cls.member
            )
        elif not cls.unit_percent.symbol:
            cls.unit_percent.symbol = "percent"
            cls.unit_percent.save(update_fields=["symbol"])

        cls.chemical_group = MaterialComponentGroup.objects.create(
            owner=cls.member,
            name="Chemical Elements",
            publication_status="published",
        )
        cls.organic_group = MaterialComponentGroup.objects.create(
            owner=cls.member,
            name="Organic/Inorganic",
            publication_status="published",
        )
        cls.carbon = MaterialComponent.objects.create(
            owner=cls.member,
            name="Carbon",
            publication_status="published",
        )
        cls.nitrogen = MaterialComponent.objects.create(
            owner=cls.member,
            name="Nitrogen",
            publication_status="published",
        )
        cls.organic = MaterialComponent.objects.create(
            owner=cls.member,
            name="Organic matter",
            publication_status="published",
        )
        cls.ash = MaterialComponent.objects.create(
            owner=cls.member,
            name="Total Ash",
            publication_status="published",
        )

        ComponentMeasurement.objects.create(
            owner=cls.member,
            sample=cls.sample,
            group=cls.chemical_group,
            component=cls.carbon,
            unit=cls.unit_percent,
            average=Decimal("70"),
        )
        ComponentMeasurement.objects.create(
            owner=cls.member,
            sample=cls.sample,
            group=cls.chemical_group,
            component=cls.nitrogen,
            unit=cls.unit_percent,
            average=Decimal("30"),
        )
        ComponentMeasurement.objects.create(
            owner=cls.member,
            sample=cls.sample,
            group=cls.organic_group,
            component=cls.organic,
            unit=cls.unit_percent,
            average=Decimal("80"),
        )
        ComponentMeasurement.objects.create(
            owner=cls.member,
            sample=cls.sample,
            group=cls.organic_group,
            component=cls.ash,
            unit=cls.unit_percent,
            average=Decimal("20"),
        )

    def test_sample_detail_shows_reorder_links_for_derived_compositions(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk}),
            {"mode": "edit"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse(
                "derived-composition-order-down",
                kwargs={"sample_pk": self.sample.pk, "group_pk": self.organic_group.pk},
            ),
        )
        self.assertContains(
            response,
            reverse(
                "derived-composition-order-up",
                kwargs={"sample_pk": self.sample.pk, "group_pk": self.organic_group.pk},
            ),
        )

    def test_order_down_creates_settings_and_moves_derived_group_left(self):
        self.client.force_login(self.member)

        initial_response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        initial_content = initial_response.content.decode()
        self.assertLess(
            initial_content.index(f'id="group-{self.chemical_group.pk}"'),
            initial_content.index(f'id="group-{self.organic_group.pk}"'),
        )

        response = self.client.get(
            reverse(
                "derived-composition-order-down",
                kwargs={"sample_pk": self.sample.pk, "group_pk": self.organic_group.pk},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.sample.compositions.count(), 2)

        reordered_response = self.client.get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        reordered_content = reordered_response.content.decode()
        self.assertLess(
            reordered_content.index(f'id="group-{self.organic_group.pk}"'),
            reordered_content.index(f'id="group-{self.chemical_group.pk}"'),
        )


# ----------- Materials/Components/Groups Relations --------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AddCompositionViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_composition"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="Test Material")
        cls.component_group = MaterialComponentGroup.objects.create(name="Test Group")
        cls.series = SampleSeries.objects.create(
            owner=cls.member, name="Test Series", material=material
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk})
        )
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            "group": self.component_group.pk,
            "fractions_of": MaterialComponent.objects.default().pk,
        }
        response = self.client.post(
            reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk}), data
        )
        self.assertRedirects(
            response, reverse("sampleseries-detail", kwargs={"pk": self.series.pk})
        )

    def test_post_adds_group_and_weight_shares_to_sample_series(self):
        self.client.force_login(self.member)
        data = {
            "group": self.component_group.pk,
            "fractions_of": MaterialComponent.objects.default().pk,
        }
        self.client.post(
            reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk}), data
        )
        for sample in self.series.samples.all():
            Composition.objects.get(sample=sample, group=self.component_group)


class SampleAddCompositionViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_composition"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="Test Material for Sample Composition")
        cls.component_group = MaterialComponentGroup.objects.create(
            name="Test Group for Sample Composition"
        )
        series = SampleSeries.objects.create(
            owner=cls.member, name="Test Series", material=material
        )
        cls.sample = Sample.objects.create(
            owner=cls.member, series=series, material=material
        )
        cls.other_users_sample = Sample.objects.create(
            owner=cls.owner,
            name="Other user's sample",
            standalone=True,
            material=material,
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-add-composition", kwargs={"pk": self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("sample-add-composition", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("sample-add-composition", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_get_does_not_crash_when_get_sample_called_multiple_times(self):
        # Regression test for #102: get_sample() was non-idempotent and returned
        # None on the second call (from get_initial()), causing the form to crash.
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("sample-add-composition", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="submit"')

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-add-composition", kwargs={"pk": self.sample.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("sample-add-composition", kwargs={"pk": self.sample.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_forbidden_for_non_owner_with_add_permission(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "sample-add-composition",
                kwargs={"pk": self.other_users_sample.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_post_forbidden_for_non_owner_with_add_permission(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse(
                "sample-add-composition",
                kwargs={"pk": self.other_users_sample.pk},
            ),
            {
                "sample": self.other_users_sample.pk,
                "group": self.component_group.pk,
                "fractions_of": MaterialComponent.objects.default().pk,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Composition.objects.filter(
                sample=self.other_users_sample,
                group=self.component_group,
            ).exists()
        )

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {
            "sample": self.sample.pk,
            "group": self.component_group.pk,
            "fractions_of": MaterialComponent.objects.default().pk,
        }
        response = self.client.post(
            reverse("sample-add-composition", kwargs={"pk": self.sample.pk}), data
        )
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

    def test_post_creates_composition_for_sample(self):
        self.client.force_login(self.member)
        data = {
            "sample": self.sample.pk,
            "group": self.component_group.pk,
            "fractions_of": MaterialComponent.objects.default().pk,
        }
        self.client.post(
            reverse("sample-add-composition", kwargs={"pk": self.sample.pk}), data
        )
        self.assertTrue(
            Composition.objects.filter(
                sample=self.sample, group=self.component_group
            ).exists()
        )


class EmptyStateViewsTestCase(TestCase):
    """Test empty state messaging and CTAs across Materials views."""

    def setUp(self):
        self.regular_user = User.objects.create_user(
            username="regular", password="test123"
        )
        self.staff_user = User.objects.create_user(
            username="staff", password="test123", is_staff=True
        )

        content_types = {
            "material": ContentType.objects.get_for_model(Material),
            "sample": ContentType.objects.get_for_model(Sample),
            "sampleseries": ContentType.objects.get_for_model(SampleSeries),
            "materialcategory": ContentType.objects.get_for_model(MaterialCategory),
            "materialcomponent": ContentType.objects.get_for_model(MaterialComponent),
            "materialcomponentgroup": ContentType.objects.get_for_model(
                MaterialComponentGroup
            ),
            "materialproperty": ContentType.objects.get_for_model(MaterialProperty),
            "analyticalmethod": ContentType.objects.get_for_model(AnalyticalMethod),
        }

        for model_name, ct in content_types.items():
            perm, _ = Permission.objects.get_or_create(
                codename=f"add_{model_name}",
                content_type=ct,
            )
            self.staff_user.user_permissions.add(perm)

    def _create_unused_category(self):
        """Create a category guaranteed not to be assigned in this test."""
        return MaterialCategory.objects.create(
            name=f"unused-category-{uuid4()}",
            owner=self.staff_user,
            publication_status="published",
        )

    def test_material_list_empty_anonymous_shows_login_hint(self):
        category = self._create_unused_category()
        response = self.client.get(
            reverse("material-list") + f"?scope=published&category={category.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")
        self.assertContains(response, "Log in to enable export and additional options.")
        self.assertNotContains(response, "Create new material")

    def test_material_list_empty_staff_shows_create_cta(self):
        self.client.force_login(self.staff_user)
        category = self._create_unused_category()
        response = self.client.get(
            reverse("material-list-owned") + f"?scope=private&category={category.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")
        self.assertContains(response, "Create new material")
        self.assertNotContains(response, "Log in to create")

    def test_material_list_empty_regular_no_create_cta(self):
        self.client.force_login(self.regular_user)
        category = self._create_unused_category()
        response = self.client.get(
            reverse("material-list-owned") + f"?scope=private&category={category.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")
        self.assertNotContains(response, "Create your first material")
        self.assertNotContains(response, "Log in to create")

    def test_material_review_list_renders_filter_context_for_staff(self):
        Material.objects.create(
            name="Review Material",
            type="material",
            owner=self.regular_user,
            publication_status="review",
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("material-list-review"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(f"{reverse('material-list-review')}?scope=review", 302)],
        )
        self.assertContains(response, "Reset filters")
        self.assertContains(response, "Review Material")

    def test_sample_detail_empty_properties_anonymous(self):
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No properties yet")
        self.assertContains(response, "Properties")
        self.assertContains(
            response,
            "Add measurements such as moisture, density, pH, or other sample properties",
        )
        self.assertNotContains(response, "Add the first property")

    def test_sample_detail_empty_properties_owner_sees_actionable_message(self):
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.regular_user,
            publication_status="published",
        )
        content_type = ContentType.objects.get_for_model(MaterialPropertyValue)
        permission, _ = Permission.objects.get_or_create(
            codename="add_materialpropertyvalue",
            content_type=content_type,
            defaults={"name": "Can add material property value"},
        )
        self.regular_user.user_permissions.add(permission)
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No properties yet")
        self.assertContains(response, "Add the first property")

    def test_sample_detail_shows_sample_identity_block_and_summary(self):
        sample = Sample.objects.create(
            name="Spruce Sample",
            material=Material.objects.create(name="Wood chips", type="material"),
            owner=self.regular_user,
            location="Hamburg",
            publication_status="published",
        )
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sdv2-hero')
        self.assertContains(response, "Spruce Sample")
        self.assertContains(response, "Wood chips")
        self.assertContains(response, "Hamburg")
        self.assertContains(response, "Composition")
        self.assertContains(response, "Properties")
        self.assertNotContains(response, "sdv2-hero-stats")

    def test_sample_detail_v2_flag_renders_prototype_template(self):
        sample = Sample.objects.create(
            name="Prototype Sample",
            material=Material.objects.create(name="Proto Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "materials/sample_detail_v2.html")
        self.assertContains(response, 'class="sdv2"')

    def test_sample_detail_uses_v2_by_default(self):
        sample = Sample.objects.create(
            name="Default Sample",
            material=Material.objects.create(name="Default Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "materials/sample_detail_v2.html")
        self.assertContains(response, 'class="sdv2"')

    def test_sample_detail_classic_flag_falls_forward_to_v2_after_retirement(self):
        sample = Sample.objects.create(
            name="Classic Sample",
            material=Material.objects.create(name="Classic Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=classic"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "materials/sample_detail_v2.html")
        self.assertTemplateNotUsed(response, "materials/sample_detail.html")
        self.assertContains(response, 'class="sdv2"')
        self.assertNotContains(response, "Classic view")

    def test_sampled_metadata_omits_unknown_time_for_legacy_dates(self):
        sample = self._create_v2_public_sample_with_metadata()
        sample.datetime = timezone.make_aware(
            datetime(2024, 8, 27), timezone.get_default_timezone()
        )
        sample.save()

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertContains(response, '<span class="sdv2-meta-label">Sampled</span>')
        self.assertContains(
            response, '<time datetime="2024-08-27">27 Aug 2024</time>', html=True
        )
        self.assertNotContains(response, '<span class="sdv2-meta-label">When</span>')

    def test_sampled_metadata_matches_explicit_precision(self):
        sample = self._create_v2_public_sample_with_metadata()
        for precision, value, markup in (
            ("year", datetime(2024, 1, 1), "<span>2024</span>"),
            (
                "date",
                datetime(2024, 8, 27),
                '<time datetime="2024-08-27">27 Aug 2024</time>',
            ),
            (
                "time",
                datetime(2024, 8, 27, 14, 30),
                '<time datetime="2024-08-27 14:30">27 Aug 2024, 14:30</time>',
            ),
            (
                "time",
                datetime(2024, 8, 27),
                '<time datetime="2024-08-27 00:00">27 Aug 2024, 00:00</time>',
            ),
        ):
            with self.subTest(precision=precision, value=value):
                sample.datetime = timezone.make_aware(
                    value, timezone.get_default_timezone()
                )
                sample.datetime_precision = precision
                sample.save()
                response = self.client.get(
                    reverse("sample-detail", kwargs={"pk": sample.pk})
                )
                self.assertContains(response, markup, html=True)
                self.assertContains(
                    response, '<span class="sdv2-meta-label">Sampled</span>'
                )
                if precision == "year":
                    self.assertNotContains(response, 'datetime="2024-01-01')

    def test_unknown_sampling_date_omits_sampled_metadata(self):
        sample = self._create_v2_public_sample_with_metadata()
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertNotContains(response, '<span class="sdv2-meta-label">Sampled</span>')

    def test_sampling_precision_is_displayed_in_list_and_gallery(self):
        sample = self._create_v2_public_sample_with_metadata()
        sample.image = "materials_sample/dated-sample.jpg"
        for precision, value, display in (
            ("year", datetime(2024, 1, 1), "2024"),
            ("date", datetime(2024, 8, 27), "27 Aug 2024"),
            ("time", datetime(2024, 8, 27, 14, 30), "27 Aug 2024, 14:30"),
        ):
            sample.datetime = timezone.make_aware(
                value, timezone.get_default_timezone()
            )
            sample.datetime_precision = precision
            sample.save()
            for route in ("sample-list", "sample-gallery"):
                with self.subTest(route=route, precision=precision):
                    response = self.client.get(reverse(route), {"scope": "published"})
                    self.assertContains(response, sample.name)
                    self.assertContains(response, display)
                    if precision == "year":
                        self.assertNotContains(response, "2024-01-01")

    def _create_v2_owner_sample(self, name, status):
        owner = User.objects.create_user(username=f"{name}-owner", password="test123")
        return Sample.objects.create(
            name=name,
            material=Material.objects.create(name=f"{name} Material", type="material"),
            owner=owner,
            publication_status=status,
        ), owner

    def test_v2_hero_distinguishes_sampling_and_analysis_time(self):
        sample, owner = self._create_v2_owner_sample("V2 Times", "private")
        sample.datetime = timezone.make_aware(datetime(2024, 3, 5, 9, 30))
        sample.analysis_date = timezone.make_aware(datetime(2024, 4, 12, 14, 0))
        sample.save()
        self.client.force_login(owner)
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<span class="sdv2-meta-label">Sampled</span>')
        self.assertContains(response, "5 Mar 2024, 09:30")
        self.assertContains(response, '<span class="sdv2-meta-label">Analysed</span>')
        self.assertContains(response, "2024-04-12 14:00")
        self.assertNotContains(response, '<span class="sdv2-meta-label">When</span>')

    def test_v2_private_sample_edit_mode_shows_submit_for_review(self):
        sample, owner = self._create_v2_owner_sample("V2 Private", "private")
        self.client.force_login(owner)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk})
            + "?experience=v2&mode=edit"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "materials/sample_detail_v2.html")
        self.assertContains(response, "Submit for review")
        self.assertContains(response, "submit-for-review")

    def test_v2_declined_sample_shows_review_feedback_entry(self):
        sample, owner = self._create_v2_owner_sample("V2 Declined", "declined")
        self.client.force_login(owner)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review feedback")

    def test_v2_edit_mode_offers_delete_in_actions_menu(self):
        sample, owner = self._create_v2_owner_sample("V2 Delete", "private")
        self.client.force_login(owner)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk})
            + "?experience=v2&mode=edit"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "sdv2-rail-delete")
        self.assertContains(response, "delete/modal")

    def test_v2_does_not_render_disabled_compare_stub(self):
        sample = Sample.objects.create(
            name="No Stub Sample",
            material=Material.objects.create(name="Stub Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Compare mode (coming soon)")

    def _create_v2_public_sample_with_metadata(self):
        return Sample.objects.create(
            name="Minimal Sample",
            material=Material.objects.create(name="Minimal Material", type="material"),
            owner=self.staff_user,
            location="Hamburg",
            description="A publicly visible sample record.",
            analysis_laboratory="TUHH Lab",
            publication_status="published",
        )

    def test_v2_anonymous_gets_minimal_layout_without_editorial_chrome(self):
        sample = self._create_v2_public_sample_with_metadata()
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "materials/sample_detail_v2.html")
        # Editorial chrome: action rail, hero stats, completeness strip,
        # provenance timeline, and command palette are owner/editor tools.
        self.assertNotContains(response, "sdv2-rail")
        self.assertNotContains(response, "sdv2-hero-stats")
        self.assertNotContains(response, "sdv2-completeness")
        self.assertNotContains(response, "sdv2-timeline")
        self.assertNotContains(response, "sdv2-palette")
        self.assertNotContains(response, "Quick actions")

    def test_v2_anonymous_still_sees_data_and_metadata(self):
        sample = self._create_v2_public_sample_with_metadata()
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        # Identity + metadata.
        self.assertContains(response, "Minimal Sample")
        self.assertContains(response, "Minimal Material")
        self.assertContains(response, "Hamburg")
        self.assertContains(response, "TUHH Lab")
        # The actual data sections remain.
        self.assertContains(response, "sdv2-properties")
        self.assertContains(response, "Composition")
        # An empty related-samples rail does not take space from the data.
        self.assertNotContains(response, "sdv2-related")
        self.assertContains(response, "sdv2-layout-full")

    def test_v2_uses_one_visual_canvas_and_consistent_section_surfaces(self):
        sample, _group = self._create_sample_with_composition_and_property()
        sample.description = "A sample with a complete reading surface."
        sample.save(update_fields=["description"])

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sdv2-canvas sdv2-canvas-fluid"')
        self.assertContains(response, "sdv2-hero sdv2-surface")
        self.assertContains(response, "sdv2-about sdv2-section-panel")
        self.assertContains(response, "sdv2-group-card sdv2-surface")
        self.assertContains(response, "sdv2-properties sdv2-section-panel")
        self.assertContains(
            response,
            'class="sdv2-raw-component"',
            count=sample.component_measurements.count(),
        )

    def test_v2_keeps_related_rail_when_related_samples_exist(self):
        sample = self._create_v2_public_sample_with_metadata()
        related_sample = Sample.objects.create(
            name="Related material sample",
            material=sample.material,
            owner=self.staff_user,
            publication_status="published",
        )

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sdv2-related"')
        self.assertNotContains(response, "sdv2-layout-full")
        self.assertContains(response, related_sample.name)

    def test_v2_renders_uploaded_sample_image_in_hero(self):
        sample = self._create_v2_public_sample_with_metadata()
        sample.image = SimpleUploadedFile(
            "sample-photo.jpg",
            b"sample image content",
            content_type="image/jpeg",
        )
        sample.image_alt_text = "Close-up of roadside pruning wood"
        sample.image_caption = "Sample after size reduction"
        sample.image_rights_notice = "CC BY 4.0"
        sample.save()

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sdv2-hero-with-media")
        self.assertContains(response, "sdv2-hero-media")
        self.assertContains(response, sample.display_image.url)
        self.assertContains(response, sample.display_image_alt_text)
        self.assertContains(response, sample.display_image_caption)
        self.assertContains(response, sample.display_image_rights_notice)

    def test_v2_hero_collapses_when_sample_has_no_display_image(self):
        sample = self._create_v2_public_sample_with_metadata()

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sdv2-hero-no-media")
        self.assertNotContains(response, "sdv2-hero-media")

    def test_v2_uses_series_image_as_hero_fallback(self):
        material = Material.objects.create(
            name="Series image material",
            type="material",
            owner=self.staff_user,
            publication_status="published",
        )
        series = SampleSeries.objects.create(
            name="Series with image",
            material=material,
            owner=self.staff_user,
            publication_status="published",
            image=SimpleUploadedFile(
                "series-photo.jpg",
                b"series image content",
                content_type="image/jpeg",
            ),
            image_alt_text="Representative image for the sample series",
        )
        sample = self._create_v2_public_sample_with_metadata()
        sample.series = series
        sample.save(update_fields=["series"])

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, series.image.url)
        self.assertContains(response, series.image_alt_text)
        self.assertContains(response, "Showing the image from the linked sample series")
        self.assertContains(
            response,
            f'<a href="{reverse("sampleseries-detail", kwargs={"pk": series.pk})}">'
            f"{series.name}</a>",
            html=True,
        )

    def test_v2_uses_single_contextual_edit_mode_action(self):
        sample = self._create_v2_public_sample_with_metadata()
        self.client.force_login(self.staff_user)

        explore_response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        edit_response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk})
            + "?experience=v2&mode=edit"
        )

        self.assertNotContains(explore_response, "sdv2-mode-toggle")
        self.assertContains(explore_response, "sdv2-mode-action")
        self.assertContains(explore_response, "?mode=edit")
        self.assertContains(explore_response, "Edit")
        self.assertContains(edit_response, "sdv2-editing-state")
        self.assertContains(
            edit_response,
            f'sdv2-mode-action" href="{reverse("sample-detail", kwargs={"pk": sample.pk})}"',
        )
        self.assertContains(edit_response, "Done")

    def test_sample_toolbar_separates_navigation_status_and_actions(self):
        sample = self._create_v2_public_sample_with_metadata()
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertContains(response, 'aria-label="Sample toolbar"')
        self.assertContains(response, 'aria-label="Sample status"')
        self.assertContains(response, 'aria-label="Sample actions"')
        self.assertContains(response, "Edit sample")
        self.assertContains(response, "More actions")
        content = response.content.decode()
        self.assertLess(
            content.index('aria-label="Sample navigation"'),
            content.index('aria-label="Sample status"'),
        )
        self.assertLess(
            content.index("sdv2-actions-trigger"), content.index("sdv2-mode-action")
        )

    def test_sample_toolbar_edit_state_is_not_styled_as_a_button(self):
        sample = self._create_v2_public_sample_with_metadata()
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}), {"mode": "edit"}
        )

        self.assertContains(
            response,
            '<span class="sdv2-editing-state">'
            '<i class="fas fa-pen-to-square" aria-hidden="true"></i>'
            "Editing sample</span>",
            html=True,
        )
        self.assertContains(response, "Done editing")
        self.assertNotContains(response, 'aria-label="Edit mode"')

    def test_sample_navigation_uses_links_not_toggle_buttons(self):
        sample = self._create_v2_public_sample_with_metadata()
        url = reverse("sample-detail", kwargs={"pk": sample.pk})
        for authenticated in (False, True):
            with self.subTest(authenticated=authenticated):
                if authenticated:
                    self.client.force_login(self.staff_user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                navigation = (
                    response.content.decode()
                    .split('aria-label="Sample navigation">', 1)[1]
                    .split("</nav>", 1)[0]
                )
                self.assertNotIn('role="button"', navigation)
                self.assertNotIn("aria-pressed", navigation)
                for route, label in (
                    ("sample-list", "All samples"),
                    ("sample-gallery", "Featured samples"),
                    ("materials-explorer", "Materials explorer"),
                ):
                    self.assertIn(reverse(route), navigation)
                    self.assertIn(label, navigation)

    def test_v2_explore_mode_is_decluttered_for_authenticated_users(self):
        sample = self._create_v2_public_sample_with_metadata()
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        # Reading layout: stats, sparkband, completeness, and timeline are
        # noise on top of data that is already visible as cards and tables.
        self.assertNotContains(response, "sdv2-hero-stats")
        self.assertNotContains(response, "sdv2-sparkband")
        self.assertNotContains(response, "sdv2-completeness")
        self.assertNotContains(response, "sdv2-timeline")
        # Data and metadata still dominate.
        self.assertContains(response, "TUHH Lab")
        self.assertContains(response, "sdv2-properties")

    def test_v2_edit_mode_exposes_editorial_sections(self):
        owner = User.objects.create_user(username="editorial-owner", password="test123")
        change_perm, _ = Permission.objects.get_or_create(
            codename="change_sample",
            content_type=ContentType.objects.get_for_model(Sample),
            defaults={"name": "Can change sample"},
        )
        owner.user_permissions.add(change_perm)
        sample = Sample.objects.create(
            name="Editorial Sample",
            material=Material.objects.create(
                name="Editorial Material", type="material"
            ),
            owner=owner,
            publication_status="private",
        )
        self.client.force_login(owner)
        explore_response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertNotContains(explore_response, "sdv2-completeness")
        self.assertNotContains(explore_response, "sdv2-timeline")

        edit_response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk})
            + "?experience=v2&mode=edit"
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, "sdv2-completeness")
        self.assertContains(edit_response, "sdv2-timeline")

    def test_v2_edit_mode_exposes_composition_creation_actions(self):
        sample, _group = self._create_sample_with_composition_and_property()
        for model, codename in (
            (ComponentMeasurement, "add_componentmeasurement"),
            (Composition, "add_composition"),
        ):
            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=ContentType.objects.get_for_model(model),
                defaults={"name": f"Can {codename.replace('_', ' ')}"},
            )
            self.staff_user.user_permissions.add(permission)
        self.client.force_login(self.staff_user)
        base_url = reverse("sample-detail", kwargs={"pk": sample.pk})

        explore_response = self.client.get(base_url + "?experience=v2")
        edit_response = self.client.get(base_url + "?experience=v2&mode=edit")

        self.assertNotContains(explore_response, "sdv2-composition-actions")
        self.assertContains(edit_response, "sdv2-composition-actions")
        self.assertContains(edit_response, "Add measurement")
        self.assertContains(edit_response, "Add composition")
        self.assertContains(
            edit_response,
            f"{reverse('componentmeasurement-create')}?sample={sample.pk}",
        )
        self.assertContains(
            edit_response,
            reverse("sample-add-composition", kwargs={"pk": sample.pk}),
        )
        self.assertEqual(
            self.client.get(
                reverse("componentmeasurement-create") + f"?sample={sample.pk}"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("sample-add-composition", kwargs={"pk": sample.pk})
            ).status_code,
            200,
        )

    def test_v2_superuser_can_add_data_to_published_sample(self):
        sample, _group = self._create_sample_with_composition_and_property()
        superuser = User.objects.create_superuser(
            username="sample-superuser", password="test123"
        )
        self.client.force_login(superuser)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk})
            + "?experience=v2&mode=edit"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sdv2-composition-actions")
        self.assertContains(response, "Add measurement")
        self.assertContains(response, "Add composition")

    def test_v2_edit_mode_exposes_all_sample_data_management_actions(self):
        sample, group = self._create_sample_with_composition_and_property()
        setting = Composition.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default(),
        )
        prop = sample.property_values.get()
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?mode=edit"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse(
                "derived-composition-order-down",
                kwargs={"sample_pk": sample.pk, "group_pk": group.pk},
            ),
        )
        self.assertContains(
            response,
            reverse(
                "derived-composition-order-up",
                kwargs={"sample_pk": sample.pk, "group_pk": group.pk},
            ),
        )
        self.assertContains(
            response, reverse("composition-update", kwargs={"pk": setting.pk})
        )
        self.assertContains(
            response,
            reverse("composition-delete-modal", kwargs={"pk": setting.pk}),
        )
        self.assertContains(
            response,
            reverse("materialpropertyvalue-delete-modal", kwargs={"pk": prop.pk}),
        )
        self.assertContains(response, "Manage access")
        self.assertContains(response, "object_management/modal/manage-access")

    def test_v2_modal_actions_are_wired_as_modal_links(self):
        sample = self._create_v2_public_sample_with_metadata()
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?mode=edit"
        )

        self.assertContains(
            response,
            'class="dropdown-item text-danger modal-link"',
            html=False,
        )

    def test_v2_in_review_sample_links_to_review_workspace(self):
        sample, owner = self._create_v2_owner_sample("V2 Review", "review")
        self.client.force_login(owner)
        review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Sample).pk,
                "object_id": sample.pk,
            },
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertContains(response, "Review view")
        self.assertContains(response, review_url)

    def test_v2_review_query_renders_embedded_review_panel(self):
        sample, owner = self._create_v2_owner_sample("V2 Panel", "review")
        self.client.force_login(owner)

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?review=1"
        )

        self.assertContains(response, 'id="review-panel"')

    def test_v2_preserves_full_provenance_and_measurement_context(self):
        sample, _group = self._create_sample_with_composition_and_property()
        sample.datetime = timezone.make_aware(datetime(2026, 8, 27, 14, 35))
        sample.lab_accreditation = "ISO/IEC 17025"
        sample.analysis_objective = "Determine suitability for fibre recovery."
        sample.save()
        sources = [
            Source.objects.create(
                abbreviation=f"SRC-{index}",
                title=f"Source {index}",
                owner=self.staff_user,
                publication_status="published",
            )
            for index in (1, 2)
        ]
        sample.sources.set(sources)
        measurement = sample.component_measurements.order_by("pk").first()
        measurement.component.abbreviation = "CELL"
        measurement.component.save(update_fields=["abbreviation"])
        measurement.comment = "Measured after conditioning."
        measurement.save(update_fields=["comment"])

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertContains(response, "14:35")
        self.assertContains(response, "ISO/IEC 17025")
        self.assertContains(response, "Determine suitability for fibre recovery.")
        self.assertContains(response, "CELL")
        self.assertContains(response, "Measured after conditioning.")
        for source in sources:
            self.assertContains(
                response, reverse("source-detail-modal", kwargs={"pk": source.pk})
            )

    def test_v2_preserves_navigation_and_raw_group_controls(self):
        sample, _group = self._create_sample_with_composition_and_property()
        back_url = reverse("sample-list") + "?scope=published"

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}),
            {"back": back_url},
        )

        self.assertContains(response, back_url.replace("&", "&amp;"))
        self.assertContains(response, reverse("sample-list"))
        self.assertContains(response, reverse("sample-gallery"))
        self.assertContains(response, reverse("materials-explorer"))
        self.assertContains(response, 'data-sdv2-raws-toggle="expand"')
        self.assertContains(response, 'data-sdv2-raws-toggle="collapse"')

    def test_v2_export_lives_in_actions_dropdown_not_rail_button(self):
        sample = self._create_v2_public_sample_with_metadata()
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "sdv2-export-trigger")
        self.assertContains(response, "Export sample to Excel")
        self.assertContains(
            response, reverse("sample-export", kwargs={"pk": sample.pk})
        )

    def test_sample_detail_shows_section_intro_and_quick_nav(self):
        sample = Sample.objects.create(
            name="Navigable Sample",
            material=Material.objects.create(
                name="Navigable Material", type="material"
            ),
            owner=self.staff_user,
            publication_status="published",
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sdv2-context-nav")
        self.assertContains(response, "All samples")
        self.assertContains(response, "Featured")
        self.assertContains(response, "Materials explorer")

        # The command palette and classic fallback are retired; secondary
        # actions live in the conventional Bootstrap dropdown in the rail.
        self.client.force_login(self.staff_user)
        v2_response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk})
        )
        self.assertEqual(v2_response.status_code, 200)
        self.assertNotContains(v2_response, "Quick actions")
        self.assertNotContains(v2_response, "sdv2Palette")
        self.assertNotContains(v2_response, "Classic view")

    def test_v2_rail_actions_dropdown_carries_secondary_editorial_actions(self):
        owner = User.objects.create_user(username="dropdown-owner", password="test123")
        sample = Sample.objects.create(
            name="Dropdown Sample",
            material=Material.objects.create(name="Dropdown Material", type="material"),
            owner=owner,
            publication_status="private",
        )
        add_perm, _ = Permission.objects.get_or_create(
            codename="add_sample",
            content_type=ContentType.objects.get_for_model(Sample),
            defaults={"name": "Can add sample"},
        )
        change_perm, _ = Permission.objects.get_or_create(
            codename="change_sample",
            content_type=ContentType.objects.get_for_model(Sample),
            defaults={"name": "Can change sample"},
        )
        owner.user_permissions.add(add_perm, change_perm)
        self.client.force_login(owner)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sdv2-actions-menu")
        self.assertContains(
            response, reverse("sample-duplicate", kwargs={"pk": sample.pk})
        )
        self.assertContains(response, "Edit sample metadata")

    def test_v2_anonymous_gets_no_actions_dropdown(self):
        sample = Sample.objects.create(
            name="Anon Dropdown Sample",
            material=Material.objects.create(
                name="Anon Dropdown Material", type="material"
            ),
            owner=self.staff_user,
            publication_status="published",
        )
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "sdv2-actions-menu")

    def _create_sample_with_composition_and_property(self):
        sample = Sample.objects.create(
            name="Anchor Sample",
            material=Material.objects.create(name="Anchor Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        group = MaterialComponentGroup.objects.create(
            owner=self.staff_user,
            name="Wood chemistry",
            publication_status="published",
        )
        cellulose = MaterialComponent.objects.create(
            owner=self.staff_user,
            name="Cellulose",
            publication_status="published",
        )
        lignin = MaterialComponent.objects.create(
            owner=self.staff_user,
            name="Lignin",
            publication_status="published",
        )
        unit_percent = Unit.objects.filter(name="%").first()
        if unit_percent is None:
            unit_percent = Unit.objects.create(
                name="%", symbol="percent", owner=self.staff_user
            )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=cellulose,
            unit=unit_percent,
            average=Decimal("60.0"),
        )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=lignin,
            unit=unit_percent,
            average=Decimal("30.0"),
        )
        moisture = MaterialProperty.objects.create(
            owner=self.staff_user,
            name="Moisture",
            publication_status="published",
        )
        MaterialPropertyValue.objects.create(
            owner=self.staff_user,
            sample=sample,
            property=moisture,
            average=Decimal("12.0"),
            publication_status="published",
        )
        return sample, group

    def test_v2_anchor_nav_links_sections_for_all_users(self):
        sample, group = self._create_sample_with_composition_and_property()
        url = reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        anonymous_response = self.client.get(url)
        self.assertEqual(anonymous_response.status_code, 200)
        self.assertContains(anonymous_response, "sdv2-anchor-nav")
        self.assertContains(anonymous_response, f"#group-{group.pk}")
        self.assertContains(anonymous_response, "#properties")
        self.assertNotContains(anonymous_response, "sdv2-anchor-share")
        self.assertContains(anonymous_response, 'data-has-action-rail="0"')
        self.assertContains(anonymous_response, "sdv2-anchor-target", count=2)
        self.assertEqual(
            anonymous_response.context["group_anchors"],
            [{"group_id": group.pk, "name": "Wood chemistry"}],
        )

        self.client.force_login(self.staff_user)
        authenticated_response = self.client.get(url)
        self.assertEqual(authenticated_response.status_code, 200)
        self.assertContains(authenticated_response, 'data-has-action-rail="1"')

    def test_v2_anchor_nav_omitted_when_single_section(self):
        sample = Sample.objects.create(
            name="Single Section Sample",
            material=Material.objects.create(
                name="Single Section Material", type="material"
            ),
            owner=self.staff_user,
            publication_status="published",
        )
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "sdv2-anchor-nav")

    def test_v2_hides_total_material_composition_without_removing_data(self):
        sample = Sample.objects.create(
            name="Hierarchy Sample",
            material=Material.objects.create(
                name="Hierarchy Material", type="material"
            ),
            owner=self.staff_user,
            publication_status="published",
        )
        default_group = MaterialComponentGroup.objects.default()
        default_component = MaterialComponent.objects.default()
        visible_group = MaterialComponentGroup.objects.create(
            owner=self.staff_user,
            name="Wood chemistry",
            publication_status="published",
        )
        cellulose = MaterialComponent.objects.create(
            owner=self.staff_user,
            name="Cellulose for hierarchy test",
            publication_status="published",
        )
        unit_percent = Unit.objects.filter(name="%").first()
        if unit_percent is None:
            unit_percent = Unit.objects.create(
                name="%", symbol="percent", owner=self.staff_user
            )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=default_group,
            component=default_component,
            unit=unit_percent,
            average=Decimal("100.0"),
        )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=visible_group,
            component=cellulose,
            unit=unit_percent,
            average=Decimal("100.0"),
        )

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )

        self.assertEqual(response.status_code, 200)
        all_compositions = response.context["data"]["compositions"]
        self.assertEqual(
            {composition["group"] for composition in all_compositions},
            {default_group.pk, visible_group.pk},
        )
        self.assertEqual(
            [
                composition["group"]
                for composition in response.context["display_compositions"]
            ],
            [visible_group.pk],
        )
        self.assertNotContains(response, f'id="group-{default_group.pk}"')
        self.assertNotContains(response, f'href="#group-{default_group.pk}"')
        self.assertContains(response, f'id="group-{visible_group.pk}"')
        self.assertNotIn(
            f"composition-chart-derived-{sample.pk}-{default_group.pk}",
            response.context["charts"],
        )

    def test_v2_omits_composition_section_when_only_total_material_exists(self):
        sample = Sample.objects.create(
            name="Root-only Sample",
            material=Material.objects.create(
                name="Root-only Material", type="material"
            ),
            owner=self.staff_user,
            publication_status="published",
        )
        default_group = MaterialComponentGroup.objects.default()
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=default_group,
            component=MaterialComponent.objects.default(),
            unit=Unit.objects.filter(name="%").first(),
            average=Decimal("100.0"),
        )

        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?experience=v2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["data"]["compositions"])
        self.assertEqual(response.context["display_compositions"], [])
        self.assertNotContains(response, 'aria-label="Composition groups"')
        self.assertNotContains(response, "No composition data yet")

    def test_sample_detail_shows_sample_sources_as_badge_links(self):
        sample = Sample.objects.create(
            name="Sourced Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        source = Source.objects.create(
            abbreviation="SRC-1",
            title="Sample Source",
            owner=self.staff_user,
            publication_status="published",
        )
        sample.sources.add(source)

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("source-detail-modal", kwargs={"pk": source.pk}),
        )
        self.assertContains(response, "SRC-1")
        self.assertContains(response, "sdv2-source-chip")

    def test_sample_detail_private_owner_sees_workspace_panels(self):
        sample = Sample.objects.create(
            name="Workspace Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.regular_user,
            publication_status="private",
        )

        self.client.force_login(self.regular_user)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?mode=edit"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editing")
        self.assertContains(response, "sdv2-completeness")
        self.assertContains(response, "sdv2-timeline")
        self.assertContains(response, "Submit for review")
        self.assertContains(response, "Manage access")
        self.assertContains(response, "Description present")

    def test_sample_detail_empty_mass_measurements_anonymous(self):
        sample = Sample.objects.create(
            name="Massless Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        sample.compositions.all().delete()

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No composition data yet")
        self.assertContains(
            response,
            "Composition groups appear here once component measurements can be normalized",
        )
        self.assertNotContains(
            response,
            f"{reverse('componentmeasurement-create')}?sample={sample.pk}",
        )

    def test_sample_detail_empty_mass_measurements_owner_sees_cta_with_permission(self):
        sample = Sample.objects.create(
            name="Massless Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.regular_user,
            publication_status="private",
        )
        content_type = ContentType.objects.get_for_model(ComponentMeasurement)
        permission, _ = Permission.objects.get_or_create(
            codename="add_componentmeasurement",
            content_type=content_type,
            defaults={"name": "Can add component measurement"},
        )
        self.regular_user.user_permissions.add(permission)
        sample.compositions.all().delete()

        self.client.force_login(self.regular_user)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?mode=edit"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add measurement")

    def test_sample_detail_empty_compositions_owner_sees_manual_and_measurement_actions(
        self,
    ):
        sample = Sample.objects.create(
            name="Compositionless Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.regular_user,
            publication_status="private",
        )
        content_type = ContentType.objects.get_for_model(ComponentMeasurement)
        permission, _ = Permission.objects.get_or_create(
            codename="add_componentmeasurement",
            content_type=content_type,
            defaults={"name": "Can add component measurement"},
        )
        self.regular_user.user_permissions.add(permission)
        composition_permission, _ = Permission.objects.get_or_create(
            codename="add_composition",
            content_type=ContentType.objects.get_for_model(Composition),
            defaults={"name": "Can add composition"},
        )
        self.regular_user.user_permissions.add(composition_permission)
        sample.compositions.all().delete()

        self.client.force_login(self.regular_user)
        response = self.client.get(
            reverse("sample-detail", kwargs={"pk": sample.pk}) + "?mode=edit"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No composition data yet")
        self.assertContains(
            response,
            "Composition groups appear here once component measurements can be normalized",
        )
        self.assertContains(response, "Add composition")
        self.assertContains(response, "Add measurement")

    def test_sample_detail_shows_default_composition(self):
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "No compositions available")

    def test_sample_detail_derives_composition_from_measurements_when_absent(self):
        sample = Sample.objects.create(
            name="Sample Without Persisted Composition",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        sample.compositions.all().delete()
        unit_percent = Unit.objects.filter(name="%").first()
        if unit_percent is None:
            unit_percent = Unit.objects.create(
                name="%", symbol="percent", owner=self.staff_user
            )
        elif not unit_percent.symbol:
            unit_percent.symbol = "percent"
            unit_percent.save(update_fields=["symbol"])

        group = MaterialComponentGroup.objects.create(
            name="Chemical Elements",
            owner=self.staff_user,
            publication_status="published",
        )
        carbon = MaterialComponent.objects.create(
            name="Carbon",
            owner=self.staff_user,
            publication_status="published",
        )
        nitrogen = MaterialComponent.objects.create(
            name="Nitrogen",
            owner=self.staff_user,
            publication_status="published",
        )

        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=carbon,
            unit=unit_percent,
            average=Decimal("30"),
        )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=nitrogen,
            unit=unit_percent,
            average=Decimal("70"),
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chemical Elements")
        compositions = response.context["data"]["compositions"]
        self.assertEqual(len(compositions), 1)
        composition = compositions[0]
        self.assertTrue(composition["is_derived"])
        self.assertEqual(composition["group_name"], "Chemical Elements")
        self.assertEqual(
            {share["component_name"] for share in composition["shares"]},
            {"Carbon", "Nitrogen"},
        )
        self.assertEqual(
            {share["as_percentage"] for share in composition["shares"]},
            {"30.0%", "70.0%"},
        )
        self.assertContains(response, "Normalized share")
        self.assertContains(response, "composition-methodology")
        self.assertNotContains(response, "30.0 ± 0.0%")
        self.assertNotContains(response, "No compositions available")

    def test_sample_detail_uses_settings_only_composition_order_for_derived_display(
        self,
    ):
        sample = Sample.objects.create(
            name="Sample With Ordering Settings",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        sample.compositions.all().delete()

        unit_percent = Unit.objects.filter(name="%").first()
        if unit_percent is None:
            unit_percent = Unit.objects.create(
                name="%", symbol="percent", owner=self.staff_user
            )
        elif not unit_percent.symbol:
            unit_percent.symbol = "percent"
            unit_percent.save(update_fields=["symbol"])

        chemical_group = MaterialComponentGroup.objects.create(
            name="Chemical Elements",
            owner=self.staff_user,
            publication_status="published",
        )
        organic_group = MaterialComponentGroup.objects.create(
            name="Organic/Inorganic",
            owner=self.staff_user,
            publication_status="published",
        )
        carbon = MaterialComponent.objects.create(
            name="Carbon",
            owner=self.staff_user,
            publication_status="published",
        )
        organic = MaterialComponent.objects.create(
            name="Organic matter",
            owner=self.staff_user,
            publication_status="published",
        )

        Composition.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=organic_group,
            fractions_of=MaterialComponent.objects.default(),
            order=100,
        )
        Composition.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=chemical_group,
            fractions_of=MaterialComponent.objects.default(),
            order=110,
        )

        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=chemical_group,
            component=carbon,
            unit=unit_percent,
            average=Decimal("100"),
        )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=organic_group,
            component=organic,
            unit=unit_percent,
            average=Decimal("100"),
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Organic/Inorganic")
        self.assertContains(response, "Chemical Elements")
        self.assertContains(response, "100.0%")
        self.assertNotContains(response, "100.0 ± 0.0%")

        content = response.content.decode()
        self.assertLess(
            content.index(f'href="#group-{organic_group.pk}"'),
            content.index(f'href="#group-{chemical_group.pk}"'),
        )
        self.assertLess(
            content.index(f'id="group-{organic_group.pk}"'),
            content.index(f'id="group-{chemical_group.pk}"'),
        )

    def test_sample_detail_scales_over_100_raw_totals_to_100(self):
        sample = Sample.objects.create(
            name="Sample Over 100",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        sample.compositions.all().delete()
        unit_percent = Unit.objects.filter(name="%").first() or Unit.objects.create(
            name="%", symbol="percent", owner=self.staff_user
        )
        group = MaterialComponentGroup.objects.create(
            name="Chemical Elements",
            owner=self.staff_user,
            publication_status="published",
        )
        for name, average in (("Carbon", "60"), ("Nitrogen", "45")):
            ComponentMeasurement.objects.create(
                owner=self.staff_user,
                sample=sample,
                group=group,
                component=MaterialComponent.objects.create(
                    name=name, owner=self.staff_user, publication_status="published"
                ),
                unit=unit_percent,
                average=Decimal(average),
            )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Σ ")
        self.assertContains(response, "57.1%")
        self.assertContains(response, "42.9%")
        self.assertNotContains(response, "alert-warning")

        composition = response.context["display_compositions"][0]
        self.assertEqual(composition["share_total_percent"], 100.0)
        chart = response.context["charts"][f"composition-chart-{composition['id']}"]
        self.assertEqual(chart["data"]["datasets"][0]["data"], [57.1, 42.9])
        self.assertEqual(
            chart["data"]["tooltip_labels"], ["Carbon: 57.1 %", "Nitrogen: 42.9 %"]
        )

    def test_sample_detail_v2_places_normalized_view_before_raw_drilldown(self):
        sample = Sample.objects.create(
            name="Sample Layout Order",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        sample.compositions.all().delete()

        unit_percent = Unit.objects.filter(name="%").first()
        if unit_percent is None:
            unit_percent = Unit.objects.create(
                name="%", symbol="percent", owner=self.staff_user
            )
        elif not unit_percent.symbol:
            unit_percent.symbol = "percent"
            unit_percent.save(update_fields=["symbol"])

        group = MaterialComponentGroup.objects.create(
            name="Test Group",
            owner=self.staff_user,
            publication_status="published",
        )
        component = MaterialComponent.objects.create(
            name="Test Component",
            owner=self.staff_user,
            publication_status="published",
        )

        Composition.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default(),
        )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=component,
            unit=unit_percent,
            average=Decimal("100"),
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertLess(
            content.index("sdv2-group-body"),
            content.index("Raw measurements"),
        )

    def test_sample_detail_keeps_dm_percent_values_for_dm_measurements(self):
        sample = Sample.objects.create(
            name="Sample DM Basis",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        sample.compositions.all().delete()

        unit_percent = Unit.objects.filter(name="%").first()
        if unit_percent is None:
            unit_percent = Unit.objects.create(
                name="%", symbol="percent", owner=self.staff_user
            )
        elif not unit_percent.symbol:
            unit_percent.symbol = "percent"
            unit_percent.save(update_fields=["symbol"])

        group = MaterialComponentGroup.objects.create(
            name="DM Group",
            owner=self.staff_user,
            publication_status="published",
        )
        dry_matter = MaterialComponent.objects.create(
            name="DM",
            owner=self.staff_user,
            publication_status="published",
        )
        lignin = MaterialComponent.objects.create(
            name="Lignin",
            owner=self.staff_user,
            publication_status="published",
        )
        cellulose = MaterialComponent.objects.create(
            name="Cellulose",
            owner=self.staff_user,
            publication_status="published",
        )

        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=lignin,
            basis_component=dry_matter,
            unit=unit_percent,
            average=Decimal("35"),
        )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=cellulose,
            basis_component=dry_matter,
            unit=unit_percent,
            average=Decimal("25"),
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "% of DM")
        self.assertContains(response, "35.0%")
        self.assertContains(response, "25.0%")
        self.assertContains(response, "40.0%")
        self.assertNotContains(response, "35.0 ± 0.0%")

    def test_sample_detail_fills_other_for_incomplete_weight_percent_measurements(self):
        sample = Sample.objects.create(
            name="Sample Incomplete Weight Percent",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        sample.compositions.all().delete()

        unit_g_per_kg = Unit.objects.filter(name="g/kg").first()
        if unit_g_per_kg is None:
            unit_g_per_kg = Unit.objects.create(
                name="g/kg", symbol="g/kg", owner=self.staff_user
            )
        elif not unit_g_per_kg.symbol:
            unit_g_per_kg.symbol = "g/kg"
            unit_g_per_kg.save(update_fields=["symbol"])

        group = MaterialComponentGroup.objects.create(
            name="Weight Percent Group",
            owner=self.staff_user,
            publication_status="published",
        )
        protein = MaterialComponent.objects.create(
            name="Protein",
            owner=self.staff_user,
            publication_status="published",
        )
        fat = MaterialComponent.objects.create(
            name="Fat",
            owner=self.staff_user,
            publication_status="published",
        )

        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=protein,
            unit=unit_g_per_kg,
            average=Decimal("150"),
        )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=fat,
            unit=unit_g_per_kg,
            average=Decimal("250"),
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "15.0%")
        self.assertContains(response, "25.0%")
        self.assertContains(response, "60.0%")
        self.assertNotContains(response, "60.0 ± 0.0%")

        content = response.content.decode()
        self.assertLess(content.index("Fat"), content.index("Protein"))
        self.assertLess(content.index(">Fat</a>"), content.index(">Protein</a>"))
        self.assertLess(content.index(">Protein</a>"), content.index(">Other</a>"))

    def test_sample_detail_uses_basis_component_as_reference_for_derived_composition(
        self,
    ):
        sample = Sample.objects.create(
            name="Sample Basis Component Reference",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        sample.compositions.all().delete()

        unit_g_per_kg = Unit.objects.filter(name="g/kg").first()
        if unit_g_per_kg is None:
            unit_g_per_kg = Unit.objects.create(
                name="g/kg", symbol="g/kg", owner=self.staff_user
            )
        elif not unit_g_per_kg.symbol:
            unit_g_per_kg.symbol = "g/kg"
            unit_g_per_kg.save(update_fields=["symbol"])

        group = MaterialComponentGroup.objects.create(
            name="Reference Group",
            owner=self.staff_user,
            publication_status="published",
        )
        volatile_solids = MaterialComponent.objects.create(
            name="VS",
            owner=self.staff_user,
            publication_status="published",
        )
        protein = MaterialComponent.objects.create(
            name="Protein",
            owner=self.staff_user,
            publication_status="published",
        )
        fat = MaterialComponent.objects.create(
            name="Fat",
            owner=self.staff_user,
            publication_status="published",
        )

        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=protein,
            basis_component=volatile_solids,
            unit=unit_g_per_kg,
            average=Decimal("100"),
        )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=fat,
            basis_component=volatile_solids,
            unit=unit_g_per_kg,
            average=Decimal("200"),
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "% of VS")

    def test_sample_detail_shows_canonical_component_mapping_for_raw_measurements(self):
        sample = Sample.objects.create(
            name="Sample With Equivalent Raw Parameter",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        group = MaterialComponentGroup.objects.create(
            name="Organic fraction",
            owner=self.staff_user,
            publication_status="published",
        )
        organic_matter = MaterialComponent.objects.create(
            name="Organic matter",
            owner=self.staff_user,
            publication_status="published",
        )
        volatile_solids = MaterialComponent.objects.create(
            name="Volatile solids",
            owner=self.staff_user,
            publication_status="published",
            comparable_component=organic_matter,
        )
        unit_percent = Unit.objects.filter(name="%").first()
        if unit_percent is None:
            unit_percent = Unit.objects.create(
                name="%", symbol="percent", owner=self.staff_user
            )
        elif not unit_percent.symbol:
            unit_percent.symbol = "percent"
            unit_percent.save(update_fields=["symbol"])

        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=volatile_solids,
            unit=unit_percent,
            average=Decimal("62"),
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Volatile solids")
        self.assertContains(response, "Canonical: Organic matter")
        self.assertContains(response, "↔ Organic matter")

    def test_analytical_method_list_empty_anonymous(self):
        response = self.client.get(
            reverse("analyticalmethod-list") + "?scope=published&name=no-match-token"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Log in to create new analytical methods.")

    def test_analytical_method_list_empty_staff_shows_create_cta(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("analyticalmethod-list-owned")
            + "?scope=private&name=no-match-token"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Create your first analytical method to get started."
        )

    def test_reset_filter_link_preserves_scope(self):
        scopes = ["published", "private", "review"]
        for scope in scopes:
            with self.subTest(scope=scope):
                self.client.force_login(self.staff_user)
                url = reverse("material-list") + f"?scope={scope}"
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

                expected_reset_url = f"?scope={scope}"
                self.assertContains(response, expected_reset_url)

    def test_empty_state_with_existing_reset_behavior(self):
        Material.objects.create(
            name="Test Material",
            type="material",
            owner=self.staff_user,
            publication_status="published",
        )

        empty_category = self._create_unused_category()

        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("material-list") + f"?scope=published&category={empty_category.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")

        reset_url = reverse("material-list") + "?scope=published"
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Material")


class MaterialsReviewWorkflowTests(TestCase):
    """Test the full review workflow (submit → approve/reject → withdraw) for Sample."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123"
        )
        cls.regular_user = User.objects.create_user(
            username="regular", password="test123"
        )

        # Add moderator permission for Sample
        sample_ct = ContentType.objects.get_for_model(Sample)
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_sample",
            content_type=sample_ct,
            defaults={"name": "Can moderate samples"},
        )
        cls.moderator.user_permissions.add(perm)

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.private_sample = Sample.objects.create(
                name="Private Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.review_sample = Sample.objects.create(
                name="Review Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

    def setUp(self):
        self.sample_ct_id = ContentType.objects.get_for_model(Sample).id

    # --- Submit for Review ---

    def test_owner_can_submit_private_sample_for_review(self):
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.private_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.private_sample.refresh_from_db()
        self.assertEqual(
            self.private_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    def test_non_owner_cannot_submit_sample_for_review(self):
        self.client.force_login(self.regular_user)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.private_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.private_sample.refresh_from_db()
        self.assertEqual(
            self.private_sample.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_anonymous_cannot_submit_sample_for_review(self):
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.private_sample.id,
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response.url)

    # --- Withdraw from Review ---

    def test_owner_can_withdraw_sample_from_review(self):
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:withdraw_from_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_non_owner_cannot_withdraw_sample_from_review(self):
        self.client.force_login(self.regular_user)
        url = reverse(
            "object_management:withdraw_from_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    # --- Approve ---

    def test_moderator_can_approve_sample(self):
        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_PUBLISHED
        )
        self.assertEqual(self.review_sample.approved_by, self.moderator)

    def test_regular_user_cannot_approve_sample(self):
        self.client.force_login(self.regular_user)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    def test_owner_cannot_approve_own_sample(self):
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    def test_approve_blocked_when_composition_has_no_measurements(self):
        """Approving a sample with an empty composition group is blocked."""
        with mute_signals(post_save, pre_save):
            sample = Sample.objects.create(
                name="Empty Composition Sample",
                material=self.material,
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
                standalone=True,
            )
            group = MaterialComponentGroup.objects.create(
                name="Placeholder Group",
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            Composition.objects.create(
                owner=self.owner,
                group=group,
                sample=sample,
            )
            # No ComponentMeasurement created for this group

        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        sample.refresh_from_db()
        self.assertEqual(sample.publication_status, UserCreatedObject.STATUS_REVIEW)

    def test_approve_succeeds_when_all_compositions_have_measurements(self):
        """Approving a sample where every composition group has measurements succeeds."""
        with mute_signals(post_save, pre_save):
            sample = Sample.objects.create(
                name="Full Composition Sample",
                material=self.material,
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
                standalone=True,
            )
            group = MaterialComponentGroup.objects.create(
                name="Filled Group",
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            component = MaterialComponent.objects.create(
                name="Test Component",
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            Composition.objects.create(
                owner=self.owner,
                group=group,
                sample=sample,
            )
            ComponentMeasurement.objects.create(
                owner=self.owner,
                sample=sample,
                group=group,
                component=component,
                average=50.0,
                standard_deviation=0.0,
            )

        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        sample.refresh_from_db()
        self.assertEqual(sample.publication_status, UserCreatedObject.STATUS_PUBLISHED)

    # --- Reject ---

    def test_moderator_can_reject_sample(self):
        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:reject_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_DECLINED
        )

    def test_regular_user_cannot_reject_sample(self):
        self.client.force_login(self.regular_user)
        url = reverse(
            "object_management:reject_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    # --- Re-submit after rejection ---

    def test_owner_can_resubmit_declined_sample(self):
        with mute_signals(post_save, pre_save):
            self.private_sample.publication_status = UserCreatedObject.STATUS_DECLINED
            self.private_sample.save()

        self.client.force_login(self.owner)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.private_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.private_sample.refresh_from_db()
        self.assertEqual(
            self.private_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )


class MaterialsReviewDetailAccessTests(TestCase):
    """Test access to the review detail view for materials models."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123"
        )
        cls.other_user = User.objects.create_user(username="other", password="test123")

        sample_ct = ContentType.objects.get_for_model(Sample)
        cls.sample_ct_id = sample_ct.id
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_sample",
            content_type=sample_ct,
            defaults={"name": "Can moderate samples"},
        )
        cls.moderator.user_permissions.add(perm)

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.review_sample = Sample.objects.create(
                name="Review Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.declined_sample = Sample.objects.create(
                name="Declined Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_DECLINED,
            )

    def _review_detail_url(self, obj):
        return reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": obj.id,
            },
        )

    def test_owner_can_access_review_detail_for_review_sample(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._review_detail_url(self.review_sample))
        self.assertEqual(response.status_code, 200)

    def test_owner_can_access_review_detail_for_declined_sample(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._review_detail_url(self.declined_sample))
        self.assertEqual(response.status_code, 200)

    def test_moderator_can_access_review_detail(self):
        self.client.force_login(self.moderator)
        response = self.client.get(self._review_detail_url(self.review_sample))
        self.assertEqual(response.status_code, 200)

    def test_sample_review_detail_uses_v2_with_full_sample_context(self):
        self.client.force_login(self.moderator)

        response = self.client.get(self._review_detail_url(self.review_sample))

        self.assertTemplateUsed(response, "materials/sample_detail_v2.html")
        self.assertContains(response, 'class="sdv2"')
        self.assertContains(response, 'id="review-panel"')
        self.assertContains(response, self.review_sample.name)
        self.assertIn("display_compositions", response.context)
        self.assertIn("property_values", response.context)

    def test_non_owner_non_moderator_cannot_access_review_detail(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self._review_detail_url(self.review_sample))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_access_review_detail(self):
        response = self.client.get(self._review_detail_url(self.review_sample))
        self.assertEqual(response.status_code, 403)


class SampleDetailTemplateReviewUITests(TestCase):
    """Test that the sample detail template shows review UI elements correctly."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")
        cls.reviewer = User.objects.create_user(username="reviewer", password="test123")

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.private_sample = Sample.objects.create(
                name="Private Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.review_sample = Sample.objects.create(
                name="Review Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.published_sample = Sample.objects.create(
                name="Published Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

    def test_private_sample_shows_submit_for_review_button_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.private_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Submit for review")

    def test_review_sample_shows_review_view_link_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.review_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review view")

    def test_review_sample_shows_review_activity_when_feedback_exists(self):
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Sample),
            object_id=self.review_sample.pk,
            action=ReviewAction.ACTION_SUBMITTED,
            user=self.owner,
        )
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Sample),
            object_id=self.review_sample.pk,
            action=ReviewAction.ACTION_COMMENT,
            comment="Please clarify the sampling date.",
            user=self.reviewer,
        )

        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.review_sample.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review activity")

    def test_owned_sample_list_shows_review_activity_badge_when_feedback_exists(self):
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Sample),
            object_id=self.review_sample.pk,
            action=ReviewAction.ACTION_SUBMITTED,
            user=self.owner,
        )
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Sample),
            object_id=self.review_sample.pk,
            action=ReviewAction.ACTION_COMMENT,
            comment="Needs one more source.",
            user=self.reviewer,
        )

        self.client.force_login(self.owner)
        response = self.client.get(reverse("sample-list-owned"), {"scope": "private"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review activity")

    def test_published_sample_does_not_show_submit_button(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.published_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Submit for Review")

    def test_sample_detail_uses_retired_v2_surface_directly(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.private_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        template_names = [t.name for t in response.templates]
        self.assertIn("materials/sample_detail_v2.html", template_names)
        self.assertNotIn("detail_with_options.html", template_names)

    def test_sample_detail_uses_series_image_when_sample_image_missing(self):
        with mute_signals(post_save, pre_save):
            series = SampleSeries.objects.create(
                name="Series With Image",
                material=self.material,
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
                image="materials_sampleseries/detail-series-image.jpg",
            )
            sample = Sample.objects.create(
                name="Sample Without Own Image",
                material=self.material,
                series=series,
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

        self.client.force_login(self.owner)
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "materials_sampleseries/detail-series-image.jpg")
        self.assertContains(response, "Showing the image from the linked sample series")


class SampleSeriesDetailTemplateReviewUITests(TestCase):
    """Test that the sample series detail template shows review UI elements."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.private_series = SampleSeries.objects.create(
                name="Private Series",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.review_series = SampleSeries.objects.create(
                name="Review Series",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

    def test_private_series_shows_submit_button_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sampleseries-detail", kwargs={"pk": self.private_series.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Submit for Review")

    def test_review_series_shows_review_view_link_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sampleseries-detail", kwargs={"pk": self.review_series.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review view")

    def test_series_detail_extends_detail_with_options(self):
        self.client.force_login(self.owner)
        url = reverse("sampleseries-detail", kwargs={"pk": self.private_series.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        template_names = [t.name for t in response.templates]
        self.assertIn("detail_with_options.html", template_names)


class MaterialsReviewDashboardTests(TestCase):
    """Test that materials models appear correctly in the review dashboard."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")
        cls.staff = User.objects.create_user(
            username="staff", password="test123", is_staff=True
        )
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123"
        )

        sample_ct = ContentType.objects.get_for_model(Sample)
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_sample",
            content_type=sample_ct,
            defaults={"name": "Can moderate samples"},
        )
        cls.moderator.user_permissions.add(perm)

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.review_sample = Sample.objects.create(
                name="Dashboard Review Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.private_sample = Sample.objects.create(
                name="Dashboard Private Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

    def test_review_sample_appears_in_dashboard_for_staff(self):
        self.client.force_login(self.staff)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        review_items = list(response.context["review_items"])
        item_names = [item.name for item in review_items]
        self.assertIn("Dashboard Review Sample", item_names)

    def test_private_sample_not_in_dashboard(self):
        self.client.force_login(self.staff)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)
        review_items = list(response.context["review_items"])
        item_names = [item.name for item in review_items]
        self.assertNotIn("Dashboard Private Sample", item_names)

    def test_moderator_sees_review_sample_in_dashboard(self):
        self.client.force_login(self.moderator)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        review_items = list(response.context["review_items"])
        sample_items = [item for item in review_items if isinstance(item, Sample)]
        self.assertTrue(len(sample_items) > 0)

    def test_filter_dashboard_by_sample_model_type(self):
        self.client.force_login(self.staff)
        sample_ct = ContentType.objects.get_for_model(Sample)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url, {"model_type": sample_ct.id})
        self.assertEqual(response.status_code, 200)
        review_items = list(response.context["review_items"])
        for item in review_items:
            self.assertIsInstance(item, Sample)


class ReviewActionLoggingTests(TestCase):
    """Test that review actions create audit log entries."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123"
        )

        sample_ct = ContentType.objects.get_for_model(Sample)
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_sample",
            content_type=sample_ct,
            defaults={"name": "Can moderate samples"},
        )
        cls.moderator.user_permissions.add(perm)

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

    def setUp(self):
        self.sample_ct_id = ContentType.objects.get_for_model(Sample).id
        with mute_signals(post_save, pre_save):
            self.sample = Sample.objects.create(
                name="Log Test Sample",
                material=self.material,
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

    def test_submit_creates_review_action_log(self):
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            self.client.post(url)

        logs = ReviewAction.for_object(self.sample)
        self.assertTrue(logs.filter(action=ReviewAction.ACTION_SUBMITTED).exists())

    def test_approve_creates_review_action_log(self):
        with mute_signals(post_save, pre_save):
            self.sample.publication_status = UserCreatedObject.STATUS_REVIEW
            self.sample.save()

        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            self.client.post(url)

        logs = ReviewAction.for_object(self.sample)
        self.assertTrue(logs.filter(action=ReviewAction.ACTION_APPROVED).exists())

    def test_reject_creates_review_action_log(self):
        with mute_signals(post_save, pre_save):
            self.sample.publication_status = UserCreatedObject.STATUS_REVIEW
            self.sample.save()

        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:reject_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            self.client.post(url)

        logs = ReviewAction.for_object(self.sample)
        self.assertTrue(logs.filter(action=ReviewAction.ACTION_REJECTED).exists())
