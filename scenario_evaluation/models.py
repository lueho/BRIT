from django.apps import apps
from django.contrib.gis.db.models import PointField
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import RegexValidator
from django.db import models, connection

from scenario_builder.models import InventoryAlgorithm, Scenario


class ScenarioResult(models.Model):
    """
    Base class for scenario results that need to be saved in the database. It relates any kind of result inherits from
    this to the corresponding scenario and algorithm. This should not be used directly. Instead, use ancestors that
    provide the specific required functionality for each result type, e.g. statistics, gis, etc.
    """
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE, null=True)
    last_update = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True, null=True)


class ScenarioResultLayer(ScenarioResult):
    name = models.CharField(max_length=200)
    base_class = models.CharField(max_length=200)
    table_name = models.CharField(max_length=200,
                                  validators=[RegexValidator(regex=r'^\w{1,28}$',
                                                             message='Invalid parameter function_name. Do not use space or \
                                                               special characters.',
                                                             code='invalid_parameter_name')],
                                  null=True)

    class TableDoesNotExist(ObjectDoesNotExist):
        pass

    def get_base_class(self):
        """
        Returns the actual base class instead of the base class name as string.
        :return: base_class
        """
        return apps.all_models['scenario_evaluation'][self.base_class]

    def get_layer_model(self):
        """
        Recreates the model from the table function_name and returns it as class.
        :return: model
        """
        # Find model that corresponds to the table function_name
        registered_result_models = apps.all_models['scenario_evaluation']
        if self.table_name in registered_result_models.keys():
            return registered_result_models[self.table_name]

        # If no registered model was found for the table function_name, check, whether it exists in the database
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT to_regclass('{self.table_name}')")
            if not cursor.fetchone()[0]:
                raise self.TableDoesNotExist()

        # If table exists but has no registered model, recreate model from table
        attrs = {
            '__module__': 'scenario_evaluation.models',
        }
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT column_name, udt_name FROM information_schema.columns WHERE table_name='{self.table_name}'")
            columns = cursor.fetchall()
        field_names = [column[0] for column in columns]
        for field_name in field_names:
            if field_name not in list(LAYER_MODELS[self.base_class]._meta.fields):
                attrs[field_name] = models.FloatField(null=True)
        return type(self.table_name, LAYER_MODELS[self.base_class], attrs)


class ScenarioResultLayerField(models.Model):
    field_name = models.CharField(max_length=56)
    field_type = models.CharField(max_length=56)
    layer = models.ForeignKey(ScenarioResultLayer, on_delete=models.CASCADE)


class ScenarioResultAggregate(ScenarioResult):
    name = models.CharField(max_length=56)
    value = models.FloatField()
    standard_deviation = models.FloatField(null=True)
    unit = models.CharField(max_length=56, null=True)


class InventoryResultPointLayer(models.Model):
    """
    Base class for dynamically created result models that consist of a point layer. This should not be used directly.
    Use type(<"result function_name">, (InventoryResultPointLayer,),) to create ancestors.
    """
    geom = PointField()

    class Meta:
        abstract = True


LAYER_MODELS = {
    'InventoryResultPointLayer': InventoryResultPointLayer
}
