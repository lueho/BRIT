from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse

from bibliography.models import Source
from distributions.models import TemporalDistribution, Timestep
from utils.object_management.views import SubmitForReviewView
from utils.properties.models import Unit
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase

from ..models import (
    AnalyticalMethod,
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
