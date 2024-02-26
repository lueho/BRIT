from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, RequestFactory
from rest_framework.views import APIView

from ..permissions import HasModelPermission


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
