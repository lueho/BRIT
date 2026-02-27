from decimal import Decimal
from urllib.parse import quote
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.test import RequestFactory, TestCase
from django.urls import reverse
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
    WeightShare,
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
            owner=cls.member, property=prop, average=123.312, standard_deviation=0.1337
        )
        sample.properties.add(cls.value)

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
        sample = self.value.sample_set.first()
        # Fix: Ensure sample exists and has a valid pk before using in reverse()
        self.assertIsNotNone(sample, "Sample should exist and be related to the value")
        self.assertIsNotNone(sample.pk, "Sample should have a valid pk")
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
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("sample-list-featured"))
        self.assertEqual(response.status_code, 200)


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

    create_object_data = {"name": "Test Sample"}
    update_object_data = {"name": "Updated Test Sample"}

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(
            name="Test Material", publication_status="published"
        )
        prop = MaterialProperty.objects.create(
            name="Test Property", unit="Test Unit", publication_status="published"
        )
        MaterialPropertyValue.objects.create(
            property=prop,
            average=123.3,
            standard_deviation=0.13,
            publication_status="published",
        )
        return {"material": material}

    @classmethod
    def create_published_object(cls):
        published_sample = super().create_published_object()
        property_value = MaterialPropertyValue.objects.get(
            property__name="Test Property"
        )
        published_sample.properties.add(property_value)
        return published_sample

    @classmethod
    def create_unpublished_object(cls):
        unpublished_sample = super().create_unpublished_object()
        property_value = MaterialPropertyValue.objects.get(
            property__name="Test Property"
        )
        unpublished_sample.properties.add(property_value)
        return unpublished_sample

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
        cls.property = MaterialProperty.objects.create(
            name="Test Property", unit="Test Unit", owner=cls.owner
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
        self.assertIn(value, self.sample.properties.all())

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
        cls.property = MaterialProperty.objects.create(
            name="Test Property", unit="Test Unit", owner=cls.owner
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
        self.assertIn(value, self.sample.properties.all())

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


class SampleCreateDuplicateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_sample"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(name="Test Material")
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
        unpublished_weight_share_1 = WeightShare.objects.create(
            composition=cls.unpublished_object,
            component=component_1,
            average=0.33,
            standard_deviation=0.01,
        )
        unpublished_weight_share_2 = WeightShare.objects.create(
            composition=cls.unpublished_object,
            component=component_1,
            average=0.67,
            standard_deviation=0.01,
        )
        published_weight_share_1 = WeightShare.objects.create(
            composition=cls.published_object,
            component=component_1,
            average=0.33,
            standard_deviation=0.01,
        )
        published_weight_share_2 = WeightShare.objects.create(
            composition=cls.published_object,
            component=component_1,
            average=0.67,
            standard_deviation=0.01,
        )
        return {
            "components": {"component_1": component_1, "component_2": component_2},
            "weight_shares": {
                "unpublished_weight_share_1": unpublished_weight_share_1,
                "unpublished_weight_share_2": unpublished_weight_share_2,
                "published_weight_share_1": published_weight_share_1,
                "published_weight_share_2": published_weight_share_2,
            },
        }

    def related_objects_post_data(self):
        return {
            "name": "Updated Test Composition",
            "sample": self.related_objects["unpublished_sample"].pk,
            "group": self.related_objects["group"].pk,
            "fractions_of": self.m2m_objects["components"]["component_1"].pk,
            "shares-TOTAL_FORMS": 2,
            "shares-INITIAL_FORMS": 2,
            "shares-0-id": self.m2m_objects["weight_shares"][
                "unpublished_weight_share_1"
            ].pk,
            "shares-0-owner": self.related_objects["unpublished_sample"].owner.pk,
            "shares-0-component": self.m2m_objects["components"]["component_1"].pk,
            "shares-0-average": 45.5,
            "shares-0-standard_deviation": 1.5,
            "shares-1-id": self.m2m_objects["weight_shares"][
                "unpublished_weight_share_2"
            ].pk,
            "shares-1-owner": self.related_objects["unpublished_sample"].owner.pk,
            "shares-1-component": self.m2m_objects["components"]["component_1"].pk,
            "shares-1-average": 54.5,
            "shares-1-standard_deviation": 1.5,
        }

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

    def test_deleted_forms_are_not_included_in_total_sum_validation(self):
        self.client.force_login(self.owner_user)
        url = self.get_update_url(self.unpublished_object.pk)
        new_component = MaterialComponent.objects.create(name="New Component")
        data = {
            "name": "Updated Test Composition",
            "sample": self.related_objects["unpublished_sample"].pk,
            "group": self.related_objects["group"].pk,
            "fractions_of": self.m2m_objects["components"][
                "component_1"
            ].pk,  # Use valid component
            "shares-INITIAL_FORMS": "2",
            "shares-TOTAL_FORMS": "3",
            "shares-0-id": self.m2m_objects["weight_shares"][
                "unpublished_weight_share_1"
            ].pk,
            "shares-0-owner": self.owner_user.pk,
            "shares-0-component": self.m2m_objects["components"]["component_1"].pk,
            "shares-0-average": "45.5",
            "shares-0-standard_deviation": "1.5",
            "shares-1-id": self.m2m_objects["weight_shares"][
                "unpublished_weight_share_2"
            ].pk,
            "shares-1-owner": self.owner_user.pk,
            "shares-1-component": self.m2m_objects["components"]["component_2"].pk,
            "shares-1-average": "54.5",
            "shares-1-standard_deviation": "1.5",
            "shares-1-DELETE": True,
            "shares-2-id": "",
            "shares-2-owner": self.owner_user.pk,
            "shares-2-component": new_component.pk,
            "shares-2-average": "54.5",
            "shares-2-standard_deviation": "1.5",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

    def test_deleted_forms_delete_correct_weight_share_record(self):
        self.client.force_login(self.owner_user)
        url = self.get_update_url(self.unpublished_object.pk)
        data = {
            "name": "Updated Test Composition",
            "sample": self.related_objects["unpublished_sample"].pk,
            "group": self.related_objects["group"].pk,
            "fractions_of": self.m2m_objects["components"][
                "component_1"
            ].pk,  # Use valid component
            "shares-INITIAL_FORMS": "1",
            "shares-TOTAL_FORMS": "2",
            "shares-0-id": self.m2m_objects["weight_shares"][
                "unpublished_weight_share_1"
            ].pk,
            "shares-0-owner": self.owner_user.pk,
            "shares-0-component": self.m2m_objects["components"]["component_1"].pk,
            "shares-0-average": "45.5",
            "shares-0-standard_deviation": "1.5",
            "shares-0-DELETE": True,
            "shares-1-id": self.m2m_objects["weight_shares"][
                "unpublished_weight_share_2"
            ].pk,
            "shares-1-owner": self.owner_user.pk,
            "shares-1-component": self.m2m_objects["components"]["component_2"].pk,
            "shares-1-average": "100.0",
            "shares-1-standard_deviation": "1.5",
            "shares-1-DELETE": False,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(WeightShare.DoesNotExist):
            WeightShare.objects.get(
                id=self.m2m_objects["weight_shares"]["unpublished_weight_share_1"].pk
            )


# ----------- Composition utilities ------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AddComponentViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_weightshare"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="Test Material")
        cls.component_group = MaterialComponentGroup.objects.create(name="Test Group")
        cls.series = SampleSeries.objects.create(name="Test Series", material=material)
        cls.default_component = MaterialComponent.objects.default()
        cls.sample = Sample.objects.get(
            series=cls.series,
            timestep=Timestep.objects.default(),
        )
        cls.sample.publication_status = "published"
        cls.sample.save()

    def setUp(self):
        self.composition = Composition.objects.create(
            sample=self.sample,
            group=self.component_group,
            fractions_of=self.default_component,
        )
        self.component = MaterialComponent.objects.create(name="Test Component")

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("composition-add-component", kwargs={"pk": self.composition.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("composition-add-component", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("composition-add-component", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("composition-add-component", kwargs={"pk": self.composition.pk})
        )
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("composition-add-component", kwargs={"pk": self.composition.pk})
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('auth_login')}?next={url}")

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("composition-add-component", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_members(self):
        self.client.force_login(self.member)
        data = {"component": self.component.pk}
        response = self.client.post(
            reverse("composition-add-component", kwargs={"pk": self.composition.pk}),
            data,
        )
        self.assertRedirects(
            response, reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )

    def test_post_adds_component(self):
        self.client.force_login(self.member)
        data = {"component": self.component.pk}
        self.client.post(
            reverse("composition-add-component", kwargs={"pk": self.composition.pk}),
            data,
        )
        self.composition.shares.get(component=self.component)


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


# ----------- Materials/Components/Groups Relations --------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AddCompositionViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ("add_composition", "add_weightshare")

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="Test Material")
        cls.component_group = MaterialComponentGroup.objects.create(name="Test Group")
        cls.series = SampleSeries.objects.create(
            name="Test Series",
            material=material,
            publication_status="published",
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

    def test_sample_detail_empty_properties_anonymous(self):
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No properties recorded. Log in to add properties."
        )

    def test_sample_detail_empty_properties_owner_sees_actionable_message(self):
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.regular_user,
            publication_status="published",
        )
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No properties recorded. Add your first property."
        )

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
        self.assertContains(response, "30.0 ± 0.0%")
        self.assertContains(response, "70.0 ± 0.0%")
        self.assertNotContains(response, "No compositions available")

    def test_sample_detail_prefers_persisted_composition_over_measurement_fallback(
        self,
    ):
        sample = Sample.objects.create(
            name="Sample With Persisted Composition",
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
            name="Macronutrients",
            owner=self.staff_user,
            publication_status="published",
        )
        phosphorus = MaterialComponent.objects.create(
            name="Phosphorus",
            owner=self.staff_user,
            publication_status="published",
        )
        potassium = MaterialComponent.objects.create(
            name="Potassium",
            owner=self.staff_user,
            publication_status="published",
        )

        persisted_composition = Composition.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default(),
        )
        WeightShare.objects.create(
            owner=self.staff_user,
            composition=persisted_composition,
            component=phosphorus,
            average=Decimal("0.2"),
            standard_deviation=Decimal("0.0"),
        )
        WeightShare.objects.create(
            owner=self.staff_user,
            composition=persisted_composition,
            component=potassium,
            average=Decimal("0.8"),
            standard_deviation=Decimal("0.0"),
        )

        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=phosphorus,
            unit=unit_percent,
            average=Decimal("70"),
        )
        ComponentMeasurement.objects.create(
            owner=self.staff_user,
            sample=sample,
            group=group,
            component=potassium,
            unit=unit_percent,
            average=Decimal("30"),
        )

        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "20.0 ± 0.0%")
        self.assertContains(response, "80.0 ± 0.0%")
        self.assertNotContains(response, "70.0 ± 0.0%")

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
        self.assertContains(response, "35.0 ± 0.0% of DM")
        self.assertContains(response, "25.0 ± 0.0% of DM")
        self.assertContains(response, "40.0 ± 0.0% of DM")

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
        self.assertContains(response, "15.0 ± 0.0%")
        self.assertContains(response, "25.0 ± 0.0%")
        self.assertContains(response, "60.0 ± 0.0%")

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
        self.assertContains(response, "Shares of:</strong> VS")

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

    def test_private_sample_shows_submit_button_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.private_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Submit for Review")

    def test_review_sample_shows_review_view_link_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.review_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review view")

    def test_published_sample_does_not_show_submit_button(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.published_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Submit for Review")

    def test_sample_detail_extends_detail_with_options(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.private_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        template_names = [t.name for t in response.templates]
        self.assertIn("detail_with_options.html", template_names)


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
