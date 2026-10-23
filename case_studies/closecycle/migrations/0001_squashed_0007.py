import django.contrib.gis.db.models.fields
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import utils.object_management.models


class Migration(migrations.Migration):
    replaces = [
        ("closecycle", "0001_initial"),
        ("closecycle", "0002_showcase_approved_at_showcase_approved_by_and_more"),
        ("closecycle", "0003_alter_showcase_publication_status"),
        ("closecycle", "0004_alter_showcase_publication_status"),
        ("closecycle", "0005_showcase_catchment_showcase_sample_series_and_more"),
        ("closecycle", "0006_showcase_geom"),
        ("closecycle", "0007_showcase_theme"),
    ]

    initial = True

    dependencies = [
        ("maps", "0001_squashed_0020"),
        ("materials", "0001_squashed_0032"),
        ("processes", "0001_squashed_0016"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BiogasPlantsSweden",
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
                ("type", models.CharField(blank=True, null=True)),
                ("name", models.CharField(blank=True, null=True)),
                ("county", models.CharField(blank=True, null=True)),
                ("city", models.CharField(blank=True, null=True)),
                ("municipality", models.CharField(blank=True, null=True)),
                ("creation_year", models.CharField(blank=True, null=True)),
                ("size", models.CharField(blank=True, null=True)),
                ("to_upgrade", models.CharField(blank=True, null=True)),
                ("main_type", models.CharField(blank=True, null=True)),
                ("sub_type", models.CharField(blank=True, null=True)),
                ("tech_type", models.CharField(blank=True, null=True)),
            ],
            options={
                "db_table": "closecycle_biogas_plants_sweden",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="Showcase",
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
                    "created_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="Created at",
                    ),
                ),
                (
                    "lastmodified_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="Last modified at",
                    ),
                ),
                (
                    "publication_status",
                    models.CharField(
                        choices=[
                            ("private", "Private"),
                            ("review", "Review"),
                            ("published", "Published"),
                            ("declined", "Declined"),
                            ("archived", "Archived"),
                        ],
                        default="private",
                        max_length=10,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.PointField(
                        blank=True,
                        help_text="Location of the showcase installation. Falls back to the centroid of the region's borders on maps when not set.",
                        null=True,
                        srid=4326,
                    ),
                ),
                (
                    "theme",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("apple_chain", "Apple Chain"),
                            ("greenhouses", "Greenhouses"),
                            ("nature_conservation", "Nature Conservation"),
                            ("tree_cultivation", "Tree Cultivation"),
                            ("municipalities_farms", "Municipalities and Farms"),
                            ("food_crops", "Food Crops"),
                            ("biorefinery_modules", "Biorefinery Modules"),
                        ],
                        db_default="",
                        default="",
                        max_length=32,
                    ),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "catchment",
                    models.ForeignKey(
                        blank=True,
                        help_text="TBN region: the area in which regional stakeholders operate jointly to valorize regional bioresources. Borders may be framed flexibly, e.g. by bioresource catchment areas, product delivery areas or administrative borders.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="showcases",
                        to="maps.catchment",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created by",
                    ),
                ),
                (
                    "lastmodified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_lastmodified",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last modified by",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        default=utils.object_management.models.get_default_owner_pk,
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "region",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="maps.region",
                    ),
                ),
                (
                    "sample_series",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Temporal sample series measured at this showcase, e.g. feedstock monitoring of the processing chain.",
                        related_name="showcases",
                        to="materials.sampleseries",
                        verbose_name="sample series",
                    ),
                ),
                (
                    "samples",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Samples taken at this showcase.",
                        related_name="showcases",
                        to="materials.sample",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ShowcaseMaterial",
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
                    "role",
                    models.CharField(
                        choices=[
                            ("input", "Input (bioresource)"),
                            ("intermediate", "Intermediate"),
                            ("product", "Product (output)"),
                        ],
                        max_length=12,
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0, help_text="Optional order for display purposes."
                    ),
                ),
                (
                    "material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="showcase_materials",
                        to="materials.material",
                    ),
                ),
                (
                    "showcase",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="showcase_materials",
                        to="closecycle.showcase",
                    ),
                ),
            ],
            options={
                "ordering": ["role", "order", "id"],
            },
        ),
        migrations.AddField(
            model_name="showcase",
            name="materials",
            field=models.ManyToManyField(
                blank=True,
                help_text="Bioresources, intermediates and products of the showcase's processing chain, linked via ShowcaseMaterial.",
                related_name="showcases",
                through="closecycle.ShowcaseMaterial",
                to="materials.material",
            ),
        ),
        migrations.CreateModel(
            name="ShowcaseProcess",
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
                    "order",
                    models.PositiveIntegerField(
                        default=0, help_text="Position of the process in the chain."
                    ),
                ),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="showcase_processes",
                        to="processes.process",
                    ),
                ),
                (
                    "showcase",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="showcase_processes",
                        to="closecycle.showcase",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.AddField(
            model_name="showcase",
            name="processes",
            field=models.ManyToManyField(
                blank=True,
                help_text="Technical process units (logistical, pre-, main- and post-treatment) forming the showcase's processing chain, linked via ShowcaseProcess.",
                related_name="showcases",
                through="closecycle.ShowcaseProcess",
                to="processes.process",
            ),
        ),
        migrations.AddIndex(
            model_name="showcasematerial",
            index=models.Index(
                fields=["showcase", "role", "order"],
                name="closecycle__showcas_ce3a67_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="showcasematerial",
            constraint=models.UniqueConstraint(
                fields=("showcase", "material", "role"),
                name="closecycle_showcasematerial_unique_material_role",
            ),
        ),
    ]
