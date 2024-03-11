from rest_framework.routers import DefaultRouter

from .viewsets import LocationViewSet, RegionViewSet

router = DefaultRouter()
router.register(r'location', LocationViewSet, basename='api-location')
router.register(r'region', RegionViewSet, basename='api-region')
