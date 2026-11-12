from unittest.mock import Mock

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.test import RequestFactory, TestCase
from factory.django import mute_signals
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from sources.waste_collection.models import Collection, CollectionPropertyValue
from utils.object_management.models import ReviewAction, UserCreatedObject

from ..permissions import (
    GlobalObjectPermission,
    UserCreatedObjectPermission,
    get_object_policy,
)


class ReviewWorkflowPermissionTests(TestCase):
    """Test the permissions for the review workflow."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.moderator = User.objects.create_user(username="moderator")
        cls.regular_user = User.objects.create_user(username="regular")

        # Add moderator permissions
        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator.user_permissions.add(permission)

        with mute_signals(post_save):
            # Create test collections in different states
            cls.private_collection = Collection.objects.create(
                name="Private Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

        with mute_signals(post_save):
            cls.review_collection = Collection.objects.create(
                name="Review Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

        with mute_signals(post_save):
            cls.published_collection = Collection.objects.create(
                name="Published Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

        # Create permission checker
        cls.permission_checker = UserCreatedObjectPermission()
        cls.factory = RequestFactory()

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

    def test_central_policy_allows_non_owner_with_add_permission_on_published_collection(
        self,
    ):
        cpv_content_type = ContentType.objects.get_for_model(CollectionPropertyValue)
        permission, _ = Permission.objects.get_or_create(
            codename="add_collectionpropertyvalue",
            content_type=cpv_content_type,
            defaults={"name": "Can add collection property value"},
        )
        self.regular_user.user_permissions.add(permission)

        request = self.factory.get("/")
        request.user = self.regular_user

        policy = get_object_policy(
            self.regular_user, self.published_collection, request=request
        )

        self.assertTrue(policy["can_add_property"])

    def test_central_policy_denies_non_owner_with_add_permission_on_private_collection(
        self,
    ):
        cpv_content_type = ContentType.objects.get_for_model(CollectionPropertyValue)
        permission, _ = Permission.objects.get_or_create(
            codename="add_collectionpropertyvalue",
            content_type=cpv_content_type,
            defaults={"name": "Can add collection property value"},
        )
        self.regular_user.user_permissions.add(permission)

        request = self.factory.get("/")
        request.user = self.regular_user

        policy = get_object_policy(
            self.regular_user, self.private_collection, request=request
        )

        self.assertFalse(policy["can_add_property"])


class GlobalObjectPermissionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.permission = GlobalObjectPermission()
        cls.factory = APIRequestFactory()

        cls.staff_user = User.objects.create_user(username="staffuser", is_staff=True)
        cls.regular_user = User.objects.create_user(
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

    def test_write_methods_denied_for_staff_only_users(self):
        """The staff flag alone is not an application write route."""
        write_methods = ["POST", "PUT", "PATCH", "DELETE"]
        self.assertTrue(self.staff_user.is_staff)
        for method in write_methods:
            with self.subTest(method=method):
                request = self.make_request(
                    method, user=self.staff_user, data={"name": "Test"}
                )
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertFalse(
                    has_perm,
                    f"Write method {method} should be denied for staff-only users.",
                )

    def test_write_methods_allowed_for_administrators(self):
        """Write methods are allowed for explicit administrators."""
        administer_permission, _ = Permission.objects.get_or_create(
            codename="administer_objects",
            content_type=ContentType.objects.get_for_model(ReviewAction),
            defaults={"name": "Can administer objects"},
        )
        self.staff_user.user_permissions.add(administer_permission)

        write_methods = ["POST", "PUT", "PATCH", "DELETE"]
        for method in write_methods:
            with self.subTest(method=method):
                request = self.make_request(
                    method, user=self.staff_user, data={"name": "Test"}
                )
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertTrue(
                    has_perm,
                    f"Write method {method} should be allowed for administrators.",
                )


class TestUserCreatedObjectPermission(TestCase):
    def setUp(self):
        self.owner_user = User.objects.create_user(username="owner")
        self.moderator_user = User.objects.create_user(username="moderator")
        self.staff_user = User.objects.create_user(username="staff", is_staff=True)
        self.other_user = User.objects.create_user(username="other")
        self.anonymous_user = AnonymousUser()

        collection_ct = ContentType.objects.get_for_model(Collection)
        self.moderator_user.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection", content_type=collection_ct
            )
        )
        self.owner_user.user_permissions.add(
            Permission.objects.get(
                codename="change_collection", content_type=collection_ct
            )
        )

        self.public_obj = Collection.objects.create(
            name="public",
            owner=self.owner_user,
            publication_status="published",
        )
        self.review_obj = Collection.objects.create(
            name="review", owner=self.owner_user, publication_status="review"
        )
        self.private_obj = Collection.objects.create(
            name="private", owner=self.owner_user, publication_status="private"
        )
        self.declined_obj = Collection.objects.create(
            name="declined", owner=self.owner_user, publication_status="declined"
        )
        self.undefined_status_obj = Collection.objects.create(
            name="bogus", owner=self.owner_user, publication_status="bogus"
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
        mock_view.queryset = Collection.objects.all()
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
        """Tests that create action requires the model's add permission."""
        user_with_perm = User.objects.create_user(username="creator")
        user_with_perm.user_permissions.add(
            Permission.objects.get(
                codename="add_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )

        request = self.create_request(method="POST", user=user_with_perm)
        view = self.create_view(action="create")

        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_create_action_requires_model_permission(self):
        """Tests that the staff flag alone does not grant create access."""
        request = self.create_request(method="POST", user=self.staff_user)
        view = self.create_view(action="create")

        self.assertFalse(self.permission.has_permission(request, view))

    def test_has_permission_update_action_authenticated_user(self):
        """Tests that update action is allowed for authenticated users."""
        request = self.create_request(method="PUT", user=self.owner_user)
        view = self.create_view(action="update")
        self.assertTrue(self.permission.has_permission(request, view))

    def test_has_permission_update_action_unauthenticated_user(self):
        """Tests that update action is denied for unauthenticated users."""
        request = self.create_request(method="PUT", user=self.anonymous_user)
        view = self.create_view(action="update")
        self.assertFalse(self.permission.has_permission(request, view))

    def test_has_object_permission_safe_published_any_user(self):
        """Tests that any user can read published objects."""
        request = self.create_request(method="GET", user=self.other_user)
        view = self.create_view()
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.public_obj)
        )

    def test_has_object_permission_safe_review_owner(self):
        """Tests that owners can read review objects."""
        request = self.create_request(method="GET", user=self.owner_user)
        view = self.create_view()
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.review_obj)
        )

    def test_has_object_permission_safe_review_moderator(self):
        """Tests moderators can read review objects."""
        request = self.create_request(method="GET", user=self.moderator_user)
        view = self.create_view()
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.review_obj)
        )

    def test_has_object_permission_safe_review_other_user(self):
        """Tests that other users cannot read review objects."""
        request = self.create_request(method="GET", user=self.other_user)
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.review_obj)
        )

    def test_has_object_permission_safe_private_owner(self):
        """Tests that owners can read their own private objects."""
        request = self.create_request(method="GET", user=self.owner_user)
        view = self.create_view()
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.private_obj)
        )

    def test_has_object_permission_safe_private_other_user(self):
        """Tests that other users cannot read private objects."""
        request = self.create_request(method="GET", user=self.other_user)
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.private_obj)
        )

    def test_has_object_permission_safe_declined_owner(self):
        """Tests that owners can read their own declined objects."""
        request = self.create_request(method="GET", user=self.owner_user)
        view = self.create_view()
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.declined_obj)
        )

    def test_has_object_permission_safe_declined_moderator(self):
        """Tests that moderators can read declined objects."""
        request = self.create_request(method="GET", user=self.moderator_user)
        view = self.create_view()
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.declined_obj)
        )

    def test_has_object_permission_safe_declined_other_user(self):
        """Tests that other users cannot read declined objects."""
        request = self.create_request(method="GET", user=self.other_user)
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.declined_obj)
        )

    def test_has_object_permission_safe_undefined_status(self):
        """Tests that undefined status objects are not accessible."""
        request = self.create_request(method="GET", user=self.owner_user)
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(
                request, view, self.undefined_status_obj
            )
        )

    def test_moderator_can_publish_review_object(self):
        """Tests that moderators can approve objects under review via the named action."""
        request = self.create_request(
            method="POST",
            user=self.moderator_user,
            data={},
        )
        view = self.create_view(action="approve")
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.review_obj)
        )

    def test_owner_cannot_publish_review_object(self):
        """Tests that owners cannot approve their own objects under review."""
        request = self.create_request(method="POST", user=self.owner_user, data={})
        view = self.create_view(action="approve")
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.review_obj)
        )

    def test_owner_cannot_modify_already_published_objects(self):
        """Tests that owners cannot modify already published objects."""
        request = self.create_request(
            method="PATCH", user=self.owner_user, data={"name": "New Name"}
        )
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.public_obj)
        )

    def test_moderator_cannot_modify_other_fields_of_non_private_object(self):
        """Tests that moderators cannot change content fields of objects under review."""
        request = self.create_request(
            method="PUT", user=self.moderator_user, data={"name": "Updated Name"}
        )
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.review_obj)
        )

    def test_moderator_cannot_modify_private_object(self):
        """Tests that moderators cannot modify private objects of other users."""
        request = self.create_request(
            method="PUT",
            user=self.moderator_user,
            data={"name": "Updated Name"},
        )
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.private_obj)
        )

    def test_moderator_cannot_publish_via_content_update(self):
        """Tests that lifecycle state cannot be smuggled through PUT/PATCH."""
        request = self.create_request(
            method="PUT",
            user=self.moderator_user,
            data={"publication_status": "published"},
        )
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.review_obj)
        )

    def test_moderator_can_modify_private_object_as_owner(self):
        """Tests that a moderator who owns an object can modify its private content."""
        request = self.create_request(
            method="PUT", user=self.owner_user, data={"name": "Updated Name"}
        )
        view = self.create_view()
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.private_obj)
        )

    def test_owner_cannot_publish_via_content_update(self):
        """Tests that owners cannot smuggle publication_status through PUT/PATCH."""
        request = self.create_request(
            method="PUT", user=self.owner_user, data={"publication_status": "published"}
        )
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.private_obj)
        )

    def test_other_user_has_no_write_permissions(self):
        """Tests that other users have no write permissions."""
        request = self.create_request(method="DELETE", user=self.other_user, data={})
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.private_obj)
        )

    def test_is_moderator_with_permission(self):
        """Tests that holders of can_moderate_<model> are moderators."""
        self.assertTrue(
            self.permission.is_moderator(self.moderator_user, self.public_obj)
        )

    def test_is_moderator_staff_flag_alone_insufficient(self):
        """Tests that the staff flag alone does not grant moderation rights."""
        self.assertFalse(self.permission.is_moderator(self.staff_user, self.public_obj))

    def test_is_moderator_without_permission_or_staff(self):
        """Tests that other users are not moderators."""
        self.assertFalse(self.permission.is_moderator(self.other_user, self.public_obj))

    def test_has_object_permission_no_publication_status(self):
        """Tests that objects with undefined publication status are not accessible."""
        request = self.create_request(method="GET", user=self.owner_user)
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(
                request, view, self.undefined_status_obj
            )
        )

    def test_has_object_permission_safe_method_no_publication_status(self):
        """Tests that objects with undefined publication status are not accessible."""
        request = self.create_request(method="HEAD", user=self.owner_user)
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(
                request, view, self.undefined_status_obj
            )
        )

    def test_has_object_permission_write_method_no_data(self):
        """Tests that write methods are allowed for objects with no data."""
        request = self.create_request(method="PUT", user=self.owner_user, data={})
        view = self.create_view()
        self.assertTrue(
            self.permission.has_object_permission(request, view, self.private_obj)
        )

    def test_has_object_permission_write_method_not_owner_not_moderator(self):
        """Tests that write methods are not allowed for objects that are not owned by the user or moderated by the user."""
        request = self.create_request(
            method="PATCH", user=self.other_user, data={"name": "Hack"}
        )
        view = self.create_view()
        self.assertFalse(
            self.permission.has_object_permission(request, view, self.public_obj)
        )
