from decimal import Decimal

import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import utils.object_management.models
import utils.properties.models


class Migration(migrations.Migration):
    replaces = [
        ("materials", "0001_initial"),
        ("materials", "0002_analyticalmethod_approved_at_and_more"),
        ("materials", "0003_alter_analyticalmethod_publication_status_and_more"),
        ("materials", "0004_alter_materialproperty_options_and_more"),
        ("materials", "0005_alter_analyticalmethod_publication_status_and_more"),
        ("materials", "0005_remove_materialpropertyvalue_name_description"),
        ("materials", "0006_materialpropertyvalue_unit"),
        ("materials", "0007_merge_20260217_0951"),
        ("materials", "0008_basematerial_comparable_component"),
        ("materials", "0009_materialproperty_comparable_property"),
        ("materials", "0010_materialpropertyvalue_basis_component"),
        ("materials", "0011_make_standard_deviation_optional"),
        ("materials", "0012_alter_analyticalmethod_sources_and_more"),
        ("materials", "0013_materialpropertyvalue_sample"),
        ("materials", "0014_remove_sample_properties"),
        ("materials", "0015_alter_materialcategory_options_and_more"),
        ("materials", "0016_delete_weightshare"),
        ("materials", "0017_unique_published_basematerial_name_type"),
        ("materials", "0018_materialproperty_configure_allowed_units"),
        ("materials", "0019_materialproperty_unit_optional"),
        ("materials", "0020_sample_image_metadata"),
        ("materials", "0021_sample_time_labels"),
        ("materials", "0022_sample_datetime_precision"),
        ("materials", "0023_remove_component_kind"),
        ("materials", "0024_sampleexternalrecord_and_more"),
        ("materials", "0025_alter_basematerial_unique_together"),
        ("materials", "0026_basematerial_is_aggregate"),
        ("materials", "0027_materialcomponentgroup_is_compositional"),
        ("materials", "0028_remove_materialproperty_unit"),
        ("materials", "0028_samplegroup_sample_sample_groups"),
        ("materials", "0029_merge_20260922_1559"),
        ("materials", "0030_product_material_category"),
        ("materials", "0031_sample_region_sample_site"),
        ("materials", "0032_sampleauthor_sample_authors_and_more"),
    ]

    initial = True

    dependencies = [
        ("bibliography", "0001_squashed_0012"),
        ("distributions", "0001_initial"),
        ("maps", "0019_region_name_en"),
        ("properties", "0001_squashed_0010"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalyticalMethod",
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
                    "ontology_uri",
                    models.URLField(
                        blank=True,
                        help_text="External ontology URI (e.g., CHMO term) for this analytical method.",
                        null=True,
                    ),
                ),
                (
                    "technique",
                    models.CharField(
                        blank=True,
                        help_text="Analytical technique (e.g., ICP-OES, Gravimetry).",
                        max_length=100,
                    ),
                ),
                (
                    "standard",
                    models.CharField(
                        blank=True,
                        help_text="Standard or protocol (e.g., DIN EN 15936).",
                        max_length=100,
                    ),
                ),
                (
                    "instrument_type",
                    models.CharField(
                        blank=True,
                        help_text="Type of instrument used (local override if not fetched externally).",
                        max_length=100,
                    ),
                ),
                (
                    "lower_detection_limit",
                    models.CharField(
                        blank=True,
                        help_text="Lower detection limit (e.g., '0.5 mg/kg').",
                        max_length=50,
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Analytical Method",
                "verbose_name_plural": "Analytical Methods",
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="BaseMaterial",
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
                ("type", models.CharField(default="material", max_length=127)),
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "abbreviation",
                    models.CharField(
                        blank=True,
                        help_text="Short abbreviation or acronym for this material/component.",
                        max_length=50,
                    ),
                ),
                (
                    "basis_component",
                    models.ForeignKey(
                        blank=True,
                        help_text="Basis component for this component (e.g. Dry Matter). Only used for components.",
                        limit_choices_to={"type": "component"},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="derived_components",
                        to="materials.basematerial",
                    ),
                ),
                (
                    "comparable_component",
                    models.ForeignKey(
                        blank=True,
                        help_text="Canonical component this raw term should be compared as. Only used for components.",
                        limit_choices_to={"type": "component"},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comparable_variants",
                        to="materials.basematerial",
                    ),
                ),
                (
                    "is_aggregate",
                    models.BooleanField(
                        default=False,
                        help_text="Component totals its sibling components within a component group (e.g. 'Total (with halides)'). Aggregates are excluded from normalized compositions. Only used for components.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Material",
                "indexes": [],
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("name"),
                        models.F("type"),
                        condition=models.Q(("publication_status", "published")),
                        name="materials_basematerial_unique_published_name_type",
                    )
                ],
                "unique_together": {("name", "owner", "type")},
            },
        ),
        migrations.CreateModel(
            name="MaterialCategory",
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
                "indexes": [],
                "constraints": [],
                "verbose_name_plural": "material categories",
            },
        ),
        migrations.CreateModel(
            name="MaterialComponentGroup",
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("is_compositional", models.BooleanField(default=True)),
            ],
            options={
                "unique_together": {("name", "owner")},
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="MaterialPropertyGroup",
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
                "unique_together": {("name", "owner")},
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="SampleGroup",
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
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("study", "Study"),
                            ("experiment", "Experiment"),
                            ("sampling_campaign", "Sampling campaign"),
                            ("analysis", "Analysis"),
                            ("other", "Other"),
                        ],
                        default="study",
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
                "verbose_name_plural": "sample groups",
                "ordering": ["name", "id"],
                "abstract": False,
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="Material",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("materials.basematerial",),
        ),
        migrations.CreateModel(
            name="MaterialComponent",
            fields=[],
            options={
                "verbose_name": "component",
                "ordering": ["name"],
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("materials.basematerial",),
        ),
        migrations.CreateModel(
            name="MaterialProperty",
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("abbreviation", models.CharField(blank=True, max_length=50)),
                (
                    "aggregation_kind",
                    models.CharField(
                        choices=[
                            ("mass_related", "Mass-related"),
                            ("non_mass_related", "Non mass-related"),
                        ],
                        default="non_mass_related",
                        max_length=30,
                    ),
                ),
                (
                    "default_basis_component",
                    models.ForeignKey(
                        blank=True,
                        help_text="Mass basis component used to normalize this property (e.g. Dry Matter).",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="default_basis_properties",
                        to="materials.materialcomponent",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        blank=True,
                        help_text="Aggregation domain used to avoid double-counting overlapping measurements.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="properties",
                        to="materials.materialpropertygroup",
                    ),
                ),
                (
                    "comparable_property",
                    models.ForeignKey(
                        blank=True,
                        help_text="Canonical property this raw term should be compared as.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comparable_variants",
                        to="materials.materialproperty",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "indexes": [],
                "constraints": [],
                "verbose_name_plural": "material properties",
            },
        ),
        migrations.CreateModel(
            name="SampleSeries",
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
                    "image",
                    models.ImageField(
                        blank=True, null=True, upload_to="materials_sampleseries/"
                    ),
                ),
                ("publish", models.BooleanField(default=False)),
                ("standard", models.BooleanField(default=True)),
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
                    "material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sample_series",
                        to="materials.material",
                    ),
                ),
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "image_alt_text",
                    models.CharField(
                        blank=True,
                        help_text="Accessible description of the image.",
                        max_length=255,
                        verbose_name="image alt text",
                    ),
                ),
                (
                    "image_caption",
                    models.CharField(
                        blank=True,
                        help_text="Caption displayed with the image.",
                        max_length=255,
                    ),
                ),
                (
                    "image_rights_notice",
                    models.CharField(
                        blank=True,
                        help_text="Copyright, license, or attribution notice for the image.",
                        max_length=255,
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
                "indexes": [],
                "constraints": [],
                "verbose_name_plural": "sample series",
            },
        ),
        migrations.CreateModel(
            name="Sample",
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
                    "image",
                    models.ImageField(
                        blank=True, null=True, upload_to="materials_sample/"
                    ),
                ),
                (
                    "datetime",
                    models.DateTimeField(
                        blank=True,
                        help_text="When the sample was taken, with its known precision recorded separately.",
                        null=True,
                        verbose_name="sampling date/time",
                    ),
                ),
                (
                    "location",
                    models.CharField(
                        blank=True,
                        help_text="Name of town, address or coordinates",
                        max_length=511,
                        null=True,
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
                    "timestep",
                    models.ForeignKey(
                        blank=True,
                        help_text="If the sample represents a specific time step in a series, select it here.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="samples",
                        to="distributions.timestep",
                    ),
                ),
                (
                    "series",
                    models.ForeignKey(
                        blank=True,
                        help_text="Temporal series for samples of the same material at defined timesteps.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="samples",
                        to="materials.sampleseries",
                    ),
                ),
                (
                    "material",
                    models.ForeignKey(
                        help_text='If no option fits, please choose "Other" and specify the material in the description.',
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="samples",
                        to="materials.material",
                    ),
                ),
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "analysis_date",
                    models.DateTimeField(
                        blank=True,
                        help_text="When the laboratory analysis was performed. Choose 00:00 if the time is unknown.",
                        null=True,
                        verbose_name="analysis date/time",
                    ),
                ),
                (
                    "analysis_laboratory",
                    models.CharField(
                        blank=True,
                        help_text="Laboratory where the analysis was performed.",
                        max_length=255,
                    ),
                ),
                (
                    "analysis_objective",
                    models.TextField(
                        blank=True, help_text="Objective or purpose of the analysis."
                    ),
                ),
                (
                    "lab_accreditation",
                    models.CharField(
                        blank=True,
                        help_text="Laboratory accreditation information.",
                        max_length=255,
                    ),
                ),
                (
                    "standalone",
                    models.BooleanField(
                        default=False,
                        help_text="True if this sample is not part of a temporal sample series. Standalone samples may still belong to sample groups.",
                    ),
                ),
                (
                    "image_alt_text",
                    models.CharField(
                        blank=True,
                        help_text="Accessible description of the image.",
                        max_length=255,
                        verbose_name="image alt text",
                    ),
                ),
                (
                    "image_caption",
                    models.CharField(
                        blank=True,
                        help_text="Caption displayed with the image.",
                        max_length=255,
                    ),
                ),
                (
                    "image_rights_notice",
                    models.CharField(
                        blank=True,
                        help_text="Copyright, license, or attribution notice for the image.",
                        max_length=255,
                    ),
                ),
                (
                    "datetime_precision",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("year", "Year"),
                            ("date", "Date"),
                            ("time", "Date and time"),
                        ],
                        default="",
                        help_text="Known sampling date precision, interpreted in the default timezone. Blank preserves legacy behavior: midnight is displayed as a date.",
                        max_length=8,
                    ),
                ),
                (
                    "region",
                    models.ForeignKey(
                        blank=True,
                        help_text="Geographic region the sample was taken in. The free-text location field and the site field can hold finer detail.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="samples",
                        to="maps.region",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        blank=True,
                        help_text="Precise sampling site (address or coordinates) when known.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="samples",
                        to="maps.location",
                        verbose_name="sampling site",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
                "abstract": False,
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="ComponentMeasurement",
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
                (
                    "average",
                    models.DecimalField(
                        decimal_places=10, default=Decimal("0.0"), max_digits=20
                    ),
                ),
                (
                    "standard_deviation",
                    models.DecimalField(
                        blank=True, decimal_places=10, max_digits=20, null=True
                    ),
                ),
                (
                    "sample_size",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Number of samples/replicates (n) used for the measurement.",
                        null=True,
                    ),
                ),
                (
                    "comment",
                    models.TextField(
                        blank=True,
                        help_text="Additional comments about the measurement.",
                    ),
                ),
                (
                    "analytical_method",
                    models.ForeignKey(
                        blank=True,
                        help_text="Analytical method used for this measurement.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="materials.analyticalmethod",
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
                    "basis_component",
                    models.ForeignKey(
                        blank=True,
                        help_text="Basis component for the measurement (e.g. Dry Matter).",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="basis_component_measurements",
                        to="materials.materialcomponent",
                    ),
                ),
                (
                    "component",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="component_measurements",
                        to="materials.materialcomponent",
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
                    "group",
                    models.ForeignKey(
                        help_text="Grouping domain for the measurement (e.g. chemical elements).",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="component_measurements",
                        to="materials.materialcomponentgroup",
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
                    "sample",
                    models.ForeignKey(
                        help_text="The sample these measurements belong to.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="component_measurements",
                        to="materials.sample",
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        default=utils.properties.models.get_default_unit_pk,
                        help_text="Unit for the measured value (e.g. %, g/kg).",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="properties.unit",
                    ),
                ),
                ("analysis_date", models.DateTimeField(blank=True, null=True)),
                ("analysis_laboratory", models.CharField(blank=True, max_length=255)),
                (
                    "detection_limit",
                    models.DecimalField(
                        blank=True, decimal_places=15, max_digits=30, null=True
                    ),
                ),
                ("raw_detection_limit", models.CharField(blank=True, max_length=255)),
                ("raw_value", models.CharField(blank=True, max_length=255)),
                (
                    "value_qualifier",
                    models.CharField(
                        choices=[
                            ("exact", "Exact"),
                            ("less_than", "Less than"),
                            ("greater_than", "Greater than"),
                            ("below_detection_limit", "Below detection limit"),
                            ("range", "Range"),
                            ("estimated", "Estimated"),
                        ],
                        default="exact",
                        max_length=32,
                    ),
                ),
            ],
            options={
                "ordering": ["component__name", "id"],
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="Composition",
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
                ("order", models.IntegerField(default=90)),
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
                    "group",
                    models.ForeignKey(
                        help_text="The group of components that this composition is part of. Typically determined by type of analysis.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="compositions",
                        to="materials.materialcomponentgroup",
                    ),
                ),
                (
                    "sample",
                    models.ForeignKey(
                        help_text="The sample that this composition is part of.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compositions",
                        to="materials.sample",
                    ),
                ),
                (
                    "fractions_of",
                    models.ForeignKey(
                        blank=True,
                        help_text="The component that the weight fractions of this composition are fractions of. Must be a component that is already defined.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="materials.materialcomponent",
                    ),
                ),
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["order"],
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="MaterialPropertyValue",
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
                ("average", models.DecimalField(decimal_places=10, max_digits=20)),
                (
                    "standard_deviation",
                    models.DecimalField(
                        blank=True, decimal_places=10, max_digits=20, null=True
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
                    "property",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="materials.materialproperty",
                    ),
                ),
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "analytical_method",
                    models.ForeignKey(
                        blank=True,
                        help_text="Analytical method used for this measurement.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="materials.analyticalmethod",
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        default=utils.properties.models.get_default_unit_pk,
                        help_text="Unit for the measured value.",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="properties.unit",
                    ),
                ),
                (
                    "basis_component",
                    models.ForeignKey(
                        blank=True,
                        help_text="Basis component for the property value (e.g. Dry Matter).",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="basis_property_values",
                        to="materials.materialcomponent",
                    ),
                ),
                (
                    "sample",
                    models.ForeignKey(
                        blank=True,
                        help_text="The sample this measurement belongs to.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="property_values",
                        to="materials.sample",
                    ),
                ),
                ("analysis_date", models.DateTimeField(blank=True, null=True)),
                ("analysis_laboratory", models.CharField(blank=True, max_length=255)),
                (
                    "comment",
                    models.TextField(
                        blank=True,
                        help_text="Additional comments about the measurement.",
                    ),
                ),
                (
                    "detection_limit",
                    models.DecimalField(
                        blank=True, decimal_places=15, max_digits=30, null=True
                    ),
                ),
                ("raw_detection_limit", models.CharField(blank=True, max_length=255)),
                ("raw_value", models.CharField(blank=True, max_length=255)),
                (
                    "value_qualifier",
                    models.CharField(
                        choices=[
                            ("exact", "Exact"),
                            ("less_than", "Less than"),
                            ("greater_than", "Greater than"),
                            ("below_detection_limit", "Below detection limit"),
                            ("range", "Range"),
                            ("estimated", "Estimated"),
                        ],
                        default="exact",
                        max_length=32,
                    ),
                ),
            ],
            options={
                "abstract": False,
                "indexes": [
                    models.Index(
                        fields=["publication_status"],
                        name="materials_m_publica_588a3d_idx",
                    )
                ],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="SampleAuthor",
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
                ("position", models.PositiveIntegerField(default=1)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sample_author_links",
                        to="bibliography.author",
                    ),
                ),
                (
                    "sample",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sample_authors",
                        to="materials.sample",
                    ),
                ),
            ],
            options={
                "ordering": ["position", "author_id", "id"],
                "indexes": [],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("sample", "author"),
                        name="materials_sampleauthor_unique_author",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="SampleExternalRecord",
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
                ("external_id", models.CharField(max_length=255)),
                ("url", models.URLField(blank=True, max_length=2083)),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "sample",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="external_records",
                        to="materials.sample",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="external_sample_records",
                        to="bibliography.source",
                    ),
                ),
            ],
            options={
                "ordering": ["source__title", "external_id"],
                "indexes": [],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("source", "external_id"),
                        name="unique_external_sample_source_id",
                    ),
                    models.UniqueConstraint(
                        fields=("sample", "source"),
                        name="unique_external_source_per_sample",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="analyticalmethod",
            name="sources",
            field=models.ManyToManyField(
                blank=True,
                help_text="References for this analytical method.",
                to="bibliography.source",
            ),
        ),
        migrations.AddField(
            model_name="basematerial",
            name="categories",
            field=models.ManyToManyField(blank=True, to="materials.materialcategory"),
        ),
        migrations.AddField(
            model_name="samplegroup",
            name="sources",
            field=models.ManyToManyField(
                blank=True, related_name="sample_groups", to="bibliography.source"
            ),
        ),
        migrations.AddField(
            model_name="materialproperty",
            name="allowed_units",
            field=models.ManyToManyField(
                blank=True,
                help_text="Units that are acceptable for this property.",
                to="properties.unit",
            ),
        ),
        migrations.AddField(
            model_name="sampleseries",
            name="temporal_distributions",
            field=models.ManyToManyField(to="distributions.temporaldistribution"),
        ),
        migrations.AddField(
            model_name="sample",
            name="sources",
            field=models.ManyToManyField(to="bibliography.source"),
        ),
        migrations.AddField(
            model_name="sample",
            name="sample_groups",
            field=models.ManyToManyField(
                blank=True,
                help_text="Studies, experiments, campaigns, or analyses that relate this sample to other samples without implying a temporal series.",
                related_name="samples",
                to="materials.samplegroup",
            ),
        ),
        migrations.AddField(
            model_name="sample",
            name="authors",
            field=models.ManyToManyField(
                blank=True,
                help_text="Corresponding authors or data contributors shown on the sample detail page.",
                related_name="samples",
                through="materials.SampleAuthor",
                to="bibliography.author",
            ),
        ),
        migrations.AddField(
            model_name="componentmeasurement",
            name="sources",
            field=models.ManyToManyField(
                blank=True,
                help_text="References for this measurement.",
                to="bibliography.source",
            ),
        ),
        migrations.AddField(
            model_name="materialpropertyvalue",
            name="sources",
            field=models.ManyToManyField(
                blank=True,
                help_text="References for this measurement.",
                to="bibliography.source",
            ),
        ),
    ]
