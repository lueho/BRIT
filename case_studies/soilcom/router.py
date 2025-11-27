from rest_framework import routers

from .viewsets import CollectionViewSet, CollectorViewSet

router = routers.DefaultRouter()
router.register('collection', CollectionViewSet, basename='api-waste-collection')
router.register('collector', CollectorViewSet, basename='api-collector')
