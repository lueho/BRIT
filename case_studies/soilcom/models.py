import celery
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Count, Q, Sum
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from bibliography.models import Source
from distributions.models import Period, TemporalDistribution, Timestep
from maps.models import Catchment
from materials.models import Material, MaterialCategory, Sample, SampleSeries
from users.models import get_default_owner
from utils.models import NamedUserObjectModel, OwnedObjectModel, PropertyValue


class CollectionCatchment(Catchment):
    class Meta:
        proxy = True

    @property
    def downstream_collections(self):
        qs = Collection.objects.filter(catchment__in=self.descendants(include_self=True))
        qs = qs.select_related('catchment', 'collector', 'waste_stream__category', 'collection_system')
        return qs

    @property
    def upstream_collections(self):
        qs = Collection.objects.filter(catchment__in=self.ancestors())
        qs = qs.select_related('catchment', 'collector', 'waste_stream__category', 'collection_system')
        return qs


class Collector(NamedUserObjectModel):
    website = models.URLField(max_length=511, blank=True, null=True)
    catchment = models.ForeignKey(CollectionCatchment, blank=True, null=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Waste Collector'


class CollectionSystem(NamedUserObjectModel):
    class Meta:
        verbose_name = 'Waste Collection System'

    def __str__(self):
        return self.name


class WasteCategory(NamedUserObjectModel):
    class Meta:
        verbose_name = 'Waste Category'
        verbose_name_plural = 'Waste categories'


class WasteComponentManager(models.Manager):

    def get_queryset(self):
        categories = MaterialCategory.objects.filter(name__in=('Biowaste component',))
        return super().get_queryset().filter(categories__in=categories)


class WasteComponent(Material):
    objects = WasteComponentManager()

    class Meta:
        proxy = True


@receiver(post_save, sender=WasteComponent)
def add_material_category(sender, instance, created, **kwargs):
    if created:
        category = MaterialCategory.objects.get(name='Biowaste component')
        instance.categories.add(category)
        instance.save()


class WasteStreamQueryset(models.query.QuerySet):

    def match_allowed_materials(self, allowed_materials):
        """
        Returns a queryset of all waste streams that match the given combination of allowed_materials
        :param allowed_materials: Queryset
        :return: Queryset
        """

        return self.alias(
            allowed_materials_count=models.Count('allowed_materials'),
            allowed_materials_matches=models.Count('allowed_materials',
                                                   filter=models.Q(allowed_materials__in=allowed_materials))
        ).filter(
            allowed_materials_count=len(allowed_materials),
            allowed_materials_matches=len(allowed_materials)
        )

    def get_or_create(self, defaults=None, **kwargs):
        """
        Customizes the regular get_or_create to incorporate comparison of many-to-many relationships of
        allowed_materials. I.e. a queryset of allowed_materials can be passed to this method to get a waste stream
        with exactly that combination of allowed materials. Each possible combination can only appear once in the
        database.
        """

        if defaults:
            defaults = defaults.copy()

        if 'allowed_materials' in kwargs:
            allowed_materials = kwargs.pop('allowed_materials')
            qs = self.match_allowed_materials(allowed_materials)
        else:
            allowed_materials = Material.objects.none()
            qs = self

        if defaults:
            allowed_materials = defaults.pop('allowed_materials', allowed_materials)

        instance, created = super(WasteStreamQueryset, qs).get_or_create(defaults=defaults, **kwargs)

        if created:
            instance.allowed_materials.add(*allowed_materials)
            if not instance.name:
                instance.name = f'{instance.category.name} {len(allowed_materials)}'
                instance.save()

        return instance, created

    def update_or_create(self, defaults=None, **kwargs):
        """
        Updates one object that matches the given kwargs on the fields given in defaults. In comparison to the
        conventional update_or_create, this method enforces that every combination of allowed materials and category
        only exists uniquely in the database.

        """

        if defaults:
            defaults = defaults.copy()

        instance, created = self.get_or_create(defaults=defaults, **kwargs)

        if not created:

            new_allowed_materials = defaults.pop('allowed_materials', None)
            category = kwargs.get('category', None)

            if new_allowed_materials:
                qs = self.match_allowed_materials(new_allowed_materials)
                if category:
                    qs = qs.filter(category=category)
                if qs.exists():
                    raise ValidationError(
                        """
                        Waste stream cannot be updated. Equivalent waste stream of equal category and same combination of 
                        allowed materials already exists.
                        """
                    )

            self.filter(id=instance.id).update(**defaults)

            if new_allowed_materials:
                instance.allowed_materials.clear()
                instance.allowed_materials.add(*new_allowed_materials)

            instance.refresh_from_db()

        return instance, created


class WasteStream(NamedUserObjectModel):
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT)
    allowed_materials = models.ManyToManyField(Material)
    composition = models.ManyToManyField(SampleSeries)

    objects = WasteStreamQueryset.as_manager()

    class Meta:
        verbose_name = 'Waste Stream'


class WasteFlyerManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(type='waste_flyer')


class WasteFlyer(Source):
    objects = WasteFlyerManager()

    class Meta:
        proxy = True
        verbose_name = 'Waste Flyer'

    def __str__(self):
        if self.url:
            return self.url
        else:
            return ''


@receiver(pre_save, sender=WasteFlyer)
def set_source_type_and_check_url(sender, instance, **kwargs):
    instance.type = 'waste_flyer'


@receiver(post_save, sender=WasteFlyer)
def check_url_valid(sender, instance, created, **kwargs):
    if created:
        celery.current_app.send_task('check_wasteflyer_url', (instance.pk,))


