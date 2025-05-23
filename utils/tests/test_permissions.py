from unittest.mock import MagicMock, Mock

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from ..permissions import (
    HasModelPermission,
    IsStaffOrReadOnly,
    UserCreatedObjectPermission,
)


class IsStaffOrReadOnlyPermissionTestCase(TestCase):
    def setUp(self):
        self.permission = IsStaffOrReadOnly()
        self.factory = APIRequestFactory()

        self.staff_user = User.objects.create_user(username="staffuser", is_staff=True)
        self.regular_user = User.objects.create_user(
            username="regularuser", is_staff=False
        )

    def make_request(self, method, user=None, data=None):
        """
        Helper method to create a DRF Request object with the specified method and user.
        """
        method_lower = method.lower()
        if method_lower == "get":
            request = self.factory.get("/fake-url/", data=data, format="json")
        elif method_lower == "post":
            request = self.factory.post("/fake-url/", data=data, format="json")
        elif method_lower == "put":
            request = self.factory.put("/fake-url/", data=data, format="json")
        elif method_lower == "patch":
            request = self.factory.patch("/fake-url/", data=data, format="json")
        elif method_lower == "delete":
            request = self.factory.delete("/fake-url/")
        elif method_lower == "head":
            request = self.factory.head("/fake-url/")
        elif method_lower == "options":
            request = self.factory.options("/fake-url/")
        else:
            raise ValueError(f"Unsupported HTTP method: {method.upper()}")

        if user:
            force_authenticate(request, user=user)

        # Wrap the request with DRF's Request to add additional attributes
        return Request(request)

    def test_safe_methods_allow_any(self):
        """
        Ensure that safe methods are allowed for any user, authenticated or not.
        """
        safe_methods = ["GET", "HEAD", "OPTIONS"]
        for method in safe_methods:
            with self.subTest(method=method):
                request = self.make_request(method)
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertTrue(
                    has_perm, f"Safe method {method} should be allowed for any user."
                )

    def test_write_methods_denied_for_unauthenticated_users(self):
        """
        Ensure that write methods are denied for unauthenticated users.
        """
        write_methods = ["POST", "PUT", "PATCH", "DELETE"]
        for method in write_methods:
            with self.subTest(method=method):
                request = self.make_request(method, data={"name": "Test"})
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertFalse(
                    has_perm,
                    f"Write method {method} should be denied for unauthenticated users.",
                )

    def test_write_methods_denied_for_authenticated_non_staff_users(self):
        """
        Ensure that write methods are denied for authenticated non-staff users.
        """
        write_methods = ["POST", "PUT", "PATCH", "DELETE"]
        for method in write_methods:
            with self.subTest(method=method):
                request = self.make_request(
                    method, user=self.regular_user, data={"name": "Test"}
                )
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertFalse(
                    has_perm,
                    f"Write method {method} should be denied for non-staff users.",
                )

    def test_write_methods_allowed_for_staff_users(self):
        """
        Ensure that write methods are allowed for authenticated staff users.
        """
        write_methods = ["POST", "PUT", "PATCH", "DELETE"]
        self.assertTrue(self.staff_user.is_staff)
        for method in write_methods:
            with self.subTest(method=method):
                request = self.make_request(
                    method, user=self.staff_user, data={"name": "Test"}
                )
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertTrue(
                    has_perm,
                    f"Write method {method} should be allowed for staff users.",
                )


class SampleModel:
    _meta = Mock()
    _meta.model_name = "samplemodel"
    _meta.app_label = "utils"

    def __init__(self, owner, publication_status):
        self.owner = owner
        self.publication_status = publication_status


