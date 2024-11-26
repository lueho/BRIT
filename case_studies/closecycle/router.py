from rest_framework import routers

from .viewsets import ShowcaseViewSet, SwedenBiogasPlantsViewSet

router = routers.DefaultRouter()
router.register('showcase', ShowcaseViewSet, basename='api-showcase')
router.register('sweden_biogas_plants', SwedenBiogasPlantsViewSet, basename='api-sweden-biogas-plants')
