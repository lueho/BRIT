from rest_framework import routers

from sources.roadside_trees.viewsets import HamburgRoadsideTreeViewSet

router = routers.DefaultRouter()
router.register(
    "hamburg_roadside_trees",
    HamburgRoadsideTreeViewSet,
    basename="api-hamburg-roadside-trees",
)

__all__ = ["router"]
