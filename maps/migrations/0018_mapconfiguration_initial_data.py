# Generated by Django 5.1.1 on 2024-10-30 16:22

from django.db import migrations


def create_default_map_configs(apps, schema_editor):
    MapLayerStyle = apps.get_model('maps', 'MapLayerStyle')
    MapLayerConfiguration = apps.get_model('maps', 'MapLayerConfiguration')
    MapConfiguration = apps.get_model('maps', 'MapConfiguration')

    default_region_layer_style, _ = MapLayerStyle.objects.get_or_create(
        name='Default Region Layer Style',
        defaults={
            'fill_color': '#1ca14d',
            'fill_opacity': 0.0,
            'color': '#1ca14d',
            'opacity': 1.0,
            'weight': 3,
            'publication_status': 'published',
        }
    )

    default_catchment_layer_style, _ = MapLayerStyle.objects.get_or_create(
        name='Default Catchment Layer Style',
        defaults={
            'fill_color': '#a12c1c',
            'fill_opacity': 0.0,
            'color': '#a12c1c',
            'opacity': 1.0,
            'weight': 3,
            'publication_status': 'published',
        }
    )

    default_feature_layer_style, _ = MapLayerStyle.objects.get_or_create(
        name='Default Features Layer Style',
        defaults={
            'fill_color': '#04555E',
            'fill_opacity': 0.2,
            'color': '#04555E',
            'opacity': 1.0,
            'weight': 3,
            'radius': 3,
            'publication_status': 'published',
        }
    )

    default_region_layer, _ = MapLayerConfiguration.objects.get_or_create(
        name='Default Region Layer',
        defaults={
            'style': default_region_layer_style,
            'layer_type': 'region',
            'load_layer': True,
            'api_basename': 'api-region',
            'publication_status': 'published',
        }
    )

    default_catchment_layer, _ = MapLayerConfiguration.objects.get_or_create(
        name='Default Catchment Layer',
        defaults={
            'style': default_catchment_layer_style,
            'layer_type': 'catchment',
            'load_layer': True,
            'api_basename': 'api-catchment',
            'publication_status': 'published',
        }
    )

    default_feature_layer, _ = MapLayerConfiguration.objects.get_or_create(
        name='Default Features Layer',
        defaults={
            'style': default_feature_layer_style,
            'layer_type': 'features',
            'load_layer': True,
            'publication_status': 'published',
        }
    )

    default_map_configuration, _ = MapConfiguration.objects.get_or_create(
        name='Default Map Configuration',
        defaults={
            'publication_status': 'published',
        }
    )
    default_map_configuration.layers.set([default_region_layer, default_catchment_layer, default_feature_layer])


def remove_default_map_configs(apps, schema_editor):
    MapLayerConfiguration = apps.get_model('maps', 'MapLayerConfiguration')
    MapConfiguration = apps.get_model('maps', 'MapConfiguration')
    MapLayerConfiguration.objects.filter(name__in=['Default Region Layer', 'Default Catchment Layer', 'Default Features Layer']).delete()
    MapConfiguration.objects.filter(name__in=['Default Map Configuration', ]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('maps', '0017_remove_geodataset_resources_and_more'),
    ]

    operations = [
        migrations.RunPython(
            create_default_map_configs,
            remove_default_map_configs
        )
    ]
