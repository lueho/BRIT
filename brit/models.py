from ai_django_core.models import CommonInfo
from django.contrib.auth.models import User, Group
from django.db import models


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


class NamedUserObjectModel(OwnedObjectModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name
