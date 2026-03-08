import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [("flexibi_hamburg", "0002_hamburgroadsidetrees_flexibi_ham_baumid_4f523a_idx_and_more")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="HamburgGreenAreas",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "geom",
                            django.contrib.gis.db.models.fields.MultiPolygonField(
                                blank=True, null=True, srid=4326
                            ),
                        ),
                        (
                            "quelle_daten",
                            models.CharField(blank=True, max_length=200, null=True),
                        ),
                        (
                            "identnummer",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        ("dgpkey", models.IntegerField(blank=True, null=True)),
                        (
                            "anlagenname",
                            models.CharField(blank=True, max_length=200, null=True),
                        ),
                        (
                            "belegenheit",
                            models.CharField(blank=True, max_length=200, null=True),
                        ),
                        (
                            "eigentum",
                            models.CharField(blank=True, max_length=200, null=True),
                        ),
                        ("bezirksnummer", models.IntegerField(blank=True, null=True)),
                        ("ortsteil", models.IntegerField(blank=True, null=True)),
                        ("flaeche_qm", models.FloatField(blank=True, null=True)),
                        ("flaeche_ha", models.FloatField(blank=True, null=True)),
                        (
                            "gruenart",
                            models.CharField(blank=True, max_length=200, null=True),
                        ),
                        ("nutzcode", models.IntegerField(blank=True, null=True)),
                        ("stand", models.CharField(blank=True, max_length=63, null=True)),
                    ],
                    options={"db_table": "flexibi_hamburg_hamburggreenareas"},
                ),
                migrations.CreateModel(
                    name="HamburgRoadsideTrees",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "geom",
                            django.contrib.gis.db.models.fields.PointField(
                                blank=True, null=True, srid=4326
                            ),
                        ),
                        ("baumid", models.IntegerField(blank=True, null=True)),
                        (
                            "gattung",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        (
                            "gattung_latein",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        (
                            "gattung_deutsch",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        ("art", models.CharField(blank=True, max_length=63, null=True)),
                        (
                            "art_latein",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        (
                            "art_deutsch",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        (
                            "sorte_latein",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        (
                            "sorte_deutsch",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        ("pflanzjahr", models.IntegerField(blank=True, null=True)),
                        (
                            "pflanzjahr_portal",
                            models.IntegerField(blank=True, null=True),
                        ),
                        (
                            "kronendurchmesser",
                            models.IntegerField(blank=True, null=True),
                        ),
                        ("stammumfang", models.IntegerField(blank=True, null=True)),
                        (
                            "strasse",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        (
                            "hausnummer",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        (
                            "ortsteil_nr",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        (
                            "stadtteil",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                        (
                            "bezirk",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                    ],
                    options={
                        "db_table": "flexibi_hamburg_hamburgroadsidetrees",
                        "verbose_name": "Hamburg Roadside Tree",
                        "verbose_name_plural": "Hamburg Roadside Trees",
                        "ordering": ["baumid"],
                        "indexes": [
                            models.Index(
                                fields=["baumid"],
                                name="flexibi_ham_baumid_4f523a_idx",
                            ),
                            models.Index(
                                fields=["gattung_deutsch"],
                                name="flexibi_ham_gattung_7a939c_idx",
                            ),
                            models.Index(
                                fields=["pflanzjahr"],
                                name="flexibi_ham_pflanzj_0ac23c_idx",
                            ),
                            models.Index(
                                fields=["stammumfang"],
                                name="flexibi_ham_stammum_f1ca86_idx",
                            ),
                            models.Index(
                                fields=["bezirk"],
                                name="flexibi_ham_bezirk_e41bc8_idx",
                            ),
                        ],
                    },
                ),
            ],
        )
    ]
