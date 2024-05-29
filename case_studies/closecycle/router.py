from rest_framework import routers

from .viewsets import ShowcaseViewSet


router = routers.DefaultRouter()
router.register('showcase', ShowcaseViewSet, basename='api-showcase')
