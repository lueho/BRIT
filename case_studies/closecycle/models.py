from django.contrib.gis.db.models import PointField
from django.db.models import CharField, ForeignKey, Model, PROTECT

from maps.models import Region
from utils.models import NamedUserCreatedObject


class Showcase(NamedUserCreatedObject):
    """
    Showcases are used in the CLOSECYCLE project to demonstrate possibilities or Territorial Biorefinery Hubs.
    """
    region = ForeignKey(Region, on_delete=PROTECT, null=True, blank=True)


class BiogasPlantsSweden(Model):
    geom = PointField(blank=True, null=True)
    type = CharField(blank=True, null=True)
    name = CharField(blank=True, null=True)
    county = CharField(blank=True, null=True)
    city = CharField(blank=True, null=True)
    municipality = CharField(blank=True, null=True)
    creation_year = CharField(blank=True, null=True)
    size = CharField(blank=True, null=True)
    to_upgrade = CharField(blank=True, null=True)
    main_type = CharField(blank=True, null=True)
    sub_type = CharField(blank=True, null=True)
    tech_type = CharField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'closecycle_biogas_plants_sweden'
