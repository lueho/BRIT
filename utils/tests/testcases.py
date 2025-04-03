from abc import ABC

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, modify_settings
from django.urls import reverse
from rest_framework.test import APIClient

from users.models import User


@modify_settings(MIDDLEWARE={'remove': 'ambient_toolbox.middleware.current_user.CurrentUserMiddleware'})
@modify_settings(MIDDLEWARE={'remove': 'debug_toolbar.middleware.DebugToolbarMiddleware'})
class UserLoginTestCase(TestCase):
    """
    CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
    logins. This TestCase with disabled middleware can be used, where the object creation mechanism is not
    relevant to the test.
    """


class ViewWithPermissionsTestCase(UserLoginTestCase):
    """This TestCase is used for testing views with permissions. There are three levels of access:
    - outsider: no permissions
    - outsider: authenticated but without any special permissions
    - member: has permissions which are specified in the member_permissions class variable"""
    owner = None
    outsider = None
    member = None
    staff = None
    member_permissions = None

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username='owner')
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        cls.staff = User.objects.create(username='staff', is_staff=True)
        if cls.member_permissions:
            if isinstance(cls.member_permissions, str):
                cls.member_permissions = [cls.member_permissions]
            for codename in cls.member_permissions:
                cls.member.user_permissions.add(Permission.objects.get(codename=codename))


