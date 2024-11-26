import datetime
from unittest.mock import patch

from django.test import TestCase, modify_settings
from django.urls import NoReverseMatch

from ..models import (Attribute, MapConfiguration, MapLayerConfiguration, MapLayerStyle, NutsRegion,
                      RegionAttributeTextValue, RegionAttributeValue)
from ..serializers import MapConfigurationSerializer, NutsRegionSummarySerializer


class MapConfigurationSerializerTestCase(TestCase):
    def setUp(self):
        self.style = MapLayerStyle.objects.create(
            color='#0000FF',
            weight=2,
            opacity=0.5,
            fill_color='#0000FF',
            fill_opacity=0.3
        )
        self.layer1 = MapLayerConfiguration.objects.create(
            layer_type='catchment',
            api_basename='api-catchment',
            load_layer=True,
            feature_id='123',
            style=self.style,
        )
        self.layer2 = MapLayerConfiguration.objects.create(
            layer_type='region',
            api_basename='api-region',
            load_layer=False,
            feature_id='321',
            style=self.style,
        )
        self.layer3 = MapLayerConfiguration.objects.create(
            layer_type='features',
            api_basename='',  # To test NoReverseMatch
            load_layer=True,
            feature_id='',
            style=self.style,
        )

        # Create a MapConfiguration instance
        self.map_config = MapConfiguration.objects.create(
            adjust_bounds_to_layer=True,
            apply_filter_to_features=False,
            load_features_layer_summary=True
        )
        self.map_config.layers.set([self.layer2, self.layer1, self.layer3])

    def mock_reverse_side_effect(name, *args, **kwargs):
        if '-detail' in name:
            return f"https://example.com/api/{name.split('-')[1]}/"
        else:
            return f"https://example.com/api/{name.split('-')[1]}/" + (
                f"{name.split('-')[2]}/" if len(name.split('-')) > 2 else "")

    @patch('maps.models.reverse', side_effect=mock_reverse_side_effect)
    def test_serialization_without_override_params(self, mock_reverse):
        serializer = MapConfigurationSerializer(instance=self.map_config)
        serialized_data = serializer.data

        style = {
            'color': '#0000FF',
            'weight': 2,
            'opacity': 0.5,
            'fillColor': '#0000FF',
            'fillOpacity': 0.3,
            'dashArray': '',
            'lineCap': 'round',
            'lineJoin': 'round',
            'fillRule': 'evenodd',
            'className': '',
            'radius': 10.0,
        }

        expected_data = {
            'adjustBoundsToLayer': True,
            'applyFilterToFeatures': False,
            'loadFeaturesLayerSummary': True,
            'catchmentLayerGeometriesUrl': 'https://example.com/api/catchment/geojson/',
            'loadCatchment': True,
            'catchmentId': '123',
            'catchmentLayerStyle': style,
            'catchmentLayerDetailsUrlTemplate': 'https://example.com/api/catchment/',
            'catchmentLayerSummariesUrl': 'https://example.com/api/catchment/summaries/',
            'regionLayerGeometriesUrl': 'https://example.com/api/region/geojson/',
            'loadRegion': False,
            'regionId': '321',
            'regionLayerStyle': style,
            'regionLayerDetailsUrlTemplate': 'https://example.com/api/region/',
            'regionLayerSummariesUrl': 'https://example.com/api/region/summaries/',
            'featuresLayerGeometriesUrl': '',  # api_basename is None
            'loadFeatures': False,  # Should be false if there is no api_basename for features
            'featuresId': '',
            'featuresLayerStyle': style,
            'featuresLayerDetailsUrlTemplate': '',  # api_basename is None
            'featuresLayerSummariesUrl': '',  # api_basename is None
        }

        self.assertDictEqual(serialized_data, expected_data)

    @patch('maps.models.reverse', side_effect=mock_reverse_side_effect)
    def test_serialization_with_override_params_features(self, mock_reverse):

        override_params = {
            'load_features': False,
            'features_feature_id': '1',
            'features_geometries_url': 'https://override.com/features/override/',
            'features_layer_details_url_template': 'https://override.com/features/override/',
            'features_layer_summary_url': 'https://override.com/features/override/summary/',
        }

        serializer = MapConfigurationSerializer(
            instance=self.map_config,
            context={'override_params': override_params}
        )
        serialized_data = serializer.data

        style = {
            'color': '#0000FF',
            'weight': 2,
            'opacity': 0.5,
            'fillColor': '#0000FF',
            'fillOpacity': 0.3,
            'dashArray': '',
            'lineCap': 'round',
            'lineJoin': 'round',
            'fillRule': 'evenodd',
            'className': '',
            'radius': 10.0,
        }

        expected_data = {
            'adjustBoundsToLayer': True,
            'applyFilterToFeatures': False,
            'loadFeaturesLayerSummary': True,
            'catchmentLayerGeometriesUrl': 'https://example.com/api/catchment/geojson/',
            'loadCatchment': True,
            'catchmentId': '123',
            'catchmentLayerStyle': style,
            'catchmentLayerDetailsUrlTemplate': 'https://example.com/api/catchment/',
            'catchmentLayerSummariesUrl': 'https://example.com/api/catchment/summaries/',
            'regionLayerGeometriesUrl': 'https://example.com/api/region/geojson/',
            'loadRegion': False,
            'regionId': '321',
            'regionLayerStyle': style,
            'regionLayerDetailsUrlTemplate': 'https://example.com/api/region/',
            'regionLayerSummariesUrl': 'https://example.com/api/region/summaries/',
            'featuresLayerGeometriesUrl': 'https://override.com/features/override/',
            'loadFeatures': False,  # Overridden
            'featuresId': '1',  # Overridden
            'featuresLayerStyle': style,
            'featuresLayerDetailsUrlTemplate': 'https://override.com/features/override/',  # Overridden
            'featuresLayerSummariesUrl': 'https://override.com/features/override/summary/',  # Overridden
        }

        self.assertDictEqual(serialized_data, expected_data)

    @patch('maps.models.reverse', side_effect=NoReverseMatch)
    def test_serialization_with_no_reverse_match(self, mock_reverse):
        serializer = MapConfigurationSerializer(instance=self.map_config)
        serialized_data = serializer.data

        style = {
            'color': '#0000FF',
            'weight': 2,
            'opacity': 0.5,
            'fillColor': '#0000FF',
            'fillOpacity': 0.3,
            'dashArray': '',
            'lineCap': 'round',
            'lineJoin': 'round',
            'fillRule': 'evenodd',
            'className': '',
            'radius': 10.0,
        }

        expected_data = {
            'adjustBoundsToLayer': True,
            'applyFilterToFeatures': False,
            'loadFeaturesLayerSummary': True,
            'catchmentLayerGeometriesUrl': '',
            'loadCatchment': False,
            'catchmentId': '123',
            'catchmentLayerStyle': style,
            'catchmentLayerDetailsUrlTemplate': '',
            'catchmentLayerSummariesUrl': '',
            'regionLayerGeometriesUrl': '',
            'loadRegion': False,
            'regionId': '321',
            'regionLayerStyle': style,
            'regionLayerDetailsUrlTemplate': '',
            'regionLayerSummariesUrl': '',
            'featuresLayerGeometriesUrl': '',
            'loadFeatures': False,
            'featuresId': '',
            'featuresLayerStyle': style,
            'featuresLayerDetailsUrlTemplate': '',
            'featuresLayerSummariesUrl': '',
        }

        self.assertDictEqual(serialized_data, expected_data)

    @patch('maps.models.reverse', side_effect=mock_reverse_side_effect)
    def test_serialization_with_override_params_region_and_catchment(self, mock_reverse):

        override_params = {
            'region_feature_id': '999',
            'catchment_feature_id': '888',
            'load_region': True,
            'load_catchment': False,
        }

        serializer = MapConfigurationSerializer(
            instance=self.map_config,
            context={'override_params': override_params}
        )
        serialized_data = serializer.data

        style = {
            'color': '#0000FF',
            'weight': 2,
            'opacity': 0.5,
            'fillColor': '#0000FF',
            'fillOpacity': 0.3,
            'dashArray': '',
            'lineCap': 'round',
            'lineJoin': 'round',
            'fillRule': 'evenodd',
            'className': '',
            'radius': 10.0,
        }

        expected_data = {
            'adjustBoundsToLayer': True,
            'applyFilterToFeatures': False,
            'loadFeaturesLayerSummary': True,
            'featuresLayerGeometriesUrl': '',
            'loadFeatures': False,
            'featuresId': '',
            'featuresLayerStyle': style,
            'featuresLayerDetailsUrlTemplate': '',
            'featuresLayerSummariesUrl': '',
            'regionLayerGeometriesUrl': 'https://example.com/api/region/geojson/',
            'loadRegion': True,  # Overridden
            'regionId': '999',  # Overridden
            'regionLayerStyle': style,
            'regionLayerDetailsUrlTemplate': 'https://example.com/api/region/',
            'regionLayerSummariesUrl': 'https://example.com/api/region/summaries/',
            'catchmentLayerGeometriesUrl': 'https://example.com/api/catchment/geojson/',
            'loadCatchment': False,  # Overridden
            'catchmentId': '888',  # Overridden
            'catchmentLayerStyle': style,
            'catchmentLayerDetailsUrlTemplate': 'https://example.com/api/catchment/',
            'catchmentLayerSummariesUrl': 'https://example.com/api/catchment/summaries/',
        }

        self.assertDictEqual(serialized_data, expected_data)

    @patch('maps.models.reverse', side_effect=mock_reverse_side_effect)
    def test_serialization_field_renaming(self, mock_reverse):

        serializer = MapConfigurationSerializer(instance=self.map_config)
        serialized_data = serializer.data

        # Ensure that snake_case fields are renamed to camelCase
        self.assertIn('applyFilterToFeatures', serialized_data)
        self.assertNotIn('apply_filter_to_features', serialized_data)
        self.assertIn('adjustBoundsToLayer', serialized_data)
        self.assertNotIn('adjust_bounds_to_layer', serialized_data)
        self.assertIn('loadFeaturesLayerSummary', serialized_data)
        self.assertNotIn('load_features_layer_summary', serialized_data)

    @patch('maps.models.reverse', side_effect=mock_reverse_side_effect)
    def test_serialization_load_layer_overridden(self, mock_reverse):

        override_params = {
            'load_region': True,
            'load_catchment': False,
            'load_features': False,
        }

        serializer = MapConfigurationSerializer(
            instance=self.map_config,
            context={'override_params': override_params}
        )
        serialized_data = serializer.data

        self.assertFalse(serialized_data['loadFeatures'])
        self.assertTrue(serialized_data['loadRegion'])
        self.assertFalse(serialized_data['loadCatchment'])

    @patch('maps.models.reverse', side_effect=mock_reverse_side_effect)
    def test_serialization_with_missing_fields(self, mock_reverse):
        # Create a layer with missing optional fields
        layer_missing = MapLayerConfiguration.objects.create(
            layer_type='catchment',
            api_basename='api-catchment',
            load_layer=True,
            feature_id='feature_missing',
            style=None,  # Empty style
        )
        self.map_config.layers.add(layer_missing)

        serializer = MapConfigurationSerializer(instance=self.map_config)
        serialized_data = serializer.data

        # Check that empty strings are handled correctly
        self.assertEqual(serialized_data['featuresLayerDetailsUrlTemplate'], '')
        self.assertEqual(serialized_data['featuresLayerSummariesUrl'], '')

    @patch('maps.models.reverse', side_effect=NoReverseMatch)
    def test_serialization_with_invalid_api_basename(self, mock_reverse):
        # Create a layer with invalid api_basename that causes NoReverseMatch
        layer_invalid = MapLayerConfiguration.objects.create(
            layer_type='features',
            api_basename='invalid_api',  # Assume this will cause NoReverseMatch
            load_layer=True,
            feature_id='1',
            style=self.style,
        )
        self.map_config.layers.add(layer_invalid)

        serializer = MapConfigurationSerializer(instance=self.map_config)
        serialized_data = serializer.data

        style = {
            'color': '#0000FF',
            'weight': 2,
            'opacity': 0.5,
            'fillColor': '#0000FF',
            'fillOpacity': 0.3,
            'dashArray': '',
            'lineCap': 'round',
            'lineJoin': 'round',
            'fillRule': 'evenodd',
            'className': '',
            'radius': 10.0,
        }

        self.assertIsNone(serialized_data.get('invalidUrl'))
        self.assertEqual(serialized_data.get('loadFeatures'), False)
        self.assertEqual(serialized_data.get('featuresId'), '1')
        self.assertEqual(serialized_data.get('featuresLayerStyle'), style)
        self.assertEqual(serialized_data.get('featuresLayerDetailsUrlTemplate'), '')

    def test_serialization_with_no_layers(self):
        # Create a MapConfiguration with no layers
        empty_map_config = MapConfiguration.objects.create(
            adjust_bounds_to_layer=False,
            apply_filter_to_features=True,
            load_features_layer_summary=False
        )

        serializer = MapConfigurationSerializer(instance=empty_map_config)
        serialized_data = serializer.data

        expected_data = {
            'applyFilterToFeatures': True,
            'adjustBoundsToLayer': False,
            'loadFeaturesLayerSummary': False,
            # No layers, so no additional fields
        }

        self.assertDictEqual(expected_data, serialized_data)

    @patch('maps.models.reverse', side_effect=mock_reverse_side_effect)
    def test_serialization_with_partial_override_params(self, mock_reverse):

        # Override only some parameters
        override_params = {
            'load_features': False,
            'features_geometries_url': 'https://override.com/features',
        }

        serializer = MapConfigurationSerializer(
            instance=self.map_config,
            context={'override_params': override_params}
        )
        serialized_data = serializer.data

        self.assertFalse(serialized_data['loadFeatures'])
        self.assertEqual(serialized_data['featuresLayerGeometriesUrl'], 'https://override.com/features')
        # Other fields should remain unchanged
        self.assertEqual(serialized_data['loadRegion'], False)
        self.assertEqual(serialized_data['regionId'], '321')


