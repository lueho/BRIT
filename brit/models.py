from django.db import models
from ai_django_core.models import CommonInfo
from django.contrib.auth.models import User, Group


class OwnedObjectModel(CommonInfo):
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
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
