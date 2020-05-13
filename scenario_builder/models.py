from typing import Tuple

from django.contrib.auth.models import User
from django.contrib.gis.db.models import MultiPolygonField, PointField
from django.core.validators import RegexValidator
from django.db import models, transaction

TYPES = (
    ('administrative', 'administrative'),
    ('custom', 'custom'),
)

GIS_SOURCE_MODELS: Tuple[Tuple[str, str]] = (
    ('HamburgRoadsideTrees', 'HamburgRoadsideTrees'),
)


class Region(models.Model):
    name = models.CharField(max_length=56, null=False)
    country = models.CharField(max_length=56, null=False)
    geom = MultiPolygonField(null=True)

    def __str__(self):
        return self.name


class Catchment(models.Model):
    name = models.CharField(max_length=256, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default='custom', null=True)
    geom = MultiPolygonField(null=True)

    def __str__(self):
        return self.name


class Material(models.Model):
    name = models.CharField(max_length=28)
    description = models.TextField(blank=True, null=True)
    is_feedstock = models.BooleanField(default=False)
    stan_flow_id = models.CharField(max_length=5,
                                    validators=[RegexValidator(regex='^[0-9]{5}?',
                                                               message='STAN id must have 5 digits.s',
                                                               code='nomatch')])

    def __str__(self):
        return self.name


class MaterialComponent(models.Model):
    name = models.CharField(max_length=20)
    description = models.TextField(blank=True, null=True)
    average = models.FloatField()
    standard_deviation = models.FloatField(null=True)
    source = models.CharField(max_length=20)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class GeoDataset(models.Model):
    name = models.CharField(max_length=56, null=False)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=False)
    model_name = models.CharField(max_length=56, choices=GIS_SOURCE_MODELS, null=True)

    def __str__(self):
        return self.name


class SFBSite(models.Model):
    name = models.CharField(max_length=20, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    geom = PointField(null=True)

    def __str__(self):
        return self.name


class InventoryAlgorithm(models.Model):
    """
    Links functions that are defined in the InventoryMixin to the corresponding geodatasets and feedstocks in the
    database. This model is for configuration by admins and must not be available to users. Customization by users can
    be done in InventoryAlgorithmParameter and InventoryAlgorithmParameterValue.
    """
    name = models.CharField(max_length=56)
    function_name = models.CharField(max_length=56, null=True)
    description = models.TextField(blank=True, null=True)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(Material, on_delete=models.CASCADE, limit_choices_to={'is_feedstock': True})
    default = models.BooleanField('Default for this combination of geodataset and feedstock', default=False)
    source = models.CharField(max_length=200, blank=True, null=True)

    def save(self, *args, **kwargs):
        """
        There can only be one default algorithm per geodataset/feedstock combination. This method adds a corresponding
        check when a record is saved. It gets rid of any previous default entry with the same geodataset/feedstock
        combination when the new algorithm is marked as default.
        """
        if not self.default:
            if not InventoryAlgorithm.objects.filter(geodataset=self.geodataset, feedstock=self.feedstock,
                                                     default=True):
                self.default = True
            return super(InventoryAlgorithm, self).save(*args, **kwargs)
        with transaction.atomic():
            InventoryAlgorithm.objects.filter(geodataset=self.geodataset, feedstock=self.feedstock, default=True) \
                .update(default=False)
            return super(InventoryAlgorithm, self).save(*args, **kwargs)

    def __str__(self):
        return self.name


class InventoryAlgorithmParameter(models.Model):
    short_name = models.CharField(max_length=28,
                                  validators=[RegexValidator(regex='^\w{1,28}$',
                                                             message='STAN id must have 5 digits.s',
                                                             code='nomatch')])
    descriptive_name = models.CharField(max_length=56)
    description = models.TextField(blank=True, null=True)
    inventory_algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE, null=True)
    unit = models.CharField(max_length=20, blank=True, null=True)
    is_required = models.BooleanField(default=False)

    def __str__(self):
        return self.short_name


class InventoryAlgorithmParameterValue(models.Model):
    name = models.CharField(max_length=56)
    description = models.TextField(blank=True, null=True)
    parameter = models.ForeignKey(InventoryAlgorithmParameter, on_delete=models.CASCADE)
    value = models.FloatField()
    standard_deviation = models.FloatField(null=True)
    source = models.CharField(max_length=200, blank=True, null=True)
    default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.default:
            if not InventoryAlgorithmParameterValue.objects.filter(parameter=self.parameter, default=True):
                self.default = True
            return super(InventoryAlgorithmParameterValue, self).save(*args, **kwargs)
        with transaction.atomic():
            InventoryAlgorithmParameterValue.objects.filter(parameter=self.parameter, default=True).update(
                default=False)
            return super(InventoryAlgorithmParameterValue, self).save(*args, **kwargs)

    def __str__(self):
        return self.name


