from materials.views import CompositionViewSet, MaterialViewSet, SampleViewSet, SampleSeriesViewSet
from rest_framework import routers

router = routers.DefaultRouter()
router.register('material', MaterialViewSet, basename='api-material')
router.register('composition', CompositionViewSet, basename='api-composition')
router.register('sample', SampleViewSet, basename='api-sample')
router.register('sampleseries', SampleSeriesViewSet, basename='api-sampleseries')
