from rest_framework import routers
from .views import CollectionViewSet

router = routers.DefaultRouter()
router.register('collection', CollectionViewSet, basename='api-collection')
