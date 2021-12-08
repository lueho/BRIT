from ai_django_core.models import CommonInfo
from django.contrib.auth.models import User, Group
from django.db import models
from django.urls import reverse


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


class OwnedObjectModel(CommonInfo):
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
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
        return reverse(f'{cls.__name__.lower()}-list')

    @classmethod
    @property
    def modal_list_url(cls):
        return reverse(f'{cls.__name__.lower()}-list-modal')

    @classmethod
    @property
    def options_list_url(cls):
        return reverse(f'{cls.__name__.lower()}-options')

    @classmethod
    @property
    def create_url(cls):
        return reverse(f'{cls.__name__.lower()}-create')

    @classmethod
    @property
    def modal_create_url(cls):
        return reverse(f'{cls.__name__.lower()}-create-modal')

    @property
    def detail_url(self):
        return reverse(f'{self.__class__.__name__.lower()}-detail', kwargs={'pk': self.pk})

    @property
    def modal_detail_url(self):
        return reverse(f'{self.__class__.__name__.lower()}-detail-modal', kwargs={'pk': self.pk})

    def get_absolute_url(self):
        return reverse(f'{self.__class__.__name__.lower()}-detail', kwargs={'pk': self.pk})

    @property
    def update_url(self):
        return reverse(f'{self.__class__.__name__.lower()}-update', kwargs={'pk': self.pk})

    @property
    def modal_update_url(self):
        return reverse(f'{self.__class__.__name__.lower()}-update-modal', kwargs={'pk': self.pk})

    @property
    def delete_url(self):
        return reverse(f'{self.__class__.__name__.lower()}-delete', kwargs={'pk': self.pk})

    @property
    def modal_delete_url(self):
        return reverse(f'{self.__class__.__name__.lower()}-delete-modal', kwargs={'pk': self.pk})


class NamedUserObjectModel(CRUDUrlsMixin, OwnedObjectModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name
