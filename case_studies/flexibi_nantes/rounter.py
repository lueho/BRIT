from rest_framework.routers import DefaultRouter

from .viewsets import NantesGreenhousesViewSet

router = DefaultRouter()
router.register(r'nantes_greenhouses', NantesGreenhousesViewSet, basename='api-nantes-greenhouses')
