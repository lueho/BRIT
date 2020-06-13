import django.contrib.gis.db.models as gis_models
from django.apps import apps
from django.db import models, connection
from django.urls import reverse

from scenario_builder.models import Scenario, InventoryAlgorithm
from .exceptions import InvalidGeometryType, NoFeaturesProvided, TableAlreadyExists


class LayerField(models.Model):
    """
    Holds all field definitions of GIS layers. Used to recreate a dynamically created model in case it is lost from
    the apps registry.
    """

    field_name = models.CharField(max_length=63)
    data_type = models.CharField(max_length=10)

    def data_type_object(self):
        if self.data_type == 'float':
            return models.FloatField()
        elif self.data_type == 'int':
            return models.IntegerField()

    @staticmethod
    def model_field_type(data_type: str):
        if data_type == 'float':
            return models.FloatField(blank=True, null=True)
        elif data_type == 'int':
            return models.IntegerField(blank=True, null=True)
        elif data_type == 'str':
            return models.CharField(blank=True, null=True, max_length=200)


class LayerManager(models.Manager):
    supported_geometry_types = ['Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon', ]

    def create_or_replace(self, **kwargs):

        results = kwargs.pop('results')

        if 'features' not in results:
            raise NoFeaturesProvided(results)
        else:
            features = results['features']
            fields = {}
            # The data types of the fields are detected from their content. Any column that has only null values
            # will be omitted completely
            fields_with_unknown_datatype = list(features[0].keys())
            for feature in features:
                if not fields_with_unknown_datatype:
                    break
                for key, value in feature.items():
                    if feature[key] and key in fields_with_unknown_datatype:
                        fields[key] = type(value).__name__
                        fields_with_unknown_datatype.remove(key)

            # At this point there might be fields left out because there were only null values from which the
            # data type could be detected. They should be omitted but this information should be logged
            # TODO: add omitted columns info to log

            kwargs['geom_type'] = fields.pop('geom')
            if kwargs['geom_type'] not in self.supported_geometry_types:
                raise InvalidGeometryType(kwargs['geom_type'])

            kwargs['table_name'] = 'result_of_scenario_' + \
                                   str(kwargs['scenario'].id) + '_algorithm_' + \
                                   str(kwargs['algorithm'].id)

            layer, created = super().get_or_create(table_name=kwargs['table_name'], defaults=kwargs)

            if created:
                layer.add_layer_fields(fields)
                feature_collection = layer.update_or_create_feature_collection()
                layer.create_feature_table()
            else:
                if layer.is_defined_by(fields=fields, **kwargs):
                    feature_collection = layer.get_feature_collection()
                    feature_collection.objects.all().delete()
                else:
                    layer.delete()
                    layer = super().create(**kwargs)
                    layer.add_layer_fields(fields)
                    feature_collection = layer.update_or_create_feature_collection()
                    layer.create_feature_table()

                layer.delete_aggregated_values()

            for feature in features:
                feature_collection.objects.create(**feature)

        layer.add_aggregated_values(results['aggregated_values'])

        return layer, feature_collection


class Layer(models.Model):
    """
    Registry of all created layers. This main model holds all meta information about each layer. When a new layer record
    is created, another custom model named "features collection" is automatically generated, preserving the original
    shape of the gis source dataset as much as required. The feature collection can be used to manage the actual
    features of the layer. It will create a separate database table with the name given in "table_name" to store the
    features.
    """

    name = models.CharField(max_length=56)
    geom_type = models.CharField(max_length=20)
    table_name = models.CharField(max_length=200)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE)
    layer_fields = models.ManyToManyField(LayerField)

    objects = LayerManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['table_name'], name='unique table_name')
        ]

    def add_aggregated_values(self, aggregates: []):
        for aggregate in aggregates:
            LayerAggregatedValue.objects.create(name=aggregate['name'],
                                                value=aggregate['value'],
                                                unit=aggregate['unit'],
                                                layer=self)

    def add_layer_fields(self, fields: dict):
        for field_name, data_type in fields.items():
            field, created = LayerField.objects.get_or_create(field_name=field_name, data_type=data_type)
            self.layer_fields.add(field)

    def as_dict(self):
        return {
            'name': self.name,
            'geom_type': self.geom_type,
            'table_name': self.table_name,
            'scenario': self.scenario,
            'inventory_algorithm': self.algorithm,
            'layer_fields': [field for field in self.layer_fields.all()],
            'aggregated_results': [
                {'name': aggregate.name,
                 'value': int(aggregate.value),
                 'unit': aggregate.unit}
                for aggregate in self.layeraggregatedvalue_set.all()
            ]
        }

    def update_or_create_feature_collection(self):
        """
        Dynamically creates model connected to this layer instance that is used to handle its features and store them
        in a separate custom database table.
        """

        # Empty app registry from any previous version of this model
        model_name = self.table_name
        if model_name in apps.all_models['layer_manager']:
            del apps.all_models['layer_manager'][model_name]

        attrs = {
            '__module__': 'layer_manager.models',
            'geom': getattr(gis_models, self.geom_type + 'Field')(srid=4326)
        }

        # Add all custom columns to model
        for field in self.layer_fields.all():
            attrs[field.field_name] = LayerField.model_field_type(field.data_type)

        # Create model class and assign table_name
        model = type(model_name, (models.Model,), attrs)
        model._meta.layer = self
        model._meta.db_table = self.table_name

        return model

    def create_feature_table(self):
        """
        Creates a new table with all given fields from a model
        :return:
        """

        feature_collection = self.get_feature_collection()

        # Check if any table of the name already exists
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT to_regclass('{feature_collection._meta.db_table}')")
            if cursor.fetchone()[0]:
                raise TableAlreadyExists

        # After cleanup, now create the new version of the result table
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(feature_collection)

    def feature_table_url(self):
        return reverse('scenario_result_map', kwargs={'pk': self.scenario.id, 'algo_pk': self.algorithm.id})

    def delete(self, **kwargs):
        self.delete_feature_table()
        del apps.all_models['layer_manager'][self.table_name]
        super().delete()

    def delete_feature_table(self):
        """
        Deletes a table from a given model
        :return:
        """
        feature_collection = self.get_feature_collection()

        with connection.cursor() as cursor:
            cursor.execute(f"SELECT to_regclass('{feature_collection._meta.db_table}')")
            if cursor.fetchone()[0] is None:
                return

        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(feature_collection)

    def delete_aggregated_values(self):
        LayerAggregatedValue.objects.filter(layer=self).delete()

    def feedstock(self):
        return self.algorithm.feedstock

    def get_feature_collection(self):
        """
        Returns the feature collection model that is used to manage the features connected to this layer.
        """

        # If the model is already registered, return original model
        if self.table_name in apps.all_models['layer_manager']:
            return apps.all_models['layer_manager'][self.table_name]
        else:
            return self.update_or_create_feature_collection()

    def is_defined_by(self, **kwargs):

        fields = {field.field_name: field.data_type for field in self.layer_fields.all()}

        comparisons = [
            self.table_name == kwargs['table_name'],
            self.geom_type == kwargs['geom_type'],
            self.scenario == kwargs['scenario'],
            self.algorithm == kwargs['algorithm'],
            fields == kwargs['fields']
        ]
        return all(comparisons)


class LayerAggregatedValue(models.Model):
    """
    Class to hold all aggregated results from a result layer
    """

    name = models.CharField(max_length=63)
    value = models.FloatField()
    unit = models.CharField(max_length=15, blank=True, null=True, default='')
    layer = models.ForeignKey(Layer, on_delete=models.CASCADE)
