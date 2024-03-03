from rest_framework import routers

from .viewsets import PropertyViewSet, UnitViewSet

router = routers.DefaultRouter()
router.register('unit', UnitViewSet, basename='api-unit')
router.register('property', PropertyViewSet, basename='api-property')