class TestUserCreatedObjectPermission(TestCase):
    def setUp(self):
        self.owner_user = Mock(spec=User)
        self.owner_user.is_authenticated = True
        self.owner_user.has_perm = Mock(return_value=False)
        self.owner_user.is_staff = False

        self.moderator_user = Mock(spec=User)
        self.moderator_user.is_authenticated = True
        self.moderator_user.has_perm = Mock(return_value=True)
        self.moderator_user.is_staff = False

        self.staff_user = Mock(spec=User)
        self.staff_user.is_authenticated = True
        self.staff_user.has_perm = Mock(return_value=False)
        self.staff_user.is_staff = True

        self.other_user = Mock(spec=User)
        self.other_user.is_authenticated = True
        self.other_user.has_perm = Mock(return_value=False)
        self.other_user.is_staff = False

        self.anonymous_user = Mock(spec=User)
        self.anonymous_user.is_authenticated = False

        self.public_obj = SampleModel(
            owner=self.owner_user, publication_status="published"
        )
        self.review_obj = SampleModel(
            owner=self.owner_user, publication_status="review"
        )
        self.private_obj = SampleModel(
            owner=self.owner_user, publication_status="private"
        )
        self.undefined_status_obj = SampleModel(
            owner=self.owner_user, publication_status=None
        )

        self.permission = UserCreatedObjectPermission()

    def create_request(self, method="GET", user=None, data=None):
        mock_request = Mock()
        mock_request.method = method
        mock_request.user = user
        mock_request.data = data or {}
        return mock_request

    def create_view(self, action=None):
        mock_view = Mock()
        mock_view.action = action
        return mock_view

    def test_has_permission_list_action_any_user(self):
        request = self.create_request(user=self.anonymous_user)
        view = self.create_view(action="list")
        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_retrieve_action_any_user(self):
        request = self.create_request(user=self.anonymous_user)
        view = self.create_view(action="retrieve")
        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_create_action_authenticated_user(self):
        request = self.create_request(user=self.owner_user)
        view = self.create_view(action="create")

        # When view.get_queryset() is not implemented, the permission should default to False
        self.assertFalse(self.permission.has_permission(request, view))

    def test_has_permission_create_action_unauthenticated_user(self):
        request = self.create_request(user=self.anonymous_user)
        view = self.create_view(action="create")
        self.assertFalse(self.permission.has_permission(request, view))

    def test_has_permission_create_action_authenticated_user_with_model_permission(
        self,
    ):
        # Setup a user with model add permission
        user_with_perm = Mock(spec=User)
        user_with_perm.is_authenticated = True
        user_with_perm.is_staff = False
        # Configure has_perm to return True for the specific model permission
        user_with_perm.has_perm = Mock(return_value=True)

        request = self.create_request(user=user_with_perm)

        # Setup a view with queryset that has a model
        view = self.create_view(action="create")
        model_mock = Mock()
        model_mock._meta.app_label = "testapp"
        model_mock._meta.model_name = "testmodel"
        queryset_mock = Mock()
        queryset_mock.model = model_mock
        view.get_queryset = Mock(return_value=queryset_mock)

        # Test - should allow create with model permission
        self.assertTrue(self.permission.has_permission(request, view))

        # Verify the permission was checked correctly
        user_with_perm.has_perm.assert_called_with("testapp.add_testmodel")

    def test_has_permission_create_action_authenticated_user_without_model_permission(
        self,
    ):
        # Setup a user without model add permission
        user_without_perm = Mock(spec=User)
        user_without_perm.is_authenticated = True
        user_without_perm.is_staff = False
        # Configure has_perm to return False for any permission
        user_without_perm.has_perm = Mock(return_value=False)

        request = self.create_request(user=user_without_perm)

        # Setup a view with queryset that has a model
        view = self.create_view(action="create")
        model_mock = Mock()
        model_mock._meta.app_label = "testapp"
        model_mock._meta.model_name = "testmodel"
        queryset_mock = Mock()
        queryset_mock.model = model_mock
        view.get_queryset = Mock(return_value=queryset_mock)

        # Test - should deny create without model permission
        self.assertFalse(self.permission.has_permission(request, view))

        # Verify the permission was checked correctly
        user_without_perm.has_perm.assert_called_with("testapp.add_testmodel")

    def test_has_permission_create_action_staff_user(self):
        # Staff users should be able to create objects without explicit permission
        request = self.create_request(user=self.staff_user)

        # Setup a view with queryset that has a model
        view = self.create_view(action="create")
        model_mock = Mock()
        model_mock._meta.app_label = "testapp"
        model_mock._meta.model_name = "testmodel"
        queryset_mock = Mock()
        queryset_mock.model = model_mock
        view.get_queryset = Mock(return_value=queryset_mock)

        # Test - staff should always be allowed
        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_update_action_authenticated_user(self):
        request = self.create_request(user=self.owner_user)
        view = self.create_view(action="update")
        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_update_action_unauthenticated_user(self):
        request = self.create_request(user=self.anonymous_user)
        view = self.create_view(action="update")
        self.assertFalse(self.permission.has_permission(request, view))

    def test_has_object_permission_safe_published_any_user(self):
        request = self.create_request(method="GET", user=self.other_user)
        view = Mock()
        obj = self.public_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_review_owner(self):
        request = self.create_request(method="GET", user=self.owner_user)
        view = Mock()
        obj = self.review_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_review_moderator(self):
        request = self.create_request(method="GET", user=self.moderator_user)
        view = Mock()
        obj = self.review_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_review_other_user(self):
        request = self.create_request(method="GET", user=self.other_user)
        view = Mock()
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=False)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_private_owner(self):
        request = self.create_request(method="GET", user=self.owner_user)
        view = Mock()
        obj = self.private_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_private_other_user(self):
        request = self.create_request(method="GET", user=self.other_user)
        view = Mock()
        obj = self.private_obj
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_undefined_status(self):
        request = self.create_request(method="GET", user=self.owner_user)
        view = Mock()
        obj = self.undefined_status_obj
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_write_owner_modify_publication_status_as_moderator(
        self,
    ):
        request = self.create_request(
            method="PUT", user=self.owner_user, data={"publication_status": "published"}
        )
        view = Mock()
        obj = self.public_obj
        self.permission._is_moderator = Mock(return_value=True)
        self.assertTrue(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.owner_user, obj)

    def test_has_object_permission_write_owner_modify_publication_status_not_moderator(
        self,
    ):
        request = self.create_request(
            method="PUT", user=self.owner_user, data={"publication_status": "published"}
        )
        view = Mock()
        obj = self.public_obj
        self.permission._is_moderator = Mock(return_value=False)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.owner_user, obj)

    def test_has_object_permission_write_owner_modify_other_fields(self):
        request = self.create_request(
            method="PATCH", user=self.owner_user, data={"title": "New Title"}
        )
        view = Mock()
        obj = self.public_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_write_moderator_modify_non_private_object(self):
        request = self.create_request(
            method="PUT", user=self.moderator_user, data={"title": "Updated Title"}
        )
        view = Mock()
        obj = self.public_obj
        self.permission._is_moderator = Mock(return_value=True)
        self.assertTrue(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.moderator_user, obj)

    def test_has_object_permission_write_moderator_modify_private_object_not_owner(
        self,
    ):
        request = self.create_request(
            method="PUT", user=self.moderator_user, data={"title": "Updated Title"}
        )
        view = Mock()
        obj = self.private_obj
        self.permission._is_moderator = Mock(return_value=True)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.moderator_user, obj)

    def test_has_object_permission_write_moderator_modify_private_object_as_owner(self):
        request = self.create_request(
            method="PUT", user=self.owner_user, data={"title": "Updated Title"}
        )
        view = Mock()
        obj = self.private_obj
        self.permission._is_moderator = Mock(return_value=True)
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_write_other_user(self):
        request = self.create_request(method="DELETE", user=self.other_user, data={})
        view = Mock()
        obj = self.public_obj
        self.permission._is_moderator = Mock(return_value=False)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.other_user, obj)

    def test_check_safe_permissions_published(self):
        request = self.create_request(method="GET", user=self.other_user)
        obj = self.public_obj
        result = self.permission._check_safe_permissions(request, obj)
        self.assertTrue(result)

    def test_check_safe_permissions_review_owner(self):
        request = self.create_request(method="GET", user=self.owner_user)
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=False)
        result = self.permission._check_safe_permissions(request, obj)
        self.assertTrue(result)

    def test_check_safe_permissions_review_moderator(self):
        request = self.create_request(method="GET", user=self.moderator_user)
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=True)
        result = self.permission._check_safe_permissions(request, obj)
        self.assertTrue(result)
        self.permission._is_moderator.assert_called_with(self.moderator_user, obj)

    def test_check_safe_permissions_review_other_user(self):
        request = self.create_request(method="GET", user=self.other_user)
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=False)
        result = self.permission._check_safe_permissions(request, obj)
        self.assertFalse(result)
        self.permission._is_moderator.assert_called_with(self.other_user, obj)

    def test_check_safe_permissions_private_owner(self):
        request = self.create_request(method="GET", user=self.owner_user)
        obj = self.private_obj
        result = self.permission._check_safe_permissions(request, obj)
        self.assertTrue(result)

    def test_check_safe_permissions_private_other_user(self):
        request = self.create_request(method="GET", user=self.other_user)
        obj = self.private_obj
        result = self.permission._check_safe_permissions(request, obj)
        self.assertFalse(result)

    def test_check_safe_permissions_undefined_status(self):
        request = self.create_request(method="GET", user=self.owner_user)
        obj = self.undefined_status_obj
        result = self.permission._check_safe_permissions(request, obj)
        self.assertFalse(result)

    def test_is_moderator_with_permission(self):
        mock_user_instance = self.moderator_user
        mock_user_instance.has_perm.return_value = True
        obj = self.public_obj
        result = self.permission._is_moderator(mock_user_instance, obj)
        self.assertTrue(result)
        mock_user_instance.has_perm.assert_called_with("utils.can_moderate_samplemodel")

    def test_is_moderator_with_staff(self):
        mock_user_instance = self.staff_user
        obj = self.public_obj
        result = self.permission._is_moderator(mock_user_instance, obj)
        self.assertTrue(result)
        mock_user_instance.has_perm.assert_not_called()

    def test_is_moderator_without_permission_or_staff(self):
        mock_user_instance = self.other_user
        obj = self.public_obj
        result = self.permission._is_moderator(mock_user_instance, obj)
        self.assertFalse(result)
        mock_user_instance.has_perm.assert_called_with("utils.can_moderate_samplemodel")

    def test_is_moderator_with_permission_false_staff_false(self):
        mock_user_instance = self.moderator_user
        mock_user_instance.has_perm.return_value = False
        mock_user_instance.is_staff = False
        obj = self.public_obj
        result = self.permission._is_moderator(mock_user_instance, obj)
        self.assertFalse(result)
        mock_user_instance.has_perm.assert_called_with("utils.can_moderate_samplemodel")

    def test_has_object_permission_no_publication_status(self):
        request = self.create_request(method="GET", user=self.owner_user)
        view = Mock()
        obj = self.undefined_status_obj
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_method_no_publication_status(self):
        request = self.create_request(method="HEAD", user=self.owner_user)
        view = Mock()
        obj = self.undefined_status_obj
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_write_method_no_data(self):
        request = self.create_request(method="PUT", user=self.owner_user, data={})
        view = Mock()
        obj = self.public_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_write_method_not_owner_not_moderator(self):
        request = self.create_request(
            method="PATCH", user=self.other_user, data={"title": "Hack"}
        )
        view = Mock()
        obj = self.public_obj
        self.permission._is_moderator = Mock(return_value=False)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.other_user, obj)

    def test_has_permission_no_action(self):
        request = self.create_request(user=self.owner_user)
        view = self.create_view(action=None)
        self.assertTrue(
            self.permission.has_permission(request, view)
        )  # Defaults to authenticated

    def test_has_permission_no_action_unauthenticated(self):
        request = self.create_request(user=self.anonymous_user)
        view = self.create_view(action=None)
        self.assertFalse(self.permission.has_permission(request, view))


