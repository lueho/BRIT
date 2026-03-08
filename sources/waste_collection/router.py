from rest_framework import routers

from case_studies.soilcom.viewsets import CollectionViewSet, CollectorViewSet

router = routers.DefaultRouter()
router.register('collection', CollectionViewSet, basename='api-waste-collection')
router.register('collector', CollectorViewSet, basename='api-collector')

__all__ = ["router"]
