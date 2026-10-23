import django.contrib.gis.db.models.fields
import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
import django.contrib.postgres.operations
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import maps.models
import utils.object_management.models


class Migration(migrations.Migration):
    replaces = [
        ("maps", "0001_initial"),
        (
            "maps",
            "0002_attribute_approved_at_attribute_approved_by_and_more",
        ),
        ("maps", "0003_alter_attribute_publication_status_and_more"),
        ("maps", "0004_region_type_field"),
        ("maps", "0005_alter_attribute_publication_status_and_more"),
        ("maps", "0006_split_categorical_attributes"),
        ("maps", "0007_alter_attribute_options"),
        ("maps", "0008_regionattributevalue_unit"),
        ("maps", "0009_regionproperty"),
        ("maps", "0010_regionattributevalue_regionproperty"),
        ("maps", "0011_alter_regionproperty_options"),
        ("maps", "0012_geodataset_runtime_metadata"),
        ("maps", "0013_alter_geodatasetcolumnpolicy_id_and_more"),
        ("maps", "0014_alter_geodatasetcolumnpolicy_options_and_more"),
        ("maps", "0015_geodatasetcolumnpolicy_is_popup"),
        ("maps", "0016_alter_nutsregion_options_nutsvintage_and_more"),
        ("maps", "0017_catchment_revisions"),
        ("maps", "0018_remove_regionproperty_unit_and_more"),
        ("maps", "0019_region_name_en"),
        ("maps", "0020_delete_attribute"),
    ]

    initial = True

    dependencies = [
        ("bibliography", "0001_squashed_0012"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("properties", "0001_squashed_0010"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GeoPolygon",
            fields=[
                ("fid", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.MultiPolygonField(
                        blank=True, null=True, srid=4326
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Region",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                ("country", models.CharField(max_length=56)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("administrative", "administrative"),
                            ("custom", "custom"),
                            ("nuts", "nuts"),
                            ("lau", "lau"),
                        ],
                        default="custom",
                        max_length=14,
                    ),
                ),
                ("name_en", models.CharField(blank=True, max_length=113, null=True)),
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
                    "borders",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="maps.geopolygon",
                    ),
                ),
                (
                    "composed_of",
                    models.ManyToManyField(
                        blank=True, related_name="composing_regions", to="maps.region"
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
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Catchment",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("administrative", "administrative"),
                            ("custom", "custom"),
                            ("nuts", "nuts"),
                            ("lau", "lau"),
                        ],
                        default="custom",
                        max_length=14,
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
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
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="maps.catchment",
                        verbose_name="parent",
                    ),
                ),
                (
                    "parent_region",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="child_catchments",
                        to="maps.region",
                    ),
                ),
                (
                    "region",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="maps.region",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="CategoricalAttribute",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
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
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="GeoDataset",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                (
                    "preview",
                    models.ImageField(
                        default="generic_map.png", upload_to="maps_geodataset/"
                    ),
                ),
                ("publish", models.BooleanField(default=False)),
                (
                    "model_name",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("HamburgRoadsideTrees", "HamburgRoadsideTrees"),
                            ("HamburgGreenAreas", "HamburgGreenAreas"),
                            ("NantesGreenhouses", "NantesGreenhouses"),
                            ("NutsRegion", "NutsRegion"),
                            ("WasteCollection", "WasteCollection"),
                        ],
                        max_length=56,
                        null=True,
                    ),
                ),
                ("data_object_id", models.PositiveIntegerField(null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
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
                    "data_content_type",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
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
                    "sources",
                    models.ManyToManyField(
                        related_name="geodatasets", to="bibliography.source"
                    ),
                ),
                (
                    "region",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="geodatasets",
                        to="maps.region",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="GeoDatasetRuntimeConfiguration",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "backend_type",
                    models.CharField(
                        choices=[
                            ("legacy_model", "Legacy model"),
                            ("django_model", "Django model"),
                            ("local_relation", "Local relation"),
                        ],
                        default="legacy_model",
                        max_length=32,
                    ),
                ),
                ("runtime_model_name", models.CharField(blank=True, max_length=100)),
                ("schema_name", models.CharField(blank=True, max_length=100)),
                ("relation_name", models.CharField(blank=True, max_length=255)),
                ("geometry_column", models.CharField(blank=True, max_length=100)),
                ("primary_key_column", models.CharField(blank=True, max_length=100)),
                ("label_field", models.CharField(blank=True, max_length=100)),
                ("features_api_basename", models.CharField(blank=True, max_length=100)),
                (
                    "dataset",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runtime_configuration",
                        to="maps.geodataset",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="GeoreferencedCatchment",
            fields=[
                (
                    "catchment_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        to="maps.catchment",
                    ),
                ),
                (
                    "geopolygon_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="maps.geopolygon",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
            bases=("maps.geopolygon", "maps.catchment"),
        ),
        migrations.CreateModel(
            name="GeoreferencedRegion",
            fields=[
                (
                    "region_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        to="maps.region",
                    ),
                ),
                (
                    "geopolygon_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="maps.geopolygon",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
            bases=("maps.geopolygon", "maps.region"),
        ),
        migrations.CreateModel(
            name="NutsRegion",
            fields=[
                (
                    "region_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="maps.region",
                    ),
                ),
                ("nuts_id", models.CharField(blank=True, max_length=5, null=True)),
                ("levl_code", models.IntegerField(blank=True, null=True)),
                ("cntr_code", models.CharField(blank=True, max_length=2, null=True)),
                ("name_latn", models.CharField(blank=True, max_length=70, null=True)),
                ("nuts_name", models.CharField(blank=True, max_length=106, null=True)),
                ("mount_type", models.IntegerField(blank=True, null=True)),
                ("urbn_type", models.IntegerField(blank=True, null=True)),
                ("coast_type", models.IntegerField(blank=True, null=True)),
                (
                    "parent",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="maps.nutsregion",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "abstract": False,
            },
            bases=("maps.region",),
        ),
        migrations.CreateModel(
            name="Location",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                (
                    "geom",
                    django.contrib.gis.db.models.fields.PointField(
                        null=True, srid=4326
                    ),
                ),
                ("address", models.CharField(blank=True, max_length=255, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
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
            ],
            options={
                "verbose_name": "Location",
            },
        ),
        migrations.CreateModel(
            name="MapConfiguration",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                (
                    "adjust_bounds_to_layer",
                    models.CharField(
                        choices=[
                            ("region", "Region"),
                            ("catchment", "Catchment"),
                            ("features", "Features"),
                        ],
                        default="region",
                        help_text="Layer to which the map bounds should be adjusted.",
                        max_length=50,
                    ),
                ),
                ("apply_filter_to_features", models.BooleanField(default=False)),
                ("load_features_layer_summary", models.BooleanField(default=False)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
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
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="geodataset",
            name="map_configuration",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="geodatasets",
                to="maps.mapconfiguration",
            ),
        ),
        migrations.CreateModel(
            name="MapLayerConfiguration",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                (
                    "layer_type",
                    models.CharField(
                        choices=[
                            ("region", "Region"),
                            ("catchment", "Catchment"),
                            ("features", "Features"),
                        ],
                        help_text="Type of the layer (region, catchment, feature).",
                        max_length=50,
                    ),
                ),
                (
                    "load_layer",
                    models.BooleanField(
                        default=True,
                        help_text="If False, the dataset will not be loaded initially to avoid long loading times.",
                    ),
                ),
                (
                    "feature_id",
                    models.CharField(
                        blank=True,
                        help_text="Unique identifier for the feature if fixed.",
                        max_length=255,
                    ),
                ),
                (
                    "api_basename",
                    models.CharField(
                        blank=True,
                        help_text="Base name for API used to derive endpoint urls for geometries, details and summaries",
                        max_length=255,
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
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
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="mapconfiguration",
            name="layers",
            field=models.ManyToManyField(
                help_text="Layers associated with this map configuration.",
                related_name="map_configurations",
                to="maps.maplayerconfiguration",
            ),
        ),
        migrations.CreateModel(
            name="MapLayerStyle",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                (
                    "stroke",
                    models.BooleanField(
                        default=True,
                        help_text="If False, the layer will not have a stroke.",
                    ),
                ),
                (
                    "color",
                    models.CharField(
                        default="#3388ff",
                        help_text="Stroke color for the layer in hexadecimal format.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a valid hex color code.",
                                regex="^#(?:[0-9a-fA-F]{3}){1,2}$",
                            )
                        ],
                    ),
                ),
                (
                    "weight",
                    models.PositiveIntegerField(
                        default=3, help_text="Stroke width in pixels."
                    ),
                ),
                (
                    "opacity",
                    models.FloatField(
                        default=1.0,
                        help_text="Stroke opacity, between 0 and 1.",
                        validators=[
                            django.core.validators.MinValueValidator(0.0),
                            django.core.validators.MaxValueValidator(1.0),
                        ],
                    ),
                ),
                (
                    "fill",
                    models.BooleanField(
                        default=True,
                        help_text="If False, the layer will not have a fill.",
                    ),
                ),
                (
                    "fill_color",
                    models.CharField(
                        blank=True,
                        help_text="Fill color for the layer in hexadecimal format.",
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a valid hex color code.",
                                regex="^#(?:[0-9a-fA-F]{3}){1,2}$",
                            )
                        ],
                    ),
                ),
                (
                    "fill_opacity",
                    models.FloatField(
                        default=0.2,
                        help_text="Fill opacity, between 0 and 1.",
                        validators=[
                            django.core.validators.MinValueValidator(0.0),
                            django.core.validators.MaxValueValidator(1.0),
                        ],
                    ),
                ),
                (
                    "dash_array",
                    models.CharField(
                        blank=True,
                        help_text="Define the stroke dash pattern, e.g., '5, 10'.",
                        max_length=50,
                    ),
                ),
                (
                    "dash_offset",
                    models.CharField(
                        blank=True,
                        help_text="Define the stroke dash offset.",
                        max_length=50,
                    ),
                ),
                (
                    "line_cap",
                    models.CharField(
                        choices=[
                            ("butt", "Butt"),
                            ("round", "Round"),
                            ("square", "Square"),
                        ],
                        default="round",
                        help_text="Shape to be used at the end of the stroke.",
                        max_length=10,
                    ),
                ),
                (
                    "line_join",
                    models.CharField(
                        choices=[
                            ("miter", "Miter"),
                            ("round", "Round"),
                            ("bevel", "Bevel"),
                        ],
                        default="round",
                        help_text="Shape to be used at the joints between segments.",
                        max_length=10,
                    ),
                ),
                (
                    "fill_rule",
                    models.CharField(
                        choices=[("evenodd", "Even-Odd"), ("nonzero", "Non-Zero")],
                        default="evenodd",
                        help_text="Rule used to determine if a point is inside the path.",
                        max_length=10,
                    ),
                ),
                (
                    "class_name",
                    models.CharField(
                        blank=True,
                        help_text="CSS class name(s) to add to the layer for additional styling.",
                        max_length=50,
                    ),
                ),
                (
                    "radius",
                    models.FloatField(
                        default=10.0, help_text="Radius of the circle marker in pixels."
                    ),
                ),
                (
                    "bubbling_mouse_events",
                    models.BooleanField(
                        default=True,
                        help_text="When true, a mouse event on this path will trigger the same event on the map.",
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
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
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="maplayerconfiguration",
            name="style",
            field=models.ForeignKey(
                help_text="Styling information for the layer.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="layer_configurations",
                to="maps.maplayerstyle",
            ),
        ),
        migrations.CreateModel(
            name="ModelMapConfiguration",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "model_name",
                    models.CharField(
                        choices=maps.models.get_model_choices,
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "map_config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="model_map_configurations",
                        to="maps.mapconfiguration",
                    ),
                ),
            ],
            options={
                "ordering": ["model_name"],
            },
        ),
        migrations.CreateModel(
            name="NutsVintage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("year", models.PositiveSmallIntegerField(unique=True)),
                ("is_current", models.BooleanField(default=False)),
                ("source_release", models.CharField(blank=True, max_length=100)),
            ],
            options={
                "ordering": ["-year"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_current", True)),
                        fields=("is_current",),
                        name="unique_current_nuts_vintage",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="RegionAttributeTextValue",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                ("date", models.DateField(blank=True, null=True)),
                ("value", models.CharField(max_length=511)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
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
                    "categorical_attribute",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="maps.categoricalattribute",
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
                        on_delete=django.db.models.deletion.PROTECT, to="maps.region"
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="RegionProperty",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "allowed_units",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Units that are acceptable for this property.",
                        to="properties.unit",
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
            ],
            options={
                "abstract": False,
                "verbose_name_plural": "region properties",
            },
        ),
        migrations.CreateModel(
            name="RegionAttributeValue",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                ("date", models.DateField(blank=True, null=True)),
                ("value", models.FloatField(default=0.0)),
                (
                    "standard_deviation",
                    models.FloatField(blank=True, default=0.0, null=True),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
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
                        on_delete=django.db.models.deletion.PROTECT, to="maps.region"
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="properties.unit",
                    ),
                ),
                (
                    "property",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="maps.regionproperty",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="GeoDatasetColumnPolicy",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("column_name", models.CharField(max_length=100)),
                ("display_label", models.CharField(blank=True, max_length=100)),
                ("is_visible", models.BooleanField(default=False)),
                ("is_filterable", models.BooleanField(default=False)),
                ("is_searchable", models.BooleanField(default=False)),
                ("is_exportable", models.BooleanField(default=False)),
                ("is_orderable", models.BooleanField(default=False)),
                ("is_popup", models.BooleanField(default=False)),
                (
                    "dataset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="column_policies",
                        to="maps.geodataset",
                    ),
                ),
            ],
            options={
                "ordering": ["column_name"],
                "verbose_name_plural": "geo dataset column policies",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("dataset", "column_name"),
                        name="maps_geodatasetcolumnpolicy_dataset_column_unique",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="GeoreferencedNutsRegion",
            fields=[
                (
                    "nutsregion_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        to="maps.nutsregion",
                    ),
                ),
                (
                    "geopolygon_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="maps.geopolygon",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
            bases=("maps.geopolygon", "maps.nutsregion"),
        ),
        migrations.AddField(
            model_name="nutsregion",
            name="version",
            field=models.ForeignKey(
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="regions",
                to="maps.nutsvintage",
            ),
        ),
        migrations.CreateModel(
            name="LauRegion",
            fields=[
                (
                    "region_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="maps.region",
                    ),
                ),
                ("cntr_code", models.CharField(blank=True, max_length=2, null=True)),
                ("lau_id", models.CharField(blank=True, max_length=13, null=True)),
                ("lau_name", models.CharField(blank=True, max_length=113, null=True)),
                ("year", models.IntegerField(blank=True, null=True)),
                (
                    "nuts_parent",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lau_children",
                        to="maps.nutsregion",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
            },
            bases=("maps.region",),
        ),
        django.contrib.postgres.operations.BtreeGistExtension(),
        migrations.CreateModel(
            name="CatchmentRevision",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                ("effective_from", models.DateField(blank=True, null=True)),
                ("effective_to", models.DateField(blank=True, null=True)),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.MultiPolygonField(srid=4326),
                ),
                ("geom_hash", models.CharField(editable=False, max_length=64)),
                (
                    "change_reason",
                    models.CharField(
                        choices=[
                            ("initial", "Initial snapshot"),
                            ("addition", "Territory added"),
                            ("removal", "Territory removed"),
                            ("transfer", "Territory transferred"),
                            ("split", "Catchment split"),
                            ("merge", "Catchments merged"),
                            ("administrative", "Administrative boundary revision"),
                            ("correction", "Data correction"),
                        ],
                        default="initial",
                        max_length=20,
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
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="revisions",
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
                    "predecessors",
                    models.ManyToManyField(
                        blank=True,
                        related_name="successors",
                        to="maps.catchmentrevision",
                    ),
                ),
                (
                    "sources",
                    models.ManyToManyField(blank=True, to="bibliography.source"),
                ),
                (
                    "members",
                    models.ManyToManyField(
                        blank=True, related_name="catchment_revisions", to="maps.region"
                    ),
                ),
            ],
            options={
                "ordering": ["catchment_id", "effective_from", "id"],
                "abstract": False,
                "indexes": [
                    models.Index(
                        fields=["catchment", "effective_from", "effective_to"],
                        name="maps_catchm_catchme_ea3be9_idx",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("effective_from__isnull", True),
                            ("effective_to__isnull", True),
                            ("effective_from__lt", models.F("effective_to")),
                            _connector="OR",
                        ),
                        name="catchment_revision_effective_period_valid",
                    ),
                    django.contrib.postgres.constraints.ExclusionConstraint(
                        condition=models.Q(
                            ("publication_status__in", ("published", "archived"))
                        ),
                        expressions=[
                            ("catchment", "="),
                            (
                                models.Func(
                                    models.F("effective_from"),
                                    models.F("effective_to"),
                                    function="DATERANGE",
                                    output_field=django.contrib.postgres.fields.ranges.DateRangeField(),
                                ),
                                "&&",
                            ),
                        ],
                        name="catchment_revision_no_public_period_overlap",
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="nutsregion",
            constraint=models.UniqueConstraint(
                fields=("nuts_id", "version"), name="unique_nuts_id_per_version"
            ),
        ),
    ]
