from django.db import models

from brit.models import NamedUserObjectModel
from materials.models import Material


class Collector(NamedUserObjectModel):
    pass


class CollectionSystem(NamedUserObjectModel):
    pass


class WasteStreamCategory(NamedUserObjectModel):
    pass


class WasteStreamAllowed(NamedUserObjectModel):
    category = models.ForeignKey(WasteStreamCategory, on_delete=models.PROTECT)
    materials = models.ManyToManyField(Material)
