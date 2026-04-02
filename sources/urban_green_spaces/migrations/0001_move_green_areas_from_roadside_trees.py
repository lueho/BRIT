import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("roadside_trees", "0002_update_content_types"),
    ]

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
                        (
                            "stand",
                            models.CharField(blank=True, max_length=63, null=True),
                        ),
                    ],
                    options={"db_table": "flexibi_hamburg_hamburggreenareas"},
                ),
            ],
        )
    ]
