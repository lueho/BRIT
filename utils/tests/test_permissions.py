from unittest.mock import MagicMock, Mock

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from ..permissions import HasModelPermission, IsStaffOrReadOnly


class IsStaffOrReadOnlyPermissionTestCase(TestCase):
    def setUp(self):
        self.permission = IsStaffOrReadOnly()
        self.factory = APIRequestFactory()

        self.staff_user = User.objects.create_user(
            username='staffuser',
            password='password123',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regularuser',
            password='password123',
            is_staff=False
        )

    def make_request(self, method, user=None, data=None):
        """
        Helper method to create a DRF Request object with the specified method and user.
        """
        method_lower = method.lower()
        if method_lower == 'get':
            request = self.factory.get('/fake-url/', data=data, format='json')
        elif method_lower == 'post':
            request = self.factory.post('/fake-url/', data=data, format='json')
        elif method_lower == 'put':
            request = self.factory.put('/fake-url/', data=data, format='json')
        elif method_lower == 'patch':
            request = self.factory.patch('/fake-url/', data=data, format='json')
        elif method_lower == 'delete':
            request = self.factory.delete('/fake-url/')
        elif method_lower == 'head':
            request = self.factory.head('/fake-url/')
        elif method_lower == 'options':
            request = self.factory.options('/fake-url/')
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
        safe_methods = ['GET', 'HEAD', 'OPTIONS']
        for method in safe_methods:
            with self.subTest(method=method):
                request = self.make_request(method)
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertTrue(
                    has_perm,
                    f"Safe method {method} should be allowed for any user."
                )

    def test_write_methods_denied_for_unauthenticated_users(self):
        """
        Ensure that write methods are denied for unauthenticated users.
        """
        write_methods = ['POST', 'PUT', 'PATCH', 'DELETE']
        for method in write_methods:
            with self.subTest(method=method):
                request = self.make_request(method, data={'name': 'Test'})
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertFalse(
                    has_perm,
                    f"Write method {method} should be denied for unauthenticated users."
                )

    def test_write_methods_denied_for_authenticated_non_staff_users(self):
        """
        Ensure that write methods are denied for authenticated non-staff users.
        """
        write_methods = ['POST', 'PUT', 'PATCH', 'DELETE']
        for method in write_methods:
            with self.subTest(method=method):
                request = self.make_request(method, user=self.regular_user, data={'name': 'Test'})
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertFalse(
                    has_perm,
                    f"Write method {method} should be denied for non-staff users."
                )

    def test_write_methods_allowed_for_staff_users(self):
        """
        Ensure that write methods are allowed for authenticated staff users.
        """
        write_methods = ['POST', 'PUT', 'PATCH', 'DELETE']
        self.assertTrue(self.staff_user.is_staff)
        for method in write_methods:
            with self.subTest(method=method):
                request = self.make_request(method, user=self.staff_user, data={'name': 'Test'})
                view = Mock()
                has_perm = self.permission.has_permission(request, view)
                self.assertTrue(
                    has_perm,
                    f"Write method {method} should be allowed for staff users."
                )


class HasModelPermissionTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.permission = HasModelPermission()
        self.user = MagicMock(spec=User)
        self.view = MagicMock(spec=APIView)
        self.view.action = 'test_action'
        self.view.permission_required = {'test_action': ['app.view_model', 'app.change_model']}

    def test_has_permission_returns_True_for_not_authenticated(self):
        request = self.factory.get('/any-url')
        self.user.is_authenticated = False
        request.user = self.user
        # This should return True because for the non-authenticated users, the permission_check should be skipped to
        # progress to the authentication check, which will raise HTTP_401_UNAUTHORIZED
        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_has_permission_raises_improperly_configured_when_missing_permission_required_attribute(self):
        view = MagicMock(spec=APIView)
        request = self.factory.get('/any-url')
        request.user = self.user
        view.request = request
        with self.assertRaises(ImproperlyConfigured):
            self.permission.has_permission(request, view)

    def test_action_not_in_permission_required(self):
        request = self.factory.get('/any-url')
        request.user = self.user
        self.view.permission_required = {'other_action': 'app.view_model'}
        with self.assertRaises(ImproperlyConfigured):
            self.permission.has_permission(request, self.view)

    def test_no_specific_permission_required(self):
        request = self.factory.get('/any-url')
        request.user = self.user
        self.view.permission_required = {'test_action': None}
        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_permission_required_user_does_not_have_it(self):
        request = self.factory.get('/any-url')
        request.user = self.user
        self.view.permission_required = {'test_action': 'app.view_model'}
        self.view.action = 'test_action'
        request.user.has_perm = MagicMock(return_value=False)
        self.assertFalse(self.permission.has_permission(request, self.view))

    def test_permission_required_user_has_it(self):
        request = self.factory.get('/any-url')
        request.user = self.user
        self.view.permission_required = {'test_action': 'app.view_model'}
        self.view.action = 'test_action'
        request.user.has_perm = MagicMock(return_value=True)
        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_multiple_permissions_required_user_has_all(self):
        request = self.factory.get('/any-url')
        request.user = self.user
        request.user.has_perm = MagicMock(side_effect=lambda perm: perm in ['app.view_model', 'app.change_model'])
        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_multiple_permissions_required_user_lacks_one(self):
        request = self.factory.get('/any-url')
        request.user = self.user
        request.user.has_perm = MagicMock(side_effect=lambda perm: perm == 'app.view_model')
        self.assertFalse(self.permission.has_permission(request, self.view))

    def test_action_without_permission_entry(self):
        request = self.factory.get('/any-url')
        request.user = self.user
        self.user.is_authenticated = True
        self.view.action = 'unlisted_action'
        with self.assertRaises(ImproperlyConfigured):
            self.permission.has_permission(request, self.view)

    def test_incorrect_permission_required_type(self):
        request = self.factory.get('/any-url')
        request.user = self.user
        self.user.is_authenticated = True
        self.view.permission_required = ['app.view_model']
        with self.assertRaises(ImproperlyConfigured):
            self.permission.has_permission(request, self.view)

    def test_options_method_is_always_allowed(self):
        request = self.factory.options('/any-url')
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
        request = self.factory.head('/any-url')
        request.user = self.user

        request.user.is_authenticated = False
        self.assertTrue(self.permission.has_permission(request, self.view))

        request.user.is_authenticated = True
        request.user.has_perm = MagicMock(return_value=True)
        self.assertTrue(self.permission.has_permission(request, self.view))

        request.user.is_authenticated = True
        request.user.has_perm = MagicMock(return_value=False)
        self.assertTrue(self.permission.has_permission(request, self.view))
