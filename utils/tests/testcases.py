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
    member_permissions = None

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username='owner')
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
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
        - form_update_data: A dictionary with data to update the object.
        - success_url: The URL to redirect after successful update or delete.
        - permission_denied_message: Message displayed on permission denied.
        """

        # This is an abstract class and should not be run as a test case directly
        __test__ = False

        model = None
        view_detail_name = None
        view_update_name = None
        view_delete_name = None
        create_object_data = None
        form_update_data = None
        success_url = None
        permission_denied_message = "Sorry, you don't have permission to access this page."

        related_objects = None
        published_object = None
        unpublished_object = None

        @classmethod
        def setUpTestData(cls):
            cls.owner_user = User.objects.create(username='owner')
            cls.non_owner_user = User.objects.create(username='nonowner')

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

        def get_detail_url(self, pk):
            return reverse(self.view_detail_name, kwargs={'pk': pk})

        def get_update_url(self, pk):
            return reverse(self.view_update_name, kwargs={'pk': pk})

        def get_delete_url(self, pk):
            return reverse(self.view_delete_name, kwargs={'pk': pk})

        # -----------------------
        # DetailView Test Cases
        # -----------------------

        def test_detail_view_published_as_anonymous(self):
            url = self.get_detail_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, self.get_update_url(self.published_object.pk))
            self.assertNotContains(response, self.get_delete_url(self.published_object.pk))

        def test_detail_view_published_as_authenticated_owner(self):
            self.client.force_login(self.owner_user)
            url = self.get_detail_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, self.get_update_url(self.published_object.pk))
            self.assertContains(response, self.get_delete_url(self.published_object.pk))

        def test_detail_view_published_as_authenticated_non_owner(self):
            self.client.force_login(self.non_owner_user)
            url = self.get_detail_url(self.published_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, self.get_update_url(self.published_object.pk))
            self.assertNotContains(response, self.get_delete_url(self.published_object.pk))

        def test_detail_view_unpublished_as_owner(self):
            self.client.force_login(self.owner_user)
            url = self.get_detail_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, self.get_update_url(self.unpublished_object.pk))
            self.assertContains(response, self.get_delete_url(self.unpublished_object.pk))

        def test_detail_view_unpublished_as_non_owner(self):
            self.client.force_login(self.non_owner_user)
            url = self.get_detail_url(self.unpublished_object.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, self.permission_denied_message, status_code=403)

        def test_detail_view_unpublished_as_anonymous(self):
            url = self.get_detail_url(self.unpublished_object.pk)
            response = self.client.get(url)
            login_url = settings.LOGIN_URL
            expected_redirect = f"{login_url}?next={url}"
            self.assertRedirects(response, expected_redirect)

        def test_detail_view_nonexistent_object(self):
            url = self.get_detail_url(pk=9999)  # Assuming this PK does not exist
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

        # -----------------------
        # UpdateView Test Cases
        # -----------------------
        # TODO: Implement update test functions
        # def test_update_view_published_as_owner(self):
        #     self.client.login(username='owner', password='password123')
        #     url = self.get_update_url(self.published_object.pk)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 200)
        #     self.assertContains(response, "Edit")
        #
        # def test_update_view_published_as_non_owner(self):
        #     self.client.login(username='nonowner', password='password123')
        #     url = self.get_update_url(self.published_object.pk)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 403)
        #     self.assertContains(response, self.permission_denied_message, status_code=403)
        #
        # def test_update_view_published_as_anonymous(self):
        #     url = self.get_update_url(self.published_object.pk)
        #     response = self.client.get(url)
        #     login_url = settings.LOGIN_URL
        #     expected_redirect = f"{login_url}?next={url}"
        #     self.assertRedirects(response, expected_redirect)
        #
        # def test_update_view_unpublished_as_owner(self):
        #     self.client.login(username='owner', password='password123')
        #     url = self.get_update_url(self.unpublished_object.pk)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 200)
        #     self.assertContains(response, "Edit")
        #
        # def test_update_view_unpublished_as_non_owner(self):
        #     self.client.login(username='nonowner', password='password123')
        #     url = self.get_update_url(self.unpublished_object.pk)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 403)
        #     self.assertContains(response, self.permission_denied_message, status_code=403)
        #
        # def test_update_view_unpublished_as_anonymous(self):
        #     url = self.get_update_url(self.unpublished_object.pk)
        #     response = self.client.get(url)
        #     login_url = settings.LOGIN_URL
        #     expected_redirect = f"{login_url}?next={url}"
        #     self.assertRedirects(response, expected_redirect)
        #
        # def test_update_view_nonexistent_object(self):
        #     url = self.get_update_url(pk=9999)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 404)
        #
        # def test_update_view_post_as_owner(self):
        #     self.client.login(username='owner', password='password123')
        #     url = self.get_update_url(self.published_object.pk)
        #     data = self.form_update_data
        #     response = self.client.post(url, data)
        #     self.assertRedirects(response, self.success_url)
        #     self.published_object.refresh_from_db()
        #     # Adjust field names based on your model
        #     for key, value in data.items():
        #         self.assertEqual(getattr(self.published_object, key), value)

        # -----------------------
        # DeleteView Test Cases
        # -----------------------
        # TODO: Implement delete test functions
        # def test_delete_view_published_as_owner(self):
        #     self.client.login(username='owner', password='password123')
        #     url = self.get_delete_url(self.published_object.pk)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 200)
        #     self.assertContains(response, "Delete")
        #
        # def test_delete_view_published_as_non_owner(self):
        #     self.client.login(username='nonowner', password='password123')
        #     url = self.get_delete_url(self.published_object.pk)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 403)
        #     self.assertContains(response, self.permission_denied_message, status_code=403)
        #
        # def test_delete_view_published_as_anonymous(self):
        #     url = self.get_delete_url(self.published_object.pk)
        #     response = self.client.get(url)
        #     login_url = settings.LOGIN_URL
        #     expected_redirect = f"{login_url}?next={url}"
        #     self.assertRedirects(response, expected_redirect)
        #
        # def test_delete_view_unpublished_as_owner(self):
        #     self.client.login(username='owner', password='password123')
        #     url = self.get_delete_url(self.unpublished_object.pk)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 200)
        #     self.assertContains(response, "Delete")
        #
        # def test_delete_view_unpublished_as_non_owner(self):
        #     self.client.login(username='nonowner', password='password123')
        #     url = self.get_delete_url(self.unpublished_object.pk)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 403)
        #     self.assertContains(response, self.permission_denied_message, status_code=403)
        #
        # def test_delete_view_unpublished_as_anonymous(self):
        #     url = self.get_delete_url(self.unpublished_object.pk)
        #     response = self.client.get(url)
        #     login_url = settings.LOGIN_URL
        #     expected_redirect = f"{login_url}?next={url}"
        #     self.assertRedirects(response, expected_redirect)
        #
        # def test_delete_view_nonexistent_object(self):
        #     url = self.get_delete_url(pk=9999)
        #     response = self.client.get(url)
        #     self.assertEqual(response.status_code, 404)
        #
        # def test_delete_view_post_as_owner(self):
        #     self.client.login(username='owner', password='password123')
        #     url = self.get_delete_url(self.published_object.pk)
        #     response = self.client.post(url)
        #     self.assertRedirects(response, self.success_url)
        #     with self.assertRaises(self.model.DoesNotExist):
        #         self.model.objects.get(pk=self.published_object.pk)
