from django.urls import path

from .views import (
    ProcessMockDashboard,
    ProcessMockMaterialDetail,
    ProcessOverviewMock,
    ProcessRunMock,
    ProcessTypeDetailMock,
    ProcessTypeListMock,
    StrawAndWoodProcessInfoView,
)

app_name = "processes"
urlpatterns = [
    path("mock/", ProcessMockDashboard.as_view(), name="dashboard"),
    path("mock/overview/", ProcessOverviewMock.as_view(), name="mock_process_overview"),
    path("types/", ProcessTypeListMock.as_view(), name="type_list"),
    path("types/<int:pk>/", ProcessTypeDetailMock.as_view(), name="type_detail"),
    path("types/<int:pk>/run/", ProcessRunMock.as_view(), name="run"),
    path(
        "materials/<int:pk>/",
        ProcessMockMaterialDetail.as_view(),
        name="mock_material_detail",
    ),
    path(
        "infocards/pulping_straw/",
        StrawAndWoodProcessInfoView.as_view(),
        name="pulping_straw_info",
    ),
]
