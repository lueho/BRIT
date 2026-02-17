from django.urls import path

from .views import (
    ProcessDashboard,
    ProcessMaterialDetail,
    ProcessOverview,
    ProcessRun,
    ProcessTypeDetail,
    ProcessTypeList,
    StrawAndWoodProcessInfoView,
)

app_name = "processes"
urlpatterns = [
    path("dashboard/", ProcessDashboard.as_view(), name="dashboard"),
    path("dashboard/", ProcessDashboard.as_view(), name="processes-dashboard"),
    path("explorer/", ProcessTypeList.as_view(), name="processes-explorer"),
    path("types/", ProcessTypeList.as_view(), name="type_list"),
    path("types/", ProcessTypeList.as_view(), name="processtype-list"),
    path("types/<int:pk>/", ProcessTypeDetail.as_view(), name="type_detail"),
    path("types/<int:pk>/", ProcessTypeDetail.as_view(), name="processtype-detail"),
    path(
        "types/<int:pk>/overview/",
        ProcessOverview.as_view(),
        name="process_overview",
    ),
    path("types/<int:pk>/run/", ProcessRun.as_view(), name="run"),
    path(
        "materials/<int:pk>/",
        ProcessMaterialDetail.as_view(),
        name="mock_material_detail",
    ),
    path(
        "infocards/pulping_straw/",
        StrawAndWoodProcessInfoView.as_view(),
        name="pulping_straw_info",
    ),
]
