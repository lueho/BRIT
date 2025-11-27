from rest_framework.routers import DefaultRouter

from .viewsets import (
    CatchmentViewSet,
    LocationViewSet,
    NutsRegionViewSet,
    RegionViewSet,
)

router = DefaultRouter()
router.register(r"location", LocationViewSet, basename="api-location")
router.register(r"region", RegionViewSet, basename="api-region")
router.register(r"catchment", CatchmentViewSet, basename="api-catchment")
router.register(r"nuts_region", NutsRegionViewSet, basename="api-nuts-region")
