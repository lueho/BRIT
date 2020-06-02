from django.apps import apps
from django.contrib.gis.db.models import PointField, MultiPolygonField
from django.db import models, connection

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
    supported_geometry_types = ['Point', 'MultiPolygon']

    def create_or_replace(self, **kwargs):

        results = kwargs.pop('results')

        if not results['features']:
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

            layer, created = Layer.objects.get_or_create(table_name=kwargs['table_name'], defaults=kwargs)

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
                    layer = self.create(**kwargs)
                    layer.add_layer_fields(fields)
                    feature_collection = layer.update_or_create_feature_collection()
                    layer.create_feature_table()

            for feature in features:
                feature_collection.objects.create(**feature)

            return layer, feature_collection


class Layer(models.Model):
    """
    Registry of all created layers
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

    def add_layer_fields(self, fields: dict):
        for field_name, data_type in fields.items():
            field, created = LayerField.objects.get_or_create(field_name=field_name, data_type=data_type)
            self.layer_fields.add(field)

    def update_or_create_feature_collection(self):

        # Empty app registry from any previous version of this model
        model_name = self.table_name
        if model_name in apps.all_models['layer_manager']:
            del apps.all_models['layer_manager'][model_name]

        attrs = {
            '__module__': 'layer_manager.models'
        }

        # Add correct geometry column to model
        if self.geom_type == 'Point':
            attrs['geom'] = PointField(srid=4326)
        elif self.geom_type == 'MultiPolygon':
            attrs['geom'] = MultiPolygonField(srid=4326)

        # Add all custom columns to model
        for field in self.layer_fields.all():
            attrs[field.field_name] = LayerField.model_field_type(field.data_type)

        # Create model class and assign table_name
        model = type(model_name, (models.Model,), attrs)
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

    def get_feature_collection(self):
        """
        Returns a model for the table that holds the GIS features of the result layer
        """

        # If the model is still registered, return original model
        if self.table_name in apps.all_models['layer_manager']:
            return apps.all_models['layer_manager'][self.table_name]
        else:
            return self.update_or_create_feature_collection()

    def is_defined_by(self, **kwargs):

        fields = {}
        for field in self.layer_fields.all():
            fields[field.field_name] = field.data_type

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
    layer = models.ForeignKey(Layer, on_delete=models.CASCADE)
