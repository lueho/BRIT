from rest_framework import routers

from case_studies.flexibi_hamburg.viewsets import HamburgRoadsideTreeViewSet

router = routers.DefaultRouter()
router.register(
    "hamburg_roadside_trees",
    HamburgRoadsideTreeViewSet,
    basename="api-hamburg-roadside-trees",
)

__all__ = ["router"]
