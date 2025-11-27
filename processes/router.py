"""DRF router configuration for the processes module API."""

from rest_framework import routers

from .viewsets import ProcessCategoryViewSet, ProcessViewSet

router = routers.DefaultRouter()
router.register(r"processes", ProcessViewSet, basename="api-process")
router.register(r"categories", ProcessCategoryViewSet, basename="api-processcategory")
