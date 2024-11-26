from rest_framework import routers

from .viewsets import HamburgRoadsideTreeViewSet

router = routers.DefaultRouter()
router.register('hamburg_roadside_trees', HamburgRoadsideTreeViewSet, basename='api-hamburg-roadside-trees')
