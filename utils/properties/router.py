from rest_framework import routers

from .viewsets import PropertyUnitViewSet, PropertyViewSet

router = routers.DefaultRouter()
router.register('unit', PropertyUnitViewSet, basename='api-propertyunit')
router.register('property', PropertyViewSet, basename='api-property')
