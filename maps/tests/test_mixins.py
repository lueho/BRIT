from unittest.mock import Mock

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.viewsets import ModelViewSet

from maps.mixins import GeoJSONMixin


class DummySerializer(serializers.Serializer):
    """Dummy serializer for testing GeoJSONMixin."""
    
    def to_representation(self, instance):
        return {"type": "Feature", "properties": {}, "geometry": None}
        
    @property
    def data(self):
        # Return valid GeoJSON structure
        return {
            "type": "FeatureCollection",
            "features": []
        }


class MockViewSet(GeoJSONMixin, ModelViewSet):
    """Minimal viewset used only for unit-tests."""

    queryset = Mock()
    geojson_serializer_class = DummySerializer

    def filter_queryset(self, queryset):
        # Default implementation just returns the queryset
        return queryset


class GeoJSONMixinTestCase(TestCase):
    """Unit-tests for the GeoJSONMixin behaviour."""

    @classmethod
    def setUpTestData(cls):
        # Create a user for the test case (once for all tests)
        cls.user = User.objects.create_user(username="testuser")

    def setUp(self):
        self.factory = APIRequestFactory()
        self.viewset = MockViewSet()
        self.viewset.format_kwarg = None
        
        # Add a default request to the viewset as required by get_serializer_context
        request = self.factory.get('/')
        force_authenticate(request, self.user)
        self.viewset.request = Request(request)
    
    def _make_request(self, url="/api/test/geojson/", user=None, **query_params):
        """Helper to create an API request with authentication."""
        request = self.factory.get(url, query_params)
        user = user or self.user
        force_authenticate(request, user=user)
        return Request(request)

    def test_geojson_requires_serializer_class(self):
        """Mixin should raise if no `geojson_serializer_class` is declared."""

        class IncompleteViewSet(GeoJSONMixin, ModelViewSet):
            pass

        viewset = IncompleteViewSet()
        with self.assertRaises(AssertionError):
            viewset.get_geojson_serializer_class()

    def test_get_geojson_serializer_class(self):
        """Returns whatever `geojson_serializer_class` is configured."""
        self.assertIs(
            self.viewset.get_geojson_serializer_class(),
            self.viewset.geojson_serializer_class,
        )

    def test_get_geojson_serializer(self):
        """Wrapper passes args/kwargs & injects context."""
        mock_serializer_class = Mock()
        self.viewset.get_geojson_serializer_class = Mock(
            return_value=mock_serializer_class
        )
        self.viewset.get_serializer_context = Mock(return_value={"request": None})

        data = [{"foo": "bar"}]
        self.viewset.get_geojson_serializer(data, many=True)

        self.viewset.get_geojson_serializer_class.assert_called_once()
        mock_serializer_class.assert_called_once_with(
            data, many=True, context={"request": None}
        )

    def test_geojson_uses_parent_get_queryset(self):
        """The /geojson/ action must honour get_queryset & filter_queryset."""
        request = self._make_request()
        
        # In the new design, get_queryset should return the already filtered queryset
        filtered_qs = Mock()
        
        # Set up viewset mocks
        self.viewset.get_queryset = Mock(return_value=filtered_qs)
        self.viewset.filter_queryset = Mock(return_value=filtered_qs)  # User filtering

        serializer_mock = Mock()
        serializer_mock.data = {"hello": "world"}
        self.viewset.get_geojson_serializer = Mock(return_value=serializer_mock)

        # Call the geojson endpoint
        response = self.viewset.geojson(request)

        # Verify the correct methods were called with appropriate arguments
        self.viewset.get_queryset.assert_called_once()
        # No more filter assertion - that's now handled by the parent viewset's get_queryset
        self.viewset.filter_queryset.assert_called_once_with(filtered_qs)  # Should apply viewset filters
        self.viewset.get_geojson_serializer.assert_called_once_with(filtered_qs, many=True)
        
        # Verify response data
        self.assertDictEqual(response.data, {"hello": "world"})

    def test_scope_parameter_handling(self):
        """Test handling of the scope parameter in the geojson endpoint."""
        # Test with different scope values
        test_scopes = ["published", "private", "invalid"]
        
        for scope in test_scopes:
            with self.subTest(scope=scope):
                # Create request with scope
                request = self._make_request(scope=scope)
                
                # Create mock queryset for what get_queryset should return
                # In the new design, the parent viewset's get_queryset method should
                # already handle all the scope-based filtering
                filtered_qs = Mock()
                
                # Setup mocks - get_queryset should return already filtered queryset
                self.viewset.get_queryset = Mock(return_value=filtered_qs)
                self.viewset.filter_queryset = Mock(return_value=filtered_qs)
                
                # Create a proper serializer mock that returns valid GeoJSON
                mock_serializer = Mock()
                mock_serializer.data = {
                    "type": "FeatureCollection",
                    "features": []
                }
                self.viewset.get_geojson_serializer = Mock(return_value=mock_serializer)
                
                # Call the endpoint
                response = self.viewset.geojson(request)
                
                # Verify mixin behavior is consistent
                # get_queryset is called but no longer does any filtering inside the mixin
                self.viewset.get_queryset.assert_called_once()
                
                # No filter calls anymore inside the mixin - that's now handled by the parent viewset
                
                # filter_queryset is still called for standard DRF filtering
                self.viewset.filter_queryset.assert_called_once_with(filtered_qs)
                self.viewset.get_geojson_serializer.assert_called_once_with(filtered_qs, many=True)
                self.assertIsInstance(response.data, dict)

    def test_authentication_handling(self):
        """Test handling of authenticated vs unauthenticated users."""
        # Test both authenticated and unauthenticated users
        test_users = [
            (self.user, "authenticated"),
            (AnonymousUser(), "unauthenticated")
        ]
        
        for user, auth_status in test_users:
            with self.subTest(auth_status=auth_status):
                # Create request
                request = self._make_request(user=user)
                
                # Create mock queryset - this is what get_queryset would return
                # already filtered based on authentication status
                filtered_qs = Mock()
                
                # Setup mocks - get_queryset now handles all auth-based filtering
                self.viewset.get_queryset = Mock(return_value=filtered_qs)
                self.viewset.filter_queryset = Mock(return_value=filtered_qs)
                
                # Create a proper serializer mock that returns valid GeoJSON
                mock_serializer = Mock()
                mock_serializer.data = {
                    "type": "FeatureCollection",
                    "features": []
                }
                self.viewset.get_geojson_serializer = Mock(return_value=mock_serializer)
                
                # Call the endpoint
                response = self.viewset.geojson(request)
                
                # Verify core mixin behavior - much simpler now
                self.viewset.get_queryset.assert_called_once()
                self.viewset.filter_queryset.assert_called_once_with(filtered_qs)
                self.viewset.get_geojson_serializer.assert_called_once_with(filtered_qs, many=True)
                self.assertIsInstance(response.data, dict)
                
    def test_empty_queryset_handling(self):
        """Test handling of empty queryset."""
        request = self._make_request()
        
        # Return an empty queryset directly from get_queryset
        empty_qs = Mock()
        self.viewset.get_queryset = Mock(return_value=empty_qs)
        self.viewset.filter_queryset = Mock(return_value=empty_qs)
        
        # Create a proper serializer mock that returns valid empty GeoJSON
        mock_serializer = Mock()
        mock_serializer.data = {
            "type": "FeatureCollection",
            "features": []
        }
        self.viewset.get_geojson_serializer = Mock(return_value=mock_serializer)
        
        # Call the endpoint
        response = self.viewset.geojson(request)
        
        # Should still be able to serialize an empty queryset
        self.assertIsInstance(response.data, dict)
        
    def test_serializer_error_handling(self):
        """Test handling of serializer errors."""
        request = self._make_request()
        
        # Create a queryset
        qs = Mock()
        qs.filter = Mock(return_value=qs)
        self.viewset.get_queryset = Mock(return_value=qs)
        self.viewset.filter_queryset = Mock(return_value=qs)
        
        # Create a mock that raises ValidationError when .data is accessed
        error_serializer = Mock(spec=DummySerializer)
        
        # Define a property that raises an exception when accessed
        def data_property_raiser(self):
            raise serializers.ValidationError("Test error")
            
        # Set the data property to raise an exception
        type(error_serializer).data = property(data_property_raiser)
        
        # Replace the get_geojson_serializer method
        self.viewset.get_geojson_serializer = Mock(return_value=error_serializer)
        
        # Call the endpoint - should raise the ValidationError
        with self.assertRaises(serializers.ValidationError):
            self.viewset.geojson(request)
