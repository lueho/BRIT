from django.contrib.auth.models import Permission
from django.urls import reverse

from distributions.models import TemporalDistribution, Timestep
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


class MaterialDashboardViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "change_material"

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("materials-dashboard"))
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("materials-dashboard"))
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("materials-dashboard"))
        self.assertEqual(200, response.status_code)


# ----------- Material Category CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class MaterialCategoryCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True

    model = MaterialCategory

    view_dashboard_name = "materials-dashboard"
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

    model = Material

    view_dashboard_name = "materials-dashboard"
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

    model = MaterialComponent

    view_dashboard_name = "materials-dashboard"
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

    model = MaterialComponentGroup

    view_dashboard_name = "materials-dashboard"
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

    model = MaterialProperty

    view_dashboard_name = "materials-dashboard"
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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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

    model = AnalyticalMethod

    view_dashboard_name = "materials-dashboard"
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

    model = SampleSeries

    view_dashboard_name = "materials-dashboard"
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
        material = Material.objects.create(name="Test Material")
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
        return {"material": Material.objects.create(name="Test Material")}


# ----------- Sample CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class FeaturedSampleListViewTestCase(ViewWithPermissionsTestCase):

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("sample-list"))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("sample-list"))
        self.assertEqual(response.status_code, 200)


class SampleCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_create_view = True

    model = Sample

    view_dashboard_name = "materials-dashboard"
    view_create_name = "sample-create"
    view_modal_create_name = "sample-create-modal"
    view_published_list_name = "sample-list"
    view_private_list_name = "sample-list-owned"
    view_detail_name = "sample-detail"
    view_update_name = "sample-update"
    view_delete_name = "sample-delete-modal"

    create_object_data = {"name": "Test Sample"}
    update_object_data = {"name": "Updated Test Sample"}

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(name="Test Material")
        prop = MaterialProperty.objects.create(name="Test Property", unit="Test Unit")
        MaterialPropertyValue.objects.create(
            name="Test Value", property=prop, average=123.3, standard_deviation=0.13
        )
        return {"material": material}

    @classmethod
    def create_published_object(cls):
        published_sample = super().create_published_object()
        property_value = MaterialPropertyValue.objects.get(name="Test Value")
        published_sample.properties.add(property_value)
        return published_sample

    @classmethod
    def create_unpublished_object(cls):
        unpublished_sample = super().create_unpublished_object()
        property_value = MaterialPropertyValue.objects.get(name="Test Value")
        unpublished_sample.properties.add(property_value)
        return unpublished_sample

    def test_list_view_published_as_authenticated_owner(self):
        if not self.public_list_view:
            self.skipTest("List view is not enabled for this test case.")
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_list_url(publication_status="published"))
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
        response = self.client.get(self.get_list_url(publication_status="published"))
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
        response = self.client.get(self.get_list_url(publication_status="private"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<th>Public</th>")
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
        response = self.client.get(self.get_list_url(publication_status="private"))
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

    def test_template_contains_edit_and_delete_buttons_for_owners(self):
        self.client.force_login(self.owner_user)
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url)
        self.assertContains(response, self.get_update_url(self.published_object.pk))
        self.assertContains(response, self.get_delete_url(self.published_object.pk))
        self.assertContains(
            response,
            reverse("sample-duplicate", kwargs={"pk": self.published_object.pk}),
        )
        self.assertContains(
            response,
            reverse("sample-add-property", kwargs={"pk": self.published_object.pk}),
        )
        self.assertContains(
            response,
            reverse("sample-add-composition", kwargs={"pk": self.published_object.pk}),
        )

        property_value = MaterialPropertyValue.objects.get(name="Test Value")
        self.assertContains(
            response,
            reverse(
                "materialpropertyvalue-delete-modal", kwargs={"pk": property_value.pk}
            ),
        )
        self.assertContains(response, "edit-group-")
        self.assertContains(response, reverse("materials-dashboard"))

    def test_template_does_not_contain_edit_and_delete_button_for_non_owner_users(self):
        self.client.force_login(self.non_owner_user)
        url = self.get_detail_url(self.published_object.pk)
        response = self.client.get(url)
        self.assertNotContains(response, self.get_update_url(self.published_object.pk))
        self.assertNotContains(response, self.get_delete_url(self.published_object.pk))
        self.assertNotContains(
            response,
            reverse("sample-duplicate", kwargs={"pk": self.published_object.pk}),
        )
        self.assertNotContains(
            response,
            reverse("sample-add-property", kwargs={"pk": self.published_object.pk}),
        )
        self.assertNotContains(
            response,
            reverse("sample-add-composition", kwargs={"pk": self.published_object.pk}),
        )

        property_value = MaterialPropertyValue.objects.get(name="Test Value")
        self.assertNotContains(
            response,
            reverse(
                "materialpropertyvalue-delete-modal", kwargs={"pk": property_value.pk}
            ),
        )
        self.assertNotContains(response, "edit-group-")
        self.assertContains(response, reverse("materials-dashboard"))


# ----------- Sample utilities -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class SampleAddPropertyViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_materialpropertyvalue"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(name="Test Series", material=material)
        cls.sample = Sample.objects.create(
            name="Test Sample", material=material, series=series
        )
        MaterialProperty.objects.create(name="Test Property", unit="Test Unit")

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-add-property", kwargs={"pk": self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
            average=123.321, standard_deviation=0.1337
        )
        self.assertIn(value, self.sample.properties.all())


class SampleModalAddPropertyViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_materialpropertyvalue"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="add_materialpropertyvalue")
        )
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(
            owner=cls.owner, name="Test Series", material=material
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner, name="Test Sample", material=material, series=series
        )
        MaterialProperty.objects.create(name="Test Property", unit="Test Unit")

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse("sample-add-property-modal", kwargs={"pk": self.sample.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
            average=123.321, standard_deviation=0.1337
        )
        self.assertIn(value, self.sample.properties.all())


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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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

    view_dashboard_name = "materials-dashboard"
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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={redirect_url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

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
