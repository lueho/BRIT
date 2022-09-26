from ai_django_core.models import CommonInfo
from django.contrib.auth.models import User, Group
from django.db import models
from django.urls import reverse, exceptions

from users.models import get_default_owner


class ReadableQueryset(models.QuerySet):

    def readable(self, user):
        qs = self.filter(visible_to_groups__in=Group.objects.filter(name='public'))
        if user.is_authenticated:
            qs = qs.union(self.filter(visible_to_groups__in=user.groups.all()))
            qs = qs.union(self.filter(owner=user))
        return qs


class AccessManager(models.Manager):

    def get_queryset(self):
        return ReadableQueryset(self.model, using=self._db)

    def readable(self, user):
        return self.get_queryset().readable(user)


def get_default_owner_pk():
    return get_default_owner().pk


class OwnedObjectModel(CommonInfo):
    owner = models.ForeignKey(User, on_delete=models.PROTECT, default=get_default_owner_pk)
    visible_to_groups = models.ManyToManyField(Group)

    objects = AccessManager()

    class Meta:
        abstract = True


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


class NamedUserObjectModel(CRUDUrlsMixin, OwnedObjectModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name
