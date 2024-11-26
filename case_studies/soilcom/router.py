from rest_framework import routers

from .viewsets import CollectionViewSet

router = routers.DefaultRouter()
router.register('collection', CollectionViewSet, basename='api-waste-collection')
