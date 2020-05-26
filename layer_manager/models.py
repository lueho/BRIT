from django.apps import apps
from django.contrib.gis.db.models import PointField, MultiPolygonField
from django.contrib.gis.geos import Point
from django.db import models, connection

from scenario_builder.models import Scenario, InventoryAlgorithm


class ModelAlreadyRegistered(Exception):
    """The model you are trying to create is already registered"""


class TableAlreadyExists(Exception):
    """The table you are trying to create already exists in the database"""


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
            return models.FloatField()
        elif data_type == 'int':
            return models.IntegerField()
        elif data_type == 'str':
            return models.CharField(max_length=56)


class LayerManager(models.Manager):

    def create_or_replace_layer(self, **kwargs):
        kwargs['table_name'] = 'result_of_scenario_' + \
                               str(kwargs['scenario'].id) + '_algorithm_' + \
                               str(kwargs['algorithm'].id)
        # Check if this layer has previously been created
        if not Layer.objects.filter(table_name=kwargs['table_name']):
            pass
        else:
            layer = Layer.objects.get(table_name=kwargs['table_name'])
            layer_model = layer.get_layer_model()
            if self._is_identical_layer(layer, **kwargs):
                layer_model.objects.all().delete()
                return layer
            else:
                self._delete_layer_table(layer_model)
                layer.delete()
                del apps.all_models['layer_manager'][kwargs['table_name']]

        if kwargs['geom_type'] == Point:
            kwargs['geom_type'] = 'point'

        fields = kwargs.pop('fields')
        layer = self.create(name=kwargs['name'],
                            geom_type=kwargs['geom_type'],
                            table_name=kwargs['table_name'],
                            scenario=kwargs['scenario'],
                            algorithm=kwargs['algorithm'])
        for field_name, data_type in fields.items():
            layer.layer_fields.add(LayerField.objects.create(field_name=field_name, data_type=data_type))

        layer_model = self._create_layer_model(fields, kwargs['geom_type'], kwargs['table_name'])
        self._create_layer_table(layer_model)

        return layer

    @staticmethod
    def _is_identical_layer(layer, **kwargs):

        fields = {}
        for field in layer.layer_fields.all():
            fields[field.field_name] = field.data_type

        comparisons = [
            layer.table_name == kwargs['table_name'],
            layer.geom_type == kwargs['geom_type'],
            layer.scenario == kwargs['scenario'],
            layer.algorithm == kwargs['algorithm'],
            fields == kwargs['fields']
        ]
        return all(comparisons)

    @staticmethod
    def _create_layer_model(fields=None, geom_type=None, table_name=None):

        if fields is None:
            fields = {}

        # Empty app registry from any previous version of this model
        model_name = table_name
        if model_name in apps.all_models['layer_manager']:
            raise ModelAlreadyRegistered
            # del apps.all_models['layer_manager'][model_name]

        attrs = {
            '__module__': 'layer_manager.models'
        }

        # Add correct geometry column to model
        if geom_type == 'point':
            attrs['geom'] = PointField(srid=4326)
        elif geom_type == 'multi-polygon':
            attrs['geom'] = MultiPolygonField(srid=4326)

        # Add all custom columns to model
        for field_name, data_type in fields.items():
            attrs[field_name] = LayerField.model_field_type(data_type)

        # Create model class and assign table_name
        model = type(model_name, (models.Model,), attrs)
        model._meta.db_table = table_name

        return model

    @staticmethod
    def _create_layer_table(layer_model):
        """
        Creates a new table with all given fields from a model
        :return:
        """

        # Check if any table of the name already exists
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT to_regclass('{layer_model._meta.db_table}')")
            if cursor.fetchone()[0]:
                raise TableAlreadyExists

        # After cleanup, now create the new version of the result table
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(layer_model)

    @staticmethod
    def _delete_layer_table(layer_model):
        """
        Deletes a table from a given model
        :param layer_model:
        :return:
        """
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT to_regclass('{layer_model._meta.db_table}')")
            if cursor.fetchone()[0] is None:
                return

        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(layer_model)


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

    def get_layer_model(self):
        """
        Returns a model for the table that holds the GIS features of the result layer
        """

        # If the model is still registered, return original model
        if self.table_name in apps.all_models['layer_manager']:
            return apps.all_models['layer_manager'][self.table_name]

        # If the model cannot be found, recreate it
        attrs = {
            '__module__': 'layer_manager.models'
        }

        # Add correct geometry column to model
        if self.geom_type == 'point':
            attrs['geom'] = PointField(srid=4326)
        elif self.geom_type == 'multi-polygon':
            attrs['geom'] = MultiPolygonField(srid=4326)

        for field in self.layer_fields.all():
            attrs[field.field_name] = LayerField.model_field_type(field.data_type)
        model = type(self.table_name, (models.Model,), attrs)
        model._meta.db_table = self.table_name
        return model
