from ai_django_core.models import CommonInfo
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.db import models
from django.urls import reverse, exceptions

from users.models import get_default_owner


class CRUDUrlsMixin(models.Model):
    class Meta:
        abstract = True

    @classmethod
    @property
    def list_url(cls):
        try:
            return reverse(f'{cls.__name__.lower()}-list')
        except exceptions.NoReverseMatch:
            return None

    @classmethod
    @property
    def modal_list_url(cls):
        try:
            return reverse(f'{cls.__name__.lower()}-list-modal')
        except exceptions.NoReverseMatch:
            return None

    @classmethod
    @property
    def options_list_url(cls):
        try:
            return reverse(f'{cls.__name__.lower()}-options')
        except exceptions.NoReverseMatch:
            return None

    @classmethod
    @property
    def create_url(cls):
        try:
            return reverse(f'{cls.__name__.lower()}-create')
        except exceptions.NoReverseMatch:
            return None

    @classmethod
    @property
    def modal_create_url(cls):
        try:
            return reverse(f'{cls.__name__.lower()}-create-modal')
        except exceptions.NoReverseMatch:
            return None

    @property
    def detail_url(self):
        try:
            return reverse(f'{self.__class__.__name__.lower()}-detail', kwargs={'pk': self.pk})
        except exceptions.NoReverseMatch:
            return None

    @property
    def modal_detail_url(self):
        try:
            return reverse(f'{self.__class__.__name__.lower()}-detail-modal', kwargs={'pk': self.pk})
        except exceptions.NoReverseMatch:
            return None

    def get_absolute_url(self):
        try:
            return reverse(f'{self.__class__.__name__.lower()}-detail', kwargs={'pk': self.pk})
        except exceptions.NoReverseMatch:
            return None

    @property
    def update_url(self):
        try:
            return reverse(f'{self.__class__.__name__.lower()}-update', kwargs={'pk': self.pk})
        except exceptions.NoReverseMatch:
            return None

    @property
    def modal_update_url(self):
        try:
            return reverse(f'{self.__class__.__name__.lower()}-update-modal', kwargs={'pk': self.pk})
        except exceptions.NoReverseMatch:
            return None

    @property
    def delete_url(self):
        try:
            return reverse(f'{self.__class__.__name__.lower()}-delete', kwargs={'pk': self.pk})
        except exceptions.NoReverseMatch:
            return None

    @property
    def modal_delete_url(self):
        try:
            return reverse(f'{self.__class__.__name__.lower()}-delete-modal', kwargs={'pk': self.pk})
        except exceptions.NoReverseMatch:
            return None


def get_default_owner_pk():
    return get_default_owner().pk


class OwnedObjectModel(CRUDUrlsMixin, CommonInfo):
    owner = models.ForeignKey(User, on_delete=models.PROTECT, default=get_default_owner_pk)
    visible_to_groups = models.ManyToManyField(Group)

    class Meta:
        abstract = True


class NamedUserObjectModel(OwnedObjectModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Unit(NamedUserObjectModel):
    dimensionless = models.BooleanField(default=False, null=True)
    reference_quantity = models.ForeignKey(
        'Property',
        related_name='reference_quantity_in_units',
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )

    class Meta:
        unique_together = ['owner', 'name']


def get_default_unit_pk():
    return Unit.objects.get_or_create(
        owner=get_default_owner(),
        name=getattr(settings, 'DEFAULT_UNIT_NAME', 'No unit')
    )[0].pk


class Property(NamedUserObjectModel):
    """
    Defines properties that can be shared among other models. Allows to compare instances of different models that share
    the same properties while enforcing the use of matching units.
    """
    unit = models.CharField(max_length=63)
    allowed_units = models.ManyToManyField(Unit)


class PropertyValue(NamedUserObjectModel):
    """
    Serves to link any abstract property definition (see "Property" class) to a concrete instance
    of any other model with a concrete value. Intended to be related to other models through many-to-many relations.
    """
    property = models.ForeignKey(Property, on_delete=models.PROTECT)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, default=get_default_unit_pk)
    average = models.FloatField()
    standard_deviation = models.FloatField(blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        name = f'{self.property}: {self.average}'
        if self.standard_deviation:
            name += f' ± {self.standard_deviation}'
        return name
