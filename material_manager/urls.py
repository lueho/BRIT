from django.urls import path

from flexibi_dst.views import ModalMessageView

from .views import (AddComponentView,
                    AddComponentGroupView,
                    AddSourceView,
                    AddSeasonalVariationView,
                    RemoveSeasonalVariationView,
                    MaterialListView,
                    MaterialCreateView,
                    MaterialDetailView,
                    MaterialUpdateView,
                    MaterialDeleteView,
                    MaterialSettingsDetailView,
                    MaterialSettingsDeleteView,
                    MaterialComponentListView,
                    MaterialComponentCreateView,
                    MaterialComponentDetailView,
                    MaterialComponentUpdateView,
                    MaterialComponentDeleteView,
                    ComponentGroupListView,
                    ComponentGroupCreateView,
                    ComponentGroupDetailView,
                    ComponentGroupUpdateView,
                    ComponentGroupDeleteView,
                    RemoveComponentGroupView,
                    RemoveComponentView,
                    CompositionSetModalUpdateView,
                    )

urlpatterns = [
    path('materials/', MaterialListView.as_view(), name='material_list'),
    # path('materials/create/', MaterialCreateView.as_view(), name='material_create'),
    path('materials/create/', ModalMessageView.as_view(
        title='Future feature',
        message='This feature will be available in the future. Please check again, soon.'
    ), name='material_create'),
    path('materials/<int:pk>/', MaterialDetailView.as_view(), name='material_detail'),
    path('materials/<int:pk>/update/', MaterialUpdateView.as_view(), name='material_update'),
    path('materials/<int:pk>/delete/', MaterialDeleteView.as_view(), name='material_delete'),
    path('materials/settings/<int:pk>/', MaterialSettingsDetailView.as_view(), name='material_settings'),
    path('materials/settings/<int:pk>/add_component_group/', AddComponentGroupView.as_view(),
         name='material_add_component_group'),
    path('materials/settings/<int:pk>/delete/', MaterialSettingsDeleteView.as_view(), name='material_settings_delete'),
    path('materialcomponents/', MaterialComponentListView.as_view(), name='component_list'),
    path('materialcomponents/create/', MaterialComponentCreateView.as_view(), name='component_create'),
    path('materialcomponents/<int:pk>/', MaterialComponentDetailView.as_view(), name='component_detail'),
    path('materialcomponents/<int:pk>/update/', MaterialComponentUpdateView.as_view(),
         name='component_update'),
    path('materialcomponents/<int:pk>/delete/', MaterialComponentDeleteView.as_view(),
         name='component_delete'),
    path('materialcomponentgroups/', ComponentGroupListView.as_view(), name='material_component_group_list'),
    path('materialcomponentgroups/create/', ComponentGroupCreateView.as_view(),
         name='material_component_group_create'),
    path('materialcomponentgroups/<int:pk>/', ComponentGroupDetailView.as_view(),
         name='material_component_group_detail'),
    path('materialcomponentgroups/<int:pk>/update/', ComponentGroupUpdateView.as_view(),
         name='material_component_group_update'),
    path('compositionsets/<int:pk>/update/', CompositionSetModalUpdateView.as_view(), name='composition_set_update'),
    path('materialcomponentgroups/<int:pk>/delete/', ComponentGroupDeleteView.as_view(),
         name='material_component_group_delete'),
    path('materialcomponentgroups/settings/<int:pk>/add_component/', AddComponentView.as_view(), name='add_component'),
    path('materialcomponentgroups/settings/<int:pk>/add_source/', AddSourceView.as_view(), name='add_source'),
    path('materialcomponentgroups/settings/<int:pk>/add_seasonal_variation/', AddSeasonalVariationView.as_view(),
         name='add_seasonal_variation'),
    path('materialcomponentgroups/settings/<int:pk>/remove_seasonal_variation/<int:distribution_pk>/',
         RemoveSeasonalVariationView.as_view(),
         name='remove_seasonal_variation'),
    path('materialcomponentgroups/settings/<int:pk>/remove_component/<int:component_pk>/',
         RemoveComponentView.as_view(), name='material_component_group_remove_component'),
    path('materialcomponentgroups/settings/<int:pk>/remove/', RemoveComponentGroupView.as_view(),
         name='material_component_group_remove'),
]