class CollectionSeasonManager(models.Manager):

    def get_queryset(self):
        distribution = TemporalDistribution.objects.get(owner=get_default_owner(), name='Months of the year')
        return super().get_queryset().filter(distribution=distribution)


class CollectionSeason(Period):
    objects = CollectionSeasonManager()

    class Meta:
        proxy = True

    def __str__(self):
        return f'{self.first_timestep.name} - {self.last_timestep.name}'


FREQUENCY_TYPES = (
    ('Fixed', 'Fixed'),
    ('Fixed-Flexible', 'Fixed-Flexible'),
    ('Fixed-Seasonal', 'Fixed-Seasonal'),
    ('Seasonal', 'Seasonal'),
)


class CollectionFrequency(NamedUserObjectModel):
    type = models.CharField(max_length=16, choices=FREQUENCY_TYPES, default='Fixed')
    seasons = models.ManyToManyField(CollectionSeason, through='CollectionCountOptions')

    class Meta:
        verbose_name_plural = 'collection frequencies'

    @property
    def has_options(self):
        frequencies_with_options = CollectionCountOptions.objects.filter(
            Q(option_1__isnull=False) | Q(option_2__isnull=False) | Q(option_3__isnull=False)
        ).values_list('frequency')
        return self.id in [f[0] for f in frequencies_with_options]

    @property
    def seasonal(self):
        qs = CollectionFrequency.objects.annotate(season_count=Count('seasons')).filter(season_count__gt=1)
        return self in qs

    @property
    def collections_per_year(self):
        return self.collectioncountoptions_set.aggregate(Sum('standard'))['standard__sum']


class CollectionCountOptions(OwnedObjectModel):
    """
    The available options of how many collections  will be provided within a given season. Is used as 'through' model
    for the many-to-many relation of CollectionFrequency and CollectionSeason.
    """
    frequency = models.ForeignKey(CollectionFrequency, on_delete=models.CASCADE, null=False)
    season = models.ForeignKey(CollectionSeason, on_delete=models.CASCADE, null=False)
    standard = models.PositiveSmallIntegerField(blank=True, null=True)
    option_1 = models.PositiveSmallIntegerField(blank=True, null=True)
    option_2 = models.PositiveSmallIntegerField(blank=True, null=True)
    option_3 = models.PositiveSmallIntegerField(blank=True, null=True)

    @property
    def non_standard_options(self):
        return [option for option in (self.option_1, self.option_2, self.option_3) if option]


YEAR_VALIDATOR = RegexValidator(r'^([0-9]{4})$', message='Year needs to be in YYYY format.', code='invalid year')

FEE_SYSTEMS = (
    ('No fee', 'No fee'),
    ('Fixed fee', 'Fixed fee',),
    ('Pay as you throw (PAYT)', 'Pay as you throw (PAYT)',)
)


class Collection(NamedUserObjectModel):
    collector = models.ForeignKey(Collector, on_delete=models.CASCADE, blank=True, null=True)
    catchment = models.ForeignKey(CollectionCatchment, on_delete=models.PROTECT, blank=True, null=True, related_name='collections')
    collection_system = models.ForeignKey(CollectionSystem, on_delete=models.CASCADE, blank=True, null=True, related_name='collections')
    waste_stream = models.ForeignKey(WasteStream, on_delete=models.SET_NULL, blank=True, null=True, related_name='collections')
    frequency = models.ForeignKey(CollectionFrequency, on_delete=models.SET_NULL, blank=True, null=True, related_name='collections')
    connection_rate = models.FloatField(blank=True, null=True)
    connection_rate_year = models.PositiveSmallIntegerField(blank=True, null=True, validators=[YEAR_VALIDATOR])
    fee_system = models.CharField(max_length=32, choices=FEE_SYSTEMS, blank=True, null=True)
    samples = models.ManyToManyField(Sample, related_name='collections')
    flyers = models.ManyToManyField(WasteFlyer, related_name='collections')
    sources = models.ManyToManyField(Source)

    @property
    def geom(self):
        return self.catchment.geom

    @property
    def connection_rate_string_representation(self):
        return f'{self.connection_rate * 100}\u00A0%'

    def construct_name(self):
        catchment = self.catchment.name if self.catchment else 'Unknown catchment'
        system = self.collection_system.name if self.collection_system else 'Unknown collection system'
        category = 'Unknown waste category'
        if self.waste_stream:
            if self.waste_stream.category:
                category = self.waste_stream.category.name
        return f'{catchment} {category} {system}'

    def __str__(self):
        return self.name


@receiver(pre_save, sender=Collection)
def name_collection(sender, instance, **kwargs):
    instance.name = instance.construct_name()


@receiver(post_save, sender=WasteStream)
@receiver(post_save, sender=WasteCategory)
@receiver(post_save, sender=CollectionSystem)
@receiver(post_save, sender=Catchment)
@receiver(post_save, sender=CollectionCatchment)
def update_collection_names(sender, instance, created, **kwargs):
    if sender == WasteCategory:
        collections = Collection.objects.filter(waste_stream__category=instance)
    else:
        collections = instance.collections.all()
    for collection in collections:
        collection.save()


class CollectionPropertyValue(PropertyValue):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(null=True, validators=[YEAR_VALIDATOR])


class AggregatedCollectionPropertyValue(PropertyValue):
    collections = models.ManyToManyField(Collection)
    year = models.PositiveSmallIntegerField(null=True, validators=[YEAR_VALIDATOR])