class ViewSetWithPermissionsTestCase(ViewWithPermissionsTestCase):
    """
    This TestCase is used for testing ViewSets. It has the same functionality as ViewWithPermissionsTestCase,
    but it uses the APIClient class provided by django rest framework instead of the standard django test client.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.client = APIClient()


def comparable_model_dict(instance):
    """
    Removes '_state' so that two model instances can be compared by their __dict__ property.
    """
    return {k: v for k, v in instance.__dict__.items() if
            k not in ('_state', 'lastmodified_at', '_prefetched_objects_cache')}


class AbstractTestCases(object):
    class UserCreatedObjectCRUDViewTestCase(ABC, UserLoginTestCase):
        """
        Abstract base test case for testing UserCreatedObjectAccessMixin across different models.
        Subclasses must define the following class attributes:

        - model: The Django model to test.
        - view_detail_name: The name of the DetailView URL.
        - view_update_name: The name of the UpdateView URL.
        - view_delete_name: The name of the DeleteView URL.
        - create_object_data: A dictionary with data to create an object.
        - update_object_data: A dictionary with data to update the object.
        - update_success_url_name: The URL to redirect after successful update or delete.
        - permission_denied_message: Message displayed on permission denied.
        """

        # This is an abstract class and should not be run as a test case directly
        __test__ = False

        dashboard_view = True
        create_view = True
        public_list_view = True
        private_list_view = True
        detail_view = True
        update_view = True
        modal_update_view = False
        delete_view = True

        model = None

        view_dashboard_name = None
        view_create_name = None
        view_published_list_name = None
        view_private_list_name = None
        view_detail_name = None
        view_update_name = None
        view_modal_update_name = None
        view_delete_name = None
        create_object_data = None
        update_object_data = None
        update_success_url_name = None
        delete_success_url_name = None
        permission_denied_message = "Sorry, you don't have permission to access this page."

        related_objects = None
        published_object = None
        unpublished_object = None

        @classmethod
        def setUpTestData(cls):
            cls.owner_user = User.objects.create(username='owner')
            cls.non_owner_user = User.objects.create(username='non_owner')
            cls.staff_user = User.objects.create(username='staff', is_staff=True)

            cls.related_objects = cls.create_related_objects()

            cls.published_object = cls.create_published_object()
            cls.unpublished_object = cls.create_unpublished_object()

        @classmethod
        def create_related_objects(cls):
            """
            Create any related objects required by the model.
            Subclasses can override this method to create related objects.

            Returns:
                A dictionary of related objects that can be used in `create_object_data`.
            """
            return {}

        def related_objects_post_data(self):
            return {key: value.pk for key, value in self.related_objects.items()}

        @classmethod
        def create_published_object(cls):
            """
            Create a published object using `create_object_data` and related objects.

            Returns:
                The published object instance.
            """
            data = cls.create_object_data.copy()
            data['publication_status'] = 'published'
            # Inject related objects if any
            data.update(cls.related_objects)
            return cls.model.objects.create(owner=cls.owner_user, **data)

        @classmethod
        def create_unpublished_object(cls):
            """
            Create an unpublished object using `create_object_data` and related objects.

            Returns:
                The unpublished object instance.
            """
            data = cls.create_object_data.copy()
            data['publication_status'] = 'private'
            # Inject related objects if any
            data.update(cls.related_objects)
            return cls.model.objects.create(owner=cls.owner_user, **data)

        def setUp(self):
            self.client = Client()

        def get_dashboard_url(self):
            return reverse(self.view_dashboard_name)

        def get_create_url(self):
            return reverse(self.view_create_name)

        def get_list_url(self, publication_status='published', **kwargs):
            if publication_status == 'published':
                return reverse(self.view_published_list_name, kwargs=kwargs)
            elif publication_status == 'private':
                return reverse(self.view_private_list_name, kwargs=kwargs)

        def get_detail_url(self, pk):
            return reverse(self.view_detail_name, kwargs={'pk': pk})

        def get_update_url(self, pk):
            return reverse(self.view_update_name, kwargs={'pk': pk})

        def get_modal_update_url(self, pk):
            return reverse(self.view_modal_update_name, kwargs={'pk': pk})

        def get_delete_url(self, pk):
            return reverse(self.view_delete_name, kwargs={'pk': pk})

        def get_update_success_url(self, pk=None):
            url_name = self.update_success_url_name or self.view_detail_name
            return reverse(url_name, kwargs={'pk': pk})

        def get_delete_success_url(self, publication_status=None):
            url_name = self.delete_success_url_name or self.view_published_list_name
            return reverse(url_name)

        def compile_update_post_data(self):
            data = self.update_object_data.copy()
            data.update(self.related_objects_post_data())
            return data

        # -----------------------
        # ListView Test Cases
        # -----------------------

        def test_list_view_published_as_anonymous(self):
            if not self.public_list_view:
                self.skipTest("List view is not enabled for this test case.")
            response = self.client.get(self.get_list_url(publication_status='published'))
            self.assertEqual(response.status_code, 200)
            if self.dashboard_view:
                self.assertContains(response, self.get_dashboard_url())
            if self.create_view:
                self.assertNotContains(response, self.get_create_url())
            if self.private_list_view:
                self.assertNotContains(response, self.get_list_url(publication_status='private'))

        def test_list_view_published_as_authenticated_owner(self):
            if not self.public_list_view:
                self.skipTest("List view is not enabled for this test case.")
            self.client.force_login(self.owner_user)
            response = self.client.get(self.get_list_url(publication_status='published'))
            self.assertEqual(response.status_code, 200)
            if self.dashboard_view:
                self.assertContains(response, self.get_dashboard_url())
            if self.create_view:
                self.assertNotContains(response, self.get_create_url())
            if self.private_list_view:
                self.assertContains(response, self.get_list_url(publication_status='private'))

        def test_list_view_published_as_authenticated_non_owner(self):
            if not self.public_list_view:
                self.skipTest("List view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            response = self.client.get(self.get_list_url(publication_status='published'))
            self.assertEqual(response.status_code, 200)
            if self.dashboard_view:
                self.assertContains(response, self.get_dashboard_url())
            if self.create_view:
                self.assertNotContains(response, self.get_create_url())
            if self.private_list_view:
                self.assertContains(response, self.get_list_url(publication_status='private'))

        def test_list_view_published_as_staff_user(self):
            if not self.public_list_view:
                self.skipTest("List view is not enabled for this test case.")
            self.client.force_login(self.staff_user)
            response = self.client.get(self.get_list_url(publication_status='published'))
            self.assertEqual(response.status_code, 200)
            if self.dashboard_view:
                self.assertContains(response, self.get_dashboard_url())
            if self.create_view:
                self.assertContains(response, self.get_create_url())
            if self.private_list_view:
                self.assertContains(response, self.get_list_url(publication_status='private'))

        def test_list_view_private_as_anonymous(self):
            if not self.private_list_view:
                self.skipTest("List view is not enabled for this test case.")
            url = self.get_list_url(publication_status='private')
            response = self.client.get(url)
            login_url = settings.LOGIN_URL
            expected_redirect = f"{login_url}?next={url}"
            self.assertRedirects(response, expected_redirect)

        def test_list_view_private_as_authenticated_owner(self):
            if not self.private_list_view:
                self.skipTest("List view is not enabled for this test case")
            self.client.force_login(self.owner_user)
            response = self.client.get(self.get_list_url(publication_status='private'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '<th>Public</th>')
            if self.dashboard_view:
                self.assertContains(response, self.get_dashboard_url())
            if self.create_view:
                self.assertNotContains(response, self.get_create_url())
            if self.public_list_view:
                self.assertContains(response, self.get_list_url(publication_status='published'))

        def test_list_view_private_as_authenticated_non_owner(self):
            if not self.private_list_view:
                self.skipTest("List view is not enabled for this test case")
            self.client.force_login(self.non_owner_user)
            response = self.client.get(self.get_list_url(publication_status='private'))
            self.assertEqual(response.status_code, 200)
            if self.dashboard_view:
                self.assertContains(response, self.get_dashboard_url())
            if self.create_view:
                self.assertNotContains(response, self.get_create_url())
            if self.public_list_view:
                self.assertContains(response, self.get_list_url(publication_status='published'))

        def test_list_view_private_as_authenticated_staff_user(self):
            if not self.private_list_view:
                self.skipTest("List view is not enabled for this test case")
            self.client.force_login(self.staff_user)
            response = self.client.get(self.get_list_url(publication_status='private'))
            self.assertEqual(response.status_code, 200)
            if self.dashboard_view:
                self.assertContains(response, self.get_dashboard_url())
            if self.create_view:
                self.assertContains(response, self.get_create_url())
            if self.public_list_view:
                self.assertContains(response, self.get_list_url(publication_status='published'))

        # -----------------------
        # DetailView Test Cases
        # -----------------------

        def test_detail_view_published_as_anonymous(self):
            if not self.detail_view:
                self.skipTest("Detail view is not enabled for this test case.")
            url = self.get_detail_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            if self.update_view:
                self.assertNotContains(response, self.get_update_url(self.published_object.pk))
            if self.delete_view:
                self.assertNotContains(response, self.get_delete_url(self.published_object.pk))

        def test_detail_view_published_as_authenticated_owner(self):
            if not self.detail_view:
                self.skipTest("Detail view is not enabled for this test case.")
            self.client.force_login(self.owner_user)
            url = self.get_detail_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            if self.update_view:
                self.assertContains(response, self.get_update_url(self.published_object.pk))
            if self.delete_view:
                self.assertContains(response, self.get_delete_url(self.published_object.pk))

        def test_detail_view_published_as_authenticated_non_owner(self):
            if not self.detail_view:
                self.skipTest("Detail view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_detail_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            if self.update_view:
                self.assertNotContains(response, self.get_update_url(self.published_object.pk))
            if self.delete_view:
                self.assertNotContains(response, self.get_delete_url(self.published_object.pk))

        def test_detail_view_unpublished_as_owner(self):
            if not self.detail_view:
                self.skipTest("Detail view is not enabled for this test case.")
            self.client.force_login(self.owner_user)
            url = self.get_detail_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            if self.update_view:
                self.assertContains(response, self.get_update_url(self.unpublished_object.pk))
            if self.delete_view:
                self.assertContains(response, self.get_delete_url(self.unpublished_object.pk))

        def test_detail_view_unpublished_as_non_owner(self):
            if not self.detail_view:
                self.skipTest("Detail view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_detail_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_detail_view_unpublished_as_anonymous(self):
            if not self.detail_view:
                self.skipTest("Detail view is not enabled for this test case.")
            url = self.get_detail_url(self.unpublished_object.pk)
            response = self.client.get(url)
            login_url = settings.LOGIN_URL
            expected_redirect = f"{login_url}?next={url}"
            self.assertRedirects(response, expected_redirect)

        def test_detail_view_nonexistent_object(self):
            if not self.detail_view:
                self.skipTest("Detail view is not enabled for this test case.")
            url = self.get_detail_url(pk=9999)  # Assuming this PK does not exist
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

        # -----------------------
        # UpdateView Test Cases
        # -----------------------

        def test_update_view_get_published_as_anonymous(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            url = self.get_update_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_update_view_post_published_as_anonymous(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            url = self.get_update_url(self.published_object.pk)
            response = self.client.post(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_update_view_get_published_as_owner(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            # published objects should not be edited anymore
            self.client.force_login(self.owner_user)
            url = self.get_update_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_update_view_post_published_as_owner(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            # published objects should not be edited anymore
            self.client.force_login(self.owner_user)
            url = self.get_update_url(self.published_object.pk)
            response = self.client.post(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_update_view_get_published_as_non_owner(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_update_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_update_view_post_published_as_non_owner(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_update_url(self.published_object.pk)
            response = self.client.post(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_update_view_get_published_as_staff_user(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            # staff can edit any object
            self.client.force_login(self.staff_user)
            url = self.get_update_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        def test_update_view_post_published_as_staff_user(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            # staff can edit any object
            self.client.force_login(self.staff_user)
            url = self.get_update_url(self.published_object.pk)
            data = self.compile_update_post_data()
            response = self.client.post(url, data)
            self.assertRedirects(response, self.get_update_success_url(pk=self.published_object.pk))

        def test_update_view_get_unpublished_as_anonymous(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            url = self.get_update_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_update_view_post_unpublished_as_anonymous(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            url = self.get_update_url(self.unpublished_object.pk)
            response = self.client.post(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_update_view_get_unpublished_as_owner(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            self.client.force_login(self.owner_user)
            url = self.get_update_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        def test_update_view_post_unpublished_as_owner(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            self.client.force_login(self.owner_user)
            url = self.get_update_url(self.unpublished_object.pk)
            data = self.compile_update_post_data()
            response = self.client.post(url, data)
            self.assertRedirects(response, self.get_update_success_url(pk=self.unpublished_object.pk))

        def test_update_view_get_unpublished_as_non_owner(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_update_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_update_view_post_unpublished_as_non_owner(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_update_url(self.unpublished_object.pk)
            response = self.client.post(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_update_view_get_unpublished_as_staff_user(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            # staff can edit any object
            self.client.force_login(self.staff_user)
            url = self.get_update_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        def test_update_view_post_unpublished_as_staff_user(self):
            if not self.update_view:
                self.skipTest("Update view is not enabled for this test case.")
            # staff can edit any object
            self.client.force_login(self.staff_user)
            url = self.get_update_url(self.unpublished_object.pk)
            data = self.compile_update_post_data()
            response = self.client.post(url, data)
            self.assertRedirects(response, self.get_update_success_url(pk=self.unpublished_object.pk))

        # -----------------------
        # ModalUpdateView Test Cases
        # -----------------------

        def test_modal_update_view_get_published_as_anonymous(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            url = self.get_modal_update_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_modal_update_view_post_published_as_anonymous(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            url = self.get_modal_update_url(self.published_object.pk)
            response = self.client.post(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_modal_update_view_get_published_as_owner(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            # published objects should not be edited anymore
            self.client.force_login(self.owner_user)
            url = self.get_modal_update_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_modal_update_view_post_published_as_owner(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            # published objects should not be edited anymore
            self.client.force_login(self.owner_user)
            url = self.get_modal_update_url(self.published_object.pk)
            response = self.client.post(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_modal_update_view_get_published_as_non_owner(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_modal_update_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_modal_update_view_post_published_as_non_owner(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_modal_update_url(self.published_object.pk)
            response = self.client.post(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_modal_update_view_get_published_as_staff_user(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            # staff can edit any object
            self.client.force_login(self.staff_user)
            url = self.get_modal_update_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        def test_modal_update_view_post_published_as_staff_user(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            # staff can edit any object
            self.client.force_login(self.staff_user)
            url = self.get_modal_update_url(self.published_object.pk)
            data = self.compile_update_post_data()
            response = self.client.post(url, data)
            self.assertRedirects(response, self.get_update_success_url(pk=self.published_object.pk))

        def test_modal_update_view_get_unpublished_as_anonymous(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            url = self.get_modal_update_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_modal_update_view_post_unpublished_as_anonymous(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            url = self.get_modal_update_url(self.unpublished_object.pk)
            response = self.client.post(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_modal_update_view_get_unpublished_as_owner(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            self.client.force_login(self.owner_user)
            url = self.get_modal_update_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        def test_modal_update_view_post_unpublished_as_owner(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            self.client.force_login(self.owner_user)
            url = self.get_modal_update_url(self.unpublished_object.pk)
            data = self.compile_update_post_data()
            response = self.client.post(url, data)
            self.assertRedirects(response, self.get_update_success_url(pk=self.unpublished_object.pk))

        def test_modal_update_view_get_unpublished_as_non_owner(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_modal_update_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_modal_update_view_post_unpublished_as_non_owner(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            url = self.get_modal_update_url(self.unpublished_object.pk)
            response = self.client.post(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_modal_update_view_get_unpublished_as_staff_user(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            # staff can edit any object
            self.client.force_login(self.staff_user)
            url = self.get_modal_update_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        def test_modal_update_view_post_unpublished_as_staff_user(self):
            if not self.modal_update_view:
                self.skipTest("ModalUpdate view is not enabled for this test case.")
            # staff can edit any object
            self.client.force_login(self.staff_user)
            url = self.get_modal_update_url(self.unpublished_object.pk)
            data = self.compile_update_post_data()
            response = self.client.post(url, data)
            self.assertRedirects(response, self.get_update_success_url(pk=self.unpublished_object.pk))

        # -----------------------
        # DeleteView Test Cases
        # -----------------------

        def tes_delete_view_get_published_as_anonymous(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            url = self.get_delete_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def tes_delete_view_post_published_as_anonymous(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            url = self.get_delete_url(self.published_object.pk)
            response = self.client.post(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_delete_view_get_published_as_owner(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            # published objects should not be deleted because other objects might depend on them
            self.client.force_login(self.owner_user)
            response = self.client.get(self.get_delete_url(self.published_object.pk))
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_delete_view_post_published_as_owner(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            # published objects should not be deleted because other objects might depend on them
            self.client.force_login(self.owner_user)
            response = self.client.post(self.get_delete_url(self.published_object.pk))
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_delete_view_get_published_as_non_owner(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            response = self.client.get(self.get_delete_url(self.published_object.pk))
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_delete_view_post_published_as_non_owner(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            response = self.client.post(self.get_delete_url(self.published_object.pk))
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_delete_view_get_published_as_staff_user(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            # Staff users can delete any object
            self.client.force_login(self.staff_user)
            response = self.client.get(self.get_delete_url(self.published_object.pk))
            self.assertEqual(response.status_code, 200)

        def test_delete_view_post_published_as_staff_user(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            # Staff users can delete any object
            self.client.force_login(self.staff_user)
            response = self.client.post(self.get_delete_url(self.published_object.pk), follow=True)
            with self.assertRaises(self.model.DoesNotExist):
                self.model.objects.get(pk=self.published_object.pk)
            self.assertRedirects(response, self.get_delete_success_url(publication_status='published'))

        def test_delete_view_get_unpublished_as_anonymous(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            url = self.get_delete_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_delete_view_post_unpublished_as_anonymous(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            url = self.get_delete_url(self.unpublished_object.pk)
            response = self.client.post(url)
            self.assertRedirects(response, f"{settings.LOGIN_URL}?next={url}")

        def test_delete_view_get_unpublished_as_owner(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            self.client.force_login(self.owner_user)
            response = self.client.get(self.get_delete_url(self.unpublished_object.pk))
            self.assertEqual(response.status_code, 200)

        def test_delete_view_post_unpublished_as_owner(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            self.client.force_login(self.owner_user)
            response = self.client.post(self.get_delete_url(self.unpublished_object.pk), follow=True)
            with self.assertRaises(self.model.DoesNotExist):
                self.model.objects.get(pk=self.unpublished_object.pk)
            self.assertRedirects(response, self.get_delete_success_url(publication_status='private'))

        def test_delete_view_get_unpublished_as_non_owner(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            response = self.client.get(self.get_delete_url(self.unpublished_object.pk))
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_delete_view_post_unpublished_as_non_owner(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            self.client.force_login(self.non_owner_user)
            response = self.client.post(self.get_delete_url(self.unpublished_object.pk))
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_delete_view_get_unpublished_as_staff_user(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            # Staff users can delete any object
            self.client.force_login(self.staff_user)
            response = self.client.get(self.get_delete_url(self.unpublished_object.pk))
            self.assertEqual(response.status_code, 200)

        def test_delete_view_post_unpublished_as_staff_user(self):
            if not self.delete_view:
                self.skipTest("Delete view is not enabled for this test case.")
            # Staff users can delete any object
            self.client.force_login(self.staff_user)
            response = self.client.post(self.get_delete_url(self.unpublished_object.pk), follow=True)
            with self.assertRaises(self.model.DoesNotExist):
                self.model.objects.get(pk=self.unpublished_object.pk)
            self.assertRedirects(response, self.get_delete_success_url(publication_status='private'))
