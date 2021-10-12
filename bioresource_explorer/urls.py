from django.urls import include, path

from .views import MapsListView

urlpatterns = [
    path('maps_list/', MapsListView.as_view(), name='maps_list'),
    # TODO: Can case study urls be detected and added automatically?
    path('nantes/', include('case_studies.flexibi_nantes.urls')),
    path('hamburg/', include('case_studies.flexibi_hamburg.urls')),
]
