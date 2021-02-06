from django.urls import path

from .views import (MaterialComponentGroupAddComponentView,
                    MaterialAddComponentGroupView,
                    MaterialListView,
                    MaterialCreateView,
                    MaterialDetailView,
                    MaterialUpdateView,
                    MaterialDeleteView,
                    MaterialSettingsListView,
                    MaterialSettingsDetailView,
                    MaterialSettingsDeleteView,
                    MaterialComponentListView,
                    MaterialComponentCreateView,
                    MaterialComponentDetailView,
                    MaterialComponentUpdateView,
                    MaterialComponentDeleteView,
                    MaterialComponentGroupListView,
                    MaterialComponentGroupCreateView,
                    MaterialComponentGroupDetailView,
                    MaterialComponentGroupUpdateView,
                    MaterialComponentGroupDeleteView,
                    MaterialComponentShareUpdateView,
                    MaterialRemoveComponentGroupView,
                    MaterialComponentGroupRemoveComponentView,
                    MaterialComponentGroupAddTemporalDistributionView,
                    MaterialComponentGroupShareDistributionUpdateView,
                    )

urlpatterns = [
    path('materials/', MaterialListView.as_view(), name='material_list'),
    path('materials/create/', MaterialCreateView.as_view(), name='material_create'),
    path('materials/<int:pk>/', MaterialDetailView.as_view(), name='material_detail'),
    path('materials/<int:pk>/update/', MaterialUpdateView.as_view(), name='material_update'),
    path('materials/<int:pk>/delete/', MaterialDeleteView.as_view(), name='material_delete'),
    path('materials/settings/', MaterialSettingsListView.as_view(), name='material_settings_list'),
    path('materials/settings/<int:pk>/', MaterialSettingsDetailView.as_view(), name='material_settings'),
    path('materials/settings/<int:pk>/add_component_group/', MaterialAddComponentGroupView.as_view(),
         name='material_add_component_group'),
    path('materials/settings/<int:pk>/delete/', MaterialSettingsDeleteView.as_view(), name='material_settings_delete'),
    path('materialcomponents/', MaterialComponentListView.as_view(), name='material_component_list'),
    path('materialcomponents/create/', MaterialComponentCreateView.as_view(), name='material_component_create'),
    path('materialcomponents/<int:pk>/', MaterialComponentDetailView.as_view(), name='material_component_detail'),
    path('materialcomponents/<int:pk>/update/', MaterialComponentUpdateView.as_view(),
         name='material_component_update'),
    path('materialcomponents/<int:pk>/delete/', MaterialComponentDeleteView.as_view(),
         name='material_component_delete'),
    path('materialcomponentgroups/', MaterialComponentGroupListView.as_view(), name='material_component_group_list'),
    path('materialcomponentgroups/create/', MaterialComponentGroupCreateView.as_view(),
         name='material_component_group_create'),
    path('materialcomponentgroups/<int:pk>/', MaterialComponentGroupDetailView.as_view(),
         name='material_component_group_detail'),
    path('materialcomponentgroups/<int:pk>/update/', MaterialComponentGroupUpdateView.as_view(),
         name='material_component_group_update'),
    path('materialcomponentgroups/<int:pk>/delete/', MaterialComponentGroupDeleteView.as_view(),
         name='material_component_group_delete'),
    path('materialcomponentgroups/settings/<int:pk>/add_component/', MaterialComponentGroupAddComponentView.as_view(),
         name='material_component_group_add_component'),
    path('materialcomponentgroups/settings/<int:pk>/remove_component/<int:component_pk>/',
         MaterialComponentGroupRemoveComponentView.as_view(), name='material_component_group_remove_component'),
    path('materialcomponentgroups/settings/<int:pk>/remove/', MaterialRemoveComponentGroupView.as_view(),
         name='material_component_group_remove'),
    path('materialcomponentgroups/settings/<int:pk>/add_temporal_distribution/',
         MaterialComponentGroupAddTemporalDistributionView.as_view(),
         name='material_component_group_add_temporal_distribution'),
    path('materialcomponentgroupshares/<int:pk>/update/', MaterialComponentShareUpdateView.as_view(),
         name='material_component_group_share_update'),
    path('material_component_groups/settings/<int:pk>/shares/<int:timestep_pk>/update/',
         MaterialComponentGroupShareDistributionUpdateView.as_view(),
         name='material_component_group_share_distribution_update'),
]
