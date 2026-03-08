from rest_framework.routers import DefaultRouter

from case_studies.flexibi_nantes.viewsets import NantesGreenhousesViewSet

router = DefaultRouter()
router.register(
    "nantes_greenhouses",
    NantesGreenhousesViewSet,
    basename="api-nantes-greenhouses",
)

__all__ = ["router"]