class HasModelPermissionTestCase(TestCase):
    # TODO: EOL this class

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = HasModelPermission()
        self.user = MagicMock(spec=User)
        self.view = MagicMock(spec=APIView)
        self.view.action = "test_action"
        self.view.permission_required = {
            "test_action": ["app.view_model", "app.change_model"]
        }

    def test_has_permission_returns_True_for_not_authenticated(self):
        request = self.factory.get("/any-url")
        self.user.is_authenticated = False
        request.user = self.user
        # This should return True because for the non-authenticated users, the permission_check should be skipped to
        # progress to the authentication check, which will raise HTTP_401_UNAUTHORIZED
        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_has_permission_raises_improperly_configured_when_missing_permission_required_attribute(
        self,
    ):
        view = MagicMock(spec=APIView)
        request = self.factory.get("/any-url")
        request.user = self.user
        view.request = request
        with self.assertRaises(ImproperlyConfigured):
            self.permission.has_permission(request, view)

    def test_action_not_in_permission_required(self):
        request = self.factory.get("/any-url")
        request.user = self.user
        self.view.permission_required = {"other_action": "app.view_model"}
        with self.assertRaises(ImproperlyConfigured):
            self.permission.has_permission(request, self.view)

    def test_no_specific_permission_required(self):
        request = self.factory.get("/any-url")
        request.user = self.user
        self.view.permission_required = {"test_action": None}
        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_permission_required_user_does_not_have_it(self):
        request = self.factory.get("/any-url")
        request.user = self.user
        self.view.permission_required = {"test_action": "app.view_model"}
        self.view.action = "test_action"
        request.user.has_perm = MagicMock(return_value=False)
        self.assertFalse(self.permission.has_permission(request, self.view))

    def test_permission_required_user_has_it(self):
        request = self.factory.get("/any-url")
        request.user = self.user
        self.view.permission_required = {"test_action": "app.view_model"}
        self.view.action = "test_action"
        request.user.has_perm = MagicMock(return_value=True)
        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_multiple_permissions_required_user_has_all(self):
        request = self.factory.get("/any-url")
        request.user = self.user
        request.user.has_perm = MagicMock(
            side_effect=lambda perm: perm in ["app.view_model", "app.change_model"]
        )
        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_multiple_permissions_required_user_lacks_one(self):
        request = self.factory.get("/any-url")
        request.user = self.user
        request.user.has_perm = MagicMock(
            side_effect=lambda perm: perm == "app.view_model"
        )
        self.assertFalse(self.permission.has_permission(request, self.view))

    def test_action_without_permission_entry(self):
        request = self.factory.get("/any-url")
        request.user = self.user
        self.user.is_authenticated = True
        self.view.action = "unlisted_action"
        with self.assertRaises(ImproperlyConfigured):
            self.permission.has_permission(request, self.view)

    def test_incorrect_permission_required_type(self):
        request = self.factory.get("/any-url")
        request.user = self.user
        self.user.is_authenticated = True
        self.view.permission_required = ["app.view_model"]
        with self.assertRaises(ImproperlyConfigured):
            self.permission.has_permission(request, self.view)

    def test_options_method_is_always_allowed(self):
        request = self.factory.options("/any-url")
        request.user = self.user

        request.user.is_authenticated = False
        self.assertTrue(self.permission.has_permission(request, self.view))

        request.user.is_authenticated = True
        request.user.has_perm = MagicMock(return_value=True)
        self.assertTrue(self.permission.has_permission(request, self.view))

        request.user.is_authenticated = True
        request.user.has_perm = MagicMock(return_value=False)
        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_head_method_is_always_allowed(self):
        request = self.factory.head("/any-url")
        request.user = self.user

        request.user.is_authenticated = False
        self.assertTrue(self.permission.has_permission(request, self.view))

        request.user.is_authenticated = True
        request.user.has_perm = MagicMock(return_value=True)
        self.assertTrue(self.permission.has_permission(request, self.view))

        request.user.is_authenticated = True
        request.user.has_perm = MagicMock(return_value=False)
        self.assertTrue(self.permission.has_permission(request, self.view))
