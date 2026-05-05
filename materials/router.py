from rest_framework import routers

from materials.viewsets import (
    ComponentMeasurementViewSet,
    CompositionViewSet,
    MaterialPropertyValueViewSet,
    MaterialViewSet,
    SampleSeriesViewSet,
    SampleViewSet,
)

router = routers.DefaultRouter()
router.register("material", MaterialViewSet, basename="api-material")
router.register("composition", CompositionViewSet, basename="api-composition")
router.register("sample", SampleViewSet, basename="api-sample")
router.register("sampleseries", SampleSeriesViewSet, basename="api-sampleseries")
router.register(
    "componentmeasurement",
    ComponentMeasurementViewSet,
    basename="api-componentmeasurement",
)
router.register(
    "materialpropertyvalue",
    MaterialPropertyValueViewSet,
    basename="api-materialpropertyvalue",
)
