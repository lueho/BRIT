from django.urls import path
from .views import (
    ProcessMockDashboard,
    ProcessTypeListMock,
    ProcessTypeDetailMock,
    ProcessRunMock,
    ProcessMockMaterialDetail,
)

app_name = 'processes'
urlpatterns = [
    path('mock/', ProcessMockDashboard.as_view(), name='dashboard'),
    path('types/', ProcessTypeListMock.as_view(), name='type_list'),
    path('types/<int:pk>/', ProcessTypeDetailMock.as_view(), name='type_detail'),
    path('types/<int:pk>/run/', ProcessRunMock.as_view(), name='run'),
    path('materials/<int:pk>/', ProcessMockMaterialDetail.as_view(), name='mock_material_detail'),
]
