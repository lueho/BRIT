from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase

from ..models import MechanismCategory, ProcessGroup, ProcessType

User = get_user_model()


class ProcessesDashboardViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_processtype"

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("processes-dashboard"))
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("processes-dashboard"))
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("processes-dashboard"))
        self.assertEqual(200, response.status_code)

    def test_context_contains_counts(self):
        response = self.client.get(reverse("processes-dashboard"))
        self.assertIn("processtype_count", response.context)
        self.assertIn("processgroup_count", response.context)
        self.assertIn("mechanismcategory_count", response.context)


class ProcessGroupCRUDViewTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = ProcessGroup
    create_object_data = {
        "name": "New Group Published",
        "description": "A test group",
    }
    update_object_data = {
        "name": "Updated Group",
        "description": "Updated description",
    }

    view_dashboard_name = "processes-dashboard"
    view_create_name = "processgroup-create"
    view_modal_create_name = "processgroup-create-modal"
    view_published_list_name = "processgroup-list"
    view_private_list_name = "processgroup-list-owned"
    view_detail_name = "processgroup-detail"
    view_modal_detail_name = "processgroup-detail-modal"
    view_update_name = "processgroup-update"
    view_modal_update_name = "processgroup-update-modal"
    view_delete_name = "processgroup-delete-modal"

    add_scope_query_param_to_list_urls = True
    modal_create_view = True
    modal_detail_view = True
    modal_update_view = True

    @classmethod
    def create_published_object(cls):
        data = cls.create_object_data.copy()
        data["publication_status"] = "published"
        data.update(cls.related_objects)
        return cls.model.objects.create(owner=cls.owner_user, **data)

    @classmethod
    def create_unpublished_object(cls):
        data = cls.create_object_data.copy()
        data["name"] = "New Group Private"
        data["publication_status"] = "private"
        data.update(cls.related_objects)
        return cls.model.objects.create(owner=cls.owner_user, **data)


class MechanismCategoryCRUDViewTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    model = MechanismCategory
    create_object_data = {
        "name": "New Mechanism Published",
        "description": "A test mechanism",
    }
    update_object_data = {
        "name": "Updated Mechanism",
        "description": "Updated description",
    }

    view_dashboard_name = "processes-dashboard"
    view_create_name = "mechanismcategory-create"
    view_modal_create_name = "mechanismcategory-create-modal"
    view_published_list_name = "mechanismcategory-list"
    view_private_list_name = "mechanismcategory-list-owned"
    view_detail_name = "mechanismcategory-detail"
    view_modal_detail_name = "mechanismcategory-detail-modal"
    view_update_name = "mechanismcategory-update"
    view_modal_update_name = "mechanismcategory-update-modal"
    view_delete_name = "mechanismcategory-delete-modal"

    add_scope_query_param_to_list_urls = True
    modal_create_view = True
    modal_detail_view = True
    modal_update_view = True

    @classmethod
    def create_published_object(cls):
        data = cls.create_object_data.copy()
        data["publication_status"] = "published"
        data.update(cls.related_objects)
        return cls.model.objects.create(owner=cls.owner_user, **data)

    @classmethod
    def create_unpublished_object(cls):
        data = cls.create_object_data.copy()
        data["name"] = "New Mechanism Private"
        data["publication_status"] = "private"
        data.update(cls.related_objects)
        return cls.model.objects.create(owner=cls.owner_user, **data)


class ProcessTypeCRUDViewTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = ProcessType
    create_object_data = {
        "name": "Test Process Published",
        "description": "A test process type",
        "short_description": "Test",
        "mechanism": "Test Mechanism",
    }
    update_object_data = {
        "name": "Updated Process",
        "description": "Updated description",
        "short_description": "Updated",
        "mechanism": "Updated Mechanism",
    }

    view_dashboard_name = "processes-dashboard"
    view_create_name = "processtype-create"
    view_modal_create_name = "processtype-create-modal"
    view_published_list_name = "processtype-list"
    view_private_list_name = "processtype-list-owned"
    view_detail_name = "processtype-detail"
    view_modal_detail_name = "processtype-detail-modal"
    view_update_name = "processtype-update"
    view_modal_update_name = "processtype-update-modal"
    view_delete_name = "processtype-delete-modal"

    add_scope_query_param_to_list_urls = True
    modal_create_view = True
    modal_detail_view = True
    modal_update_view = True

    @classmethod
    def create_published_object(cls):
        data = cls.create_object_data.copy()
        data["publication_status"] = "published"
        data.update(cls.related_objects)
        return cls.model.objects.create(owner=cls.owner_user, **data)

    @classmethod
    def create_unpublished_object(cls):
        data = cls.create_object_data.copy()
        data["name"] = "Test Process Private"
        data["publication_status"] = "private"
        data.update(cls.related_objects)
        return cls.model.objects.create(owner=cls.owner_user, **data)


class ProcessTypeDetailViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="pt_detail_owner")
        cls.group = ProcessGroup.objects.create(
            name="DetailGroup",
            owner=cls.owner,
            publication_status="published",
        )
        cls.process_type = ProcessType.objects.create(
            name="Detail Process",
            description="Full detail process",
            short_description="Short desc",
            mechanism="Mechanism",
            temperature_min=100,
            temperature_max=200,
            yield_min=50,
            yield_max=60,
            group=cls.group,
            owner=cls.owner,
            publication_status="published",
        )

    def test_detail_contains_process_fields(self):
        url = reverse("processtype-detail", kwargs={"pk": self.process_type.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Detail Process", content)
        self.assertIn("Mechanism", content)
        self.assertIn("DetailGroup", content)

    def test_detail_contains_temperature_range(self):
        url = reverse("processtype-detail", kwargs={"pk": self.process_type.pk})
        response = self.client.get(url)
        content = response.content.decode()
        self.assertIn("100", content)
        self.assertIn("200", content)