@modify_settings(MIDDLEWARE={'remove': 'ambient_toolbox.middleware.current_user.CurrentUserMiddleware'})
class NutsRegionSummarySerializerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        attribute = Attribute.objects.create(name='Population density', unit='1/km²')
        region = NutsRegion.objects.create(
            nuts_id='TE57',
            name_latn='Test NUTS'
        )
        RegionAttributeValue.objects.create(
            attribute=attribute,
            region=region,
            value=123.321,
            date=datetime.date(2018, 1, 1)
        )
        RegionAttributeValue.objects.create(
            attribute=attribute,
            region=region,
            value=123.321,
            date=datetime.date(2019, 1, 1)
        )
        Attribute.objects.get_or_create(name='Urban rural remoteness', unit='')
        Attribute.objects.create(name='Population', unit='')

    def setUp(self):
        self.region = NutsRegion.objects.get(nuts_id='TE57')
        self.urban_rural_remoteness = Attribute.objects.get(name='Urban rural remoteness')

    def test_serializer_contains_main_data(self):
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('nuts_id', data)
        self.assertIn('name', data)

    def test_population_method_field_returns_value_as_integer(self):
        RegionAttributeValue.objects.create(
            attribute=Attribute.objects.get(name='Population'),
            region=self.region,
            value=123321,
            date=datetime.date(2021, 12, 31)
        )
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('population', data)
        self.assertTrue(type(data['population'] == int))

    def test_population_method_field_returns_non_for_non_existing(self):
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('population', data)
        self.assertFalse(data['population'])

    def test_population_density_method_field_returns_newest_value(self):
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('population_density', data)
        self.assertEqual(data['population_density'], '123.321 per km² (2019)')

    def test_urban_rural_remoteness_method_field_returns_non_if_for_non_existing(self):
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('urban_rural_remoteness', data)
        self.assertFalse(data['urban_rural_remoteness'])

    def test_urban_rural_remoteness_method_field_returns_existing_values(self):
        RegionAttributeTextValue.objects.create(
            attribute=self.urban_rural_remoteness,
            region=self.region,
            value='intermediate, close to a city',
            date=datetime.date.today()
        )
        data = NutsRegionSummarySerializer(self.region).data
        self.assertIn('urban_rural_remoteness', data)
        self.assertEqual(data['urban_rural_remoteness'], 'intermediate, close to a city')
