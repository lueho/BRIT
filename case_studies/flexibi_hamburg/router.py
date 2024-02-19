from rest_framework import routers

from .views import HamburgRoadsideTreeViewSet

router = routers.DefaultRouter()
router.register('hamburgroadsidetree', HamburgRoadsideTreeViewSet, basename='api-hamburgroadsidetree')
