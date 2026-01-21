from unittest.mock import Mock

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.test import RequestFactory, TestCase
from factory.django import mute_signals
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from case_studies.soilcom.models import Collection
from utils.object_management.models import UserCreatedObject

from ..permissions import (
    GlobalObjectPermission,
    UserCreatedObjectPermission,
)


class ReviewWorkflowPermissionTests(TestCase):
    """Test the permissions for the review workflow."""

    def setUp(self):
        # Create users
        self.owner = User.objects.create_user(username="owner")
        self.moderator = User.objects.create_user(username="moderator")
        self.regular_user = User.objects.create_user(username="regular")

        # Add moderator permissions
        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        self.moderator.user_permissions.add(permission)

        with mute_signals(post_save):
            # Create test collections in different states
            self.private_collection = Collection.objects.create(
                name="Private Collection",
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

        with mute_signals(post_save):
            self.review_collection = Collection.objects.create(
                name="Review Collection",
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

        with mute_signals(post_save):
            self.published_collection = Collection.objects.create(
                name="Published Collection",
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

        # Create permission checker
        self.permission_checker = UserCreatedObjectPermission()
        self.factory = RequestFactory()

    def test_submit_permission(self):
        """Test permission to submit an object for review."""
        # Owner should be able to submit their private object
        request = self.factory.post("/")
        request.user = self.owner
        self.assertTrue(
            self.permission_checker.has_submit_permission(
                request, self.private_collection
            )
        )

        # Regular user should not be able to submit someone else's private object
        request.user = self.regular_user
        self.assertFalse(
            self.permission_checker.has_submit_permission(
                request, self.private_collection
            )
        )

        # No one should be able to submit an object already in review
        request.user = self.owner
        self.assertFalse(
            self.permission_checker.has_submit_permission(
                request, self.review_collection
            )
        )

    def test_withdraw_permission(self):
        """Test permission to withdraw an object from review."""
        # Owner should be able to withdraw their object from review
        request = self.factory.post("/")
        request.user = self.owner
        self.assertTrue(
            self.permission_checker.has_withdraw_permission(
                request, self.review_collection
            )
        )

        # Regular user should not be able to withdraw someone else's object
        request.user = self.regular_user
        self.assertFalse(
            self.permission_checker.has_withdraw_permission(
                request, self.review_collection
            )
        )

        # No one should be able to withdraw a private object
        request.user = self.owner
        self.assertFalse(
            self.permission_checker.has_withdraw_permission(
                request, self.private_collection
            )
        )

    def test_approve_permission(self):
        """Test permission to approve an object."""
        # Moderator should be able to approve an object in review
        request = self.factory.post("/")
        request.user = self.moderator
        self.assertTrue(
            self.permission_checker.has_approve_permission(
                request, self.review_collection
            )
        )

        # Owner should not be able to approve their own object
        request.user = self.owner
        self.assertFalse(
            self.permission_checker.has_approve_permission(
                request, self.review_collection
            )
        )

        # Regular user should not be able to approve any object
        request.user = self.regular_user
        self.assertFalse(
            self.permission_checker.has_approve_permission(
                request, self.review_collection
            )
        )

        # No one should be able to approve a private object
        request.user = self.moderator
        self.assertFalse(
            self.permission_checker.has_approve_permission(
                request, self.private_collection
            )
        )

    def test_reject_permission(self):
        """Test permission to reject an object."""
        # Moderator should be able to reject an object in review
        request = self.factory.post("/")
        request.user = self.moderator
        self.assertTrue(
            self.permission_checker.has_reject_permission(
                request, self.review_collection
            )
        )

        # Owner should not be able to reject their own object
        request.user = self.owner
        self.assertFalse(
            self.permission_checker.has_reject_permission(
                request, self.review_collection
            )
        )

        # Regular user should not be able to reject any object
        request.user = self.regular_user
        self.assertFalse(
            self.permission_checker.has_reject_permission(
                request, self.review_collection
            )
        )

        # No one should be able to reject a private object
        request.user = self.moderator
        self.assertFalse(
            self.permission_checker.has_reject_permission(
                request, self.private_collection
            )
        )


class GlobalObjectPermissionTestCase(TestCase):
    def setUp(self):
        self.permission = GlobalObjectPermission()
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
        """Tests that list action is allowed for any user."""
        request = self.create_request(user=self.anonymous_user)
        view = self.create_view(action="list")
        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_retrieve_action_any_user(self):
        """Tests that retrieve action is allowed for any user."""
        request = self.create_request(user=self.anonymous_user)
        view = self.create_view(action="retrieve")
        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_create_action_authenticated_user_with_model_perm(self):
        """Tests that create action is allowed for authenticated users with model permission."""
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
        view.queryset = queryset_mock
        view.get_queryset = Mock(return_value=queryset_mock)

        # Test - should allow create with model permission
        self.assertTrue(self.permission.has_permission(request, view))

        # Verify the permission was checked correctly
        user_with_perm.has_perm.assert_called_with("testapp.add_testmodel")

    def test_has_permission_create_action_staff_user(self):
        """Tests that create action is allowed for staff users."""
        # Staff users should be able to create objects without explicit permission
        request = self.create_request(user=self.staff_user)

        # Setup a view with queryset that has a model
        view = self.create_view(action="create")
        model_mock = Mock()
        model_mock._meta.app_label = "testapp"
        model_mock._meta.model_name = "testmodel"
        queryset_mock = Mock()
        queryset_mock.model = model_mock
        view.queryset = queryset_mock
        view.get_queryset = Mock(return_value=queryset_mock)

        # Test - staff should always be allowed
        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_update_action_authenticated_user(self):
        """Tests that update action is allowed for authenticated users."""
        request = self.create_request(user=self.owner_user)
        view = self.create_view(action="update")
        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_update_action_unauthenticated_user(self):
        """Tests that update action is denied for unauthenticated users."""
        request = self.create_request(user=self.anonymous_user)
        view = self.create_view(action="update")
        self.assertFalse(self.permission.has_permission(request, view))

    def test_has_object_permission_safe_published_any_user(self):
        """Tests that any user can read published objects."""
        request = self.create_request(method="GET", user=self.other_user)
        view = Mock()
        obj = self.public_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_review_owner(self):
        """Tests that owners can read review objects."""
        request = self.create_request(method="GET", user=self.owner_user)
        view = Mock()
        obj = self.review_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_review_moderator(self):
        """Tests modarators can read review objects."""
        request = self.create_request(method="GET", user=self.moderator_user)
        view = Mock()
        obj = self.review_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_review_other_user(self):
        """Tests that other users cannot read review objects."""
        request = self.create_request(method="GET", user=self.other_user)
        view = Mock()
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=False)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_private_owner(self):
        """Tests that owners can read their own private objects."""
        request = self.create_request(method="GET", user=self.owner_user)
        view = Mock()
        obj = self.private_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_private_other_user(self):
        """Tests that other users cannot read private objects."""
        request = self.create_request(method="GET", user=self.other_user)
        view = Mock()
        obj = self.private_obj
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_undefined_status(self):
        """Tests that undefined status objects are not accessible."""
        request = self.create_request(method="GET", user=self.owner_user)
        view = Mock()
        obj = self.undefined_status_obj
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_moderator_can_publish_review_object(self):
        """Tests that moderators can change objects under review to published."""
        request = self.create_request(
            method="PUT",
            user=self.moderator_user,
            data={"publication_status": "published"},
        )
        view = Mock()
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=True)
        self.assertTrue(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.moderator_user, obj)

    def test_owner_cannot_publish_review_object(self):
        """Tests that owners cannot change objects under review to published."""
        request = self.create_request(
            method="PUT", user=self.owner_user, data={"publication_status": "published"}
        )
        view = Mock()
        obj = self.private_obj
        self.permission._is_moderator = Mock(return_value=False)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.owner_user, obj)

    def test_owner_cannot_modify_already_published_objects(self):
        """Tests that owners cannot modify already published objects."""
        request = self.create_request(
            method="PATCH", user=self.owner_user, data={"title": "New Title"}
        )
        view = Mock()
        obj = self.public_obj
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_moderator_cannot_modify_other_fields_of_non_private_object(self):
        """Tests that moderators cannot change fields other than publicatcion_status."""
        request = self.create_request(
            method="PUT", user=self.moderator_user, data={"title": "Updated Title"}
        )
        view = Mock()
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=True)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.moderator_user, obj)

    def test_moderator_cannot_modify_private_object(self):
        """Tests that moderators cannot modify private objects of other users."""
        request = self.create_request(
            method="PUT",
            user=self.moderator_user,
            data={"publication_status": "published"},
        )
        view = Mock()
        obj = self.private_obj
        self.permission._is_moderator = Mock(return_value=True)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.moderator_user, obj)

    def test_moderator_can_modify_private_object_as_owner(self):
        """Tests that moderators can modify private objects of their own."""
        request = self.create_request(
            method="PUT", user=self.owner_user, data={"title": "Updated Title"}
        )
        view = Mock()
        obj = self.private_obj
        self.permission._is_moderator = Mock(return_value=True)
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_moderator_cannot_publish_private_object_as_owner(self):
        """Tests that moderators cannot publish their own private objects."""
        request = self.create_request(
            method="PUT", user=self.owner_user, data={"publication_status": "published"}
        )
        view = Mock()
        obj = self.private_obj
        self.permission._is_moderator = Mock(return_value=True)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_other_user_has_no_write_permissions(self):
        """Tests that other users have no write permissions."""
        request = self.create_request(method="DELETE", user=self.other_user, data={})
        view = Mock()
        obj = self.private_obj
        self.permission._is_moderator = Mock(return_value=False)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.other_user, obj)

    def test_check_safe_permissions_published(self):
        """Tests that other users can view published objects."""
        request = self.create_request(method="GET", user=self.other_user)
        obj = self.public_obj
        result = self.permission._check_safe_permissions(request, obj)
        self.assertTrue(result)

    def test_check_safe_permissions_review_owner(self):
        """Tests that owners can view their own objects under review."""
        request = self.create_request(method="GET", user=self.owner_user)
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=False)
        result = self.permission._check_safe_permissions(request, obj)
        self.assertTrue(result)

    def test_check_safe_permissions_review_moderator(self):
        """Tests that moderators can view objects under review."""
        request = self.create_request(method="GET", user=self.moderator_user)
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=True)
        result = self.permission._check_safe_permissions(request, obj)
        self.assertTrue(result)
        self.permission._is_moderator.assert_called_with(self.moderator_user, obj)

    def test_check_safe_permissions_review_other_user(self):
        """Tests that other users cannot view objects under review."""
        request = self.create_request(method="GET", user=self.other_user)
        obj = self.review_obj
        self.permission._is_moderator = Mock(return_value=False)
        result = self.permission._check_safe_permissions(request, obj)
        self.assertFalse(result)
        self.permission._is_moderator.assert_called_with(self.other_user, obj)

    def test_check_safe_permissions_private_owner(self):
        """Tests that owners can view their own private objects."""
        request = self.create_request(method="GET", user=self.owner_user)
        obj = self.private_obj
        result = self.permission._check_safe_permissions(request, obj)
        self.assertTrue(result)

    def test_check_safe_permissions_private_other_user(self):
        """Tests that other users cannot view private objects."""
        request = self.create_request(method="GET", user=self.other_user)
        obj = self.private_obj
        result = self.permission._check_safe_permissions(request, obj)
        self.assertFalse(result)

    def test_check_safe_permissions_undefined_status(self):
        """Tests that other users cannot view objects with undefined publication status."""
        request = self.create_request(method="GET", user=self.owner_user)
        obj = self.undefined_status_obj
        result = self.permission._check_safe_permissions(request, obj)
        self.assertFalse(result)

    def test_is_moderator_with_permission(self):
        """Tests that moderators have permission to moderate objects."""
        mock_user_instance = self.moderator_user
        mock_user_instance.has_perm.return_value = True
        obj = self.public_obj
        result = self.permission._is_moderator(mock_user_instance, obj)
        self.assertTrue(result)
        mock_user_instance.has_perm.assert_called_with("utils.can_moderate_samplemodel")

    def test_is_moderator_with_staff(self):
        """Tests that staff users are moderators."""
        mock_user_instance = self.staff_user
        obj = self.public_obj
        result = self.permission._is_moderator(mock_user_instance, obj)
        self.assertTrue(result)
        mock_user_instance.has_perm.assert_not_called()

    def test_is_moderator_without_permission_or_staff(self):
        """Tests that other users are not moderators."""
        mock_user_instance = self.other_user
        obj = self.public_obj
        result = self.permission._is_moderator(mock_user_instance, obj)
        self.assertFalse(result)
        mock_user_instance.has_perm.assert_called_with("utils.can_moderate_samplemodel")

    def test_is_moderator_with_permission_false_staff_false(self):
        """Tests that moderators can have limited permissions."""
        mock_user_instance = self.moderator_user
        mock_user_instance.has_perm.return_value = False
        mock_user_instance.is_staff = False
        obj = self.public_obj
        result = self.permission._is_moderator(mock_user_instance, obj)
        self.assertFalse(result)
        mock_user_instance.has_perm.assert_called_with("utils.can_moderate_samplemodel")

    def test_has_object_permission_no_publication_status(self):
        """Tests that objects with undefined publication status are not accessible."""
        request = self.create_request(method="GET", user=self.owner_user)
        view = Mock()
        obj = self.undefined_status_obj
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_safe_method_no_publication_status(self):
        """Tests that objects with undefined publication status are not accessible."""
        request = self.create_request(method="HEAD", user=self.owner_user)
        view = Mock()
        obj = self.undefined_status_obj
        self.assertFalse(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_write_method_no_data(self):
        """Tests that write methods are allowed for objects with no data."""
        request = self.create_request(method="PUT", user=self.owner_user, data={})
        view = Mock()
        obj = self.private_obj
        self.assertTrue(self.permission.has_object_permission(request, view, obj))

    def test_has_object_permission_write_method_not_owner_not_moderator(self):
        """Tests that write methods are not allowed for objects that are not owned by the user or moderated by the user."""
        request = self.create_request(
            method="PATCH", user=self.other_user, data={"title": "Hack"}
        )
        view = Mock()
        obj = self.public_obj
        self.permission._is_moderator = Mock(return_value=False)
        self.assertFalse(self.permission.has_object_permission(request, view, obj))
        self.permission._is_moderator.assert_called_with(self.other_user, obj)
