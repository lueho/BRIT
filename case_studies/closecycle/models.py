from django.db.models import ForeignKey, PROTECT
from django.urls import reverse

from maps.models import Region
from utils.models import NamedUserObjectModel


class Showcase(NamedUserObjectModel):
    """
    Showcases are used in the CLOSECYCLE project to demonstrate possibilities or Territorial Biorefinery Hubs.
    """
    region = ForeignKey(Region, on_delete=PROTECT, null=True, blank=True)