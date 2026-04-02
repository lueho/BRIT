from django.contrib.gis.db.models import PointField
from django.db import models

from sources.urban_green_spaces.models import HamburgGreenAreas


class HamburgRoadsideTrees(models.Model):
    geom = PointField(blank=True, null=True)
    baumid = models.IntegerField(blank=True, null=True)
    gattung = models.CharField(max_length=63, blank=True, null=True)
    gattung_latein = models.CharField(max_length=63, blank=True, null=True)
    gattung_deutsch = models.CharField(max_length=63, blank=True, null=True)
    art = models.CharField(max_length=63, blank=True, null=True)
    art_latein = models.CharField(max_length=63, blank=True, null=True)
    art_deutsch = models.CharField(max_length=63, blank=True, null=True)
    sorte_latein = models.CharField(max_length=63, blank=True, null=True)
    sorte_deutsch = models.CharField(max_length=63, blank=True, null=True)
    pflanzjahr = models.IntegerField(blank=True, null=True)
    pflanzjahr_portal = models.IntegerField(blank=True, null=True)
    kronendurchmesser = models.IntegerField(blank=True, null=True)
    stammumfang = models.IntegerField(blank=True, null=True)
    strasse = models.CharField(max_length=63, blank=True, null=True)
    hausnummer = models.CharField(max_length=63, blank=True, null=True)
    ortsteil_nr = models.CharField(max_length=63, blank=True, null=True)
    stadtteil = models.CharField(max_length=63, blank=True, null=True)
    bezirk = models.CharField(max_length=63, blank=True, null=True)

    class Meta:
        db_table = "flexibi_hamburg_hamburgroadsidetrees"
        verbose_name = "Hamburg Roadside Tree"
        verbose_name_plural = "Hamburg Roadside Trees"
        ordering = ["baumid"]
        indexes = [
            models.Index(fields=["baumid"], name="flexibi_ham_baumid_4f523a_idx"),
            models.Index(
                fields=["gattung_deutsch"], name="flexibi_ham_gattung_7a939c_idx"
            ),
            models.Index(fields=["pflanzjahr"], name="flexibi_ham_pflanzj_0ac23c_idx"),
            models.Index(fields=["stammumfang"], name="flexibi_ham_stammum_f1ca86_idx"),
            models.Index(fields=["bezirk"], name="flexibi_ham_bezirk_e41bc8_idx"),
        ]


__all__ = ["HamburgGreenAreas", "HamburgRoadsideTrees"]