class ScenarioConfigurationError(Exception):
    pass


class Scenario(models.Model):
    name = models.CharField(max_length=56, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    site = models.ForeignKey(SFBSite, on_delete=models.CASCADE, null=True)
    catchment = models.ForeignKey(Catchment, on_delete=models.CASCADE, null=True)
    feedstocks = models.ManyToManyField(Material, limit_choices_to={'is_feedstock': True})
    use_default_configuration = models.BooleanField(default=True)

    def is_valid_configuration(self):
        # At least one entry for a scenario
        if not ScenarioInventoryConfiguration.objects.filter(scenario=self):
            raise ScenarioConfigurationError('The scenario is not configured.')

        # Get all inventory algorithms that are used in this scenario
        algorithms = [c.inventory_algorithm for c in
                      ScenarioInventoryConfiguration.objects.filter(scenario=self).distinct('inventory_algorithm')]

        # Are all required parameters included in the configurarion?
        required = \
            InventoryAlgorithmParameter.objects.filter(inventory_algorithm__in=algorithms, is_required=True) \
                .values_list('id')
        configured = \
            ScenarioInventoryConfiguration.objects.filter(inventory_algorithm__in=algorithms) \
                .values_list('inventory_parameter')
        if not set(required).issubset(configured):
            raise ScenarioConfigurationError('Not all required parameters are defined.')

        # Is each parameter only defined once per scenario?
        if not len(set(configured)) == len(configured):
            raise ScenarioConfigurationError('There are double defined parameters in the configuration')

    def create_default_configuration(self):
        """
        Gathers all defaults that are necessary to evaluate a defined base scenario and saves them as entries in
        ScenarioInventoryConfiguration. The scenario can now be evaluated with defaults or be customized in a second
        step.
        :return:
        """
        for feedstock in self.feedstocks.all():
            for inventory_algorithm in InventoryAlgorithm.objects.filter(feedstock=feedstock,
                                                                         geodataset__region=self.region,
                                                                         default=True):
                for parameter in InventoryAlgorithmParameter.objects.filter(inventory_algorithm=inventory_algorithm):
                    config_entry = ScenarioInventoryConfiguration()
                    config_entry.scenario = self
                    config_entry.feedstock = feedstock
                    config_entry.inventory_algorithm = inventory_algorithm
                    config_entry.geodataset = inventory_algorithm.geodataset
                    config_entry.inventory_parameter = parameter
                    config_entry.inventory_value = InventoryAlgorithmParameterValue.objects.get(parameter=parameter,
                                                                                                default=True)
                    config_entry.save()

    def save(self, *args, **kwargs):
        super(Scenario, self).save(*args, **kwargs)
        if self.use_default_configuration:
            self.create_default_configuration()

    def __str__(self):
        return self.name


class ScenarioInventoryConfiguration(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(Material, limit_choices_to={'is_feedstock': True}, on_delete=models.CASCADE)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    inventory_algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE)
    inventory_parameter = models.ForeignKey(InventoryAlgorithmParameter, on_delete=models.CASCADE)
    inventory_value = models.ForeignKey(InventoryAlgorithmParameterValue, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        # Only save if there is no previous entry for a parameter in a scenario. Otherwise drop old entry first.
        if not ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario,
                                                             inventory_algorithm=self.inventory_algorithm,
                                                             inventory_parameter=self.inventory_parameter):
            super(ScenarioInventoryConfiguration, self).save(*args, **kwargs)
        else:
            ScenarioInventoryConfiguration.objects \
                .filter(scenario=self.scenario,
                        inventory_algorithm=self.inventory_algorithm,
                        inventory_parameter=self.inventory_parameter) \
                .update(inventory_value=self.inventory_value)


class BaseScenarioResult(models.Model):
    """
    Base class for scenario results that need to be saved in the database. It relates any kind of result inherits from
    this to the corresponding scenario and algorithm. This should not be used directly. Instead, use ancestors that
    provide the specific required functionality for each result type, e.g. statistics, gis, etc.
    """
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, null=True)
    algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE, null=True)
    last_update = models.DateTimeField(auto_now=True)


class InventoryResultPointLayer(BaseScenarioResult):
    """
    Base class for dynamically created result models that consist of a point layer. This should not be used directly.
    Use type(<"result name">, (InventoryResultPointLayer,),) to create ancestors.
    """
    geom = PointField()
    average = models.FloatField(null=True)
    standard_deviation = models.FloatField(null=True)
