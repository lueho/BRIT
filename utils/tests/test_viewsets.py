from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase, modify_settings
from rest_framework import serializers, status
from rest_framework.test import APIRequestFactory

from .models import TestGlobalObject
from ..viewsets import AutoPermModelViewSet, GlobalObjectViewSet


class MockSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestGlobalObject
        fields = ['id', 'name', 'description']


@modify_settings(MIDDLEWARE={'remove': 'ambient_toolbox.middleware.current_user.CurrentUserMiddleware'})
class GlobalObjectViewSetTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        self.staff_user = User.objects.create_user(
            username='staffuser',
            password='staffpassword',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regularuser',
            password='regularpassword',
            is_staff=False
        )

        self.example_object = TestGlobalObject.objects.create(
            name='Test Object',
            description='A test global object.'
        )

    def get_mock_viewset(self, method, user=None, data=None, pk=None):
        """
        Create and return a mock viewset action.
        """
        if method.lower() == 'get':
            request = self.factory.get('/fake-url/')
        elif method.lower() == 'post':
            request = self.factory.post('/fake-url/', data=data)
        elif method.lower() == 'put':
            request = self.factory.put('/fake-url/', data=data)
        elif method.lower() == 'patch':
            request = self.factory.patch('/fake-url/', data=data)
        elif method.lower() == 'delete':
            request = self.factory.delete('/fake-url/')
        else:
            raise ValueError("Unsupported method")

        if user:
            request.user = user
        else:
            request.user = AnonymousUser()

        with patch.object(GlobalObjectViewSet, 'get_queryset', return_value=TestGlobalObject.objects.all()):
            with patch.object(GlobalObjectViewSet, 'get_serializer_class', return_value=MockSerializer):
                view = GlobalObjectViewSet.as_view({
                    'get': 'list',
                    'post': 'create',
                    'put': 'update',
                    'patch': 'partial_update',
                    'delete': 'destroy'
                })

                response = view(request, pk=pk) if pk else view(request)

                return response

    def test_read_access_unauthenticated_user(self):
        """
        Unauthenticated users should be able to perform read operations.
        """
        response = self.get_mock_viewset('get')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.get_mock_viewset('get', pk=self.example_object.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_write_access_unauthenticated_user(self):
        """
        Unauthenticated users should NOT be able to perform write operations.
        """
        response = self.get_mock_viewset('post', data={'name': 'New Object', 'description': 'New description.'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.get_mock_viewset(
            'put',
            user=AnonymousUser(),
            data={'name': 'Updated Name', 'description': 'Updated description.'},
            pk=self.example_object.id
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.get_mock_viewset(
            'patch',
            user=AnonymousUser(),
            data={'description': 'Partially updated description.'},
            pk=self.example_object.id
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.get_mock_viewset('delete', user=AnonymousUser(), pk=self.example_object.id)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_write_access_authenticated_regular_user(self):
        """
        Authenticated non-staff users should NOT be able to perform write operations.
        """
        response = self.get_mock_viewset(
            'post',
            user=self.regular_user,
            data={'name': 'New Object', 'description': 'New description.'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.get_mock_viewset(
            'put',
            user=self.regular_user,
            data={'name': 'Updated Name', 'description': 'Updated description.'},
            pk=self.example_object.id
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.get_mock_viewset(
            'patch',
            user=self.regular_user,
            data={'description': 'Partially updated description.'},
            pk=self.example_object.id
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.get_mock_viewset('delete', user=self.regular_user, pk=self.example_object.id)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_write_access_authenticated_staff_user(self):
        """
        Authenticated staff users should be able to perform write operations.
        """
        response = self.get_mock_viewset(
            'post',
            user=self.staff_user,
            data={'name': 'Staff Created Object', 'description': 'Created by staff.'}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TestGlobalObject.objects.count(), 2)
        self.assertEqual(TestGlobalObject.objects.get(id=response.data['id']).name, 'Staff Created Object')

        response = self.get_mock_viewset(
            'put',
            user=self.staff_user,
            data={'name': 'Updated by Staff', 'description': 'Updated by staff.'},
            pk=self.example_object.id
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.example_object.refresh_from_db()
        self.assertEqual(self.example_object.name, 'Updated by Staff')
        self.assertEqual(self.example_object.description, 'Updated by staff.')

        response = self.get_mock_viewset(
            'patch',
            user=self.staff_user,
            data={'description': 'Partially updated by staff.'},
            pk=self.example_object.id
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.example_object.refresh_from_db()
        self.assertEqual(self.example_object.description, 'Partially updated by staff.')

        response = self.get_mock_viewset(
            'delete',
            user=self.staff_user,
            pk=self.example_object.id
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(TestGlobalObject.objects.count(), 1)

    def test_create_object_with_duplicate_name_staff_user(self):
        """
        Attempting to create an object with a duplicate name should fail.
        Only staff users can perform write operations.
        """
        response = self.get_mock_viewset(
            'post',
            user=self.staff_user,
            data={'name': 'Unique Object', 'description': 'Unique description.'}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.get_mock_viewset(
            'post',
            user=self.staff_user,
            data={'name': 'Unique Object', 'description': 'Duplicate name.'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, "Duplicate names should fail.")
        self.assertIn('name', response.data, "Response should contain 'name' field error.")

    def test_delete_nonexistent_object_staff_user(self):
        """
        Attempting to delete a nonexistent object should return 404.
        """
        nonexistent_pk = 9999
        response = self.get_mock_viewset('delete', user=self.staff_user, pk=nonexistent_pk)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, "Nonexistent object should return 404.")


class AutoPermModelViewSetTestCase(TestCase):

    def setUp(self):
        self.viewset = AutoPermModelViewSet()
        self.viewset.queryset = MagicMock()
        self.model_cls = MagicMock()
        self.model_cls._meta.model_name = 'testmodel'
        self.model_cls._meta.app_label = 'testapp'
        self.viewset.get_queryset = MagicMock(return_value=MagicMock(model=self.model_cls))

    def test_generate_permission_required(self):
        expected_permissions = {
            'create': 'testapp.add_testmodel',
            'list': 'testapp.view_testmodel',
            'retrieve': 'testapp.view_testmodel',
            'update': 'testapp.change_testmodel',
            'partial_update': 'testapp.change_testmodel',
            'destroy': 'testapp.delete_testmodel',
        }
        autogenerated_permissions = self.viewset._generate_permission_required()
        self.assertEqual(autogenerated_permissions, expected_permissions)

    def test_custom_override_autogenerated_permissions(self):
        self.viewset.custom_permission_required = {'list': 'custom.list_permission'}
        expected_permissions = {
            'create': 'testapp.add_testmodel',
            'list': 'custom.list_permission',
            'retrieve': 'testapp.view_testmodel',
            'update': 'testapp.change_testmodel',
            'partial_update': 'testapp.change_testmodel',
            'destroy': 'testapp.delete_testmodel',
        }
        actual_permissions = self.viewset.permission_required
        self.assertEqual(actual_permissions, expected_permissions)

    def test_permission_required_generated_once(self):
        """Ensure permission_required property generates permissions only once."""
        with patch.object(self.viewset, '_generate_permission_required',
                          wraps=self.viewset._generate_permission_required) as mocked_method:
            _ = self.viewset.permission_required
            _ = self.viewset.permission_required
            mocked_method.assert_called_once()

    def test_get_permissions_triggers_permission_generation(self):
        self.assertFalse(self.viewset._permission_required_generated)
        self.viewset.get_permissions()
        self.assertTrue(self.viewset._permission_required_generated)
