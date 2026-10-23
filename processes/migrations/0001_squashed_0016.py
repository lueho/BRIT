import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import processes.models
import utils.object_management.models


class Migration(migrations.Migration):
    replaces = [
        ("processes", "0001_initial"),
        ("processes", "0002_processcategory_process_processinforesource_and_more"),
        ("processes", "0003_refine_process_models"),
        (
            "processes",
            "0004_rename_processmat_process_r_0d0e2b_idx_processes_p_process_807014_idx_and_more",
        ),
        ("processes", "0005_add_moderation_permissions"),
        ("processes", "0006_alter_process_publication_status_and_more"),
        ("processes", "0007_alter_process_options_process_author_and_more"),
        ("processes", "0008_process_supplementary_document"),
        ("processes", "0009_processcategory_supplementary_document"),
        ("processes", "0010_process_image_metadata"),
        ("processes", "0011_process_authors"),
        ("processes", "0012_move_process_contact_details_to_authors"),
        ("processes", "0013_process_sources"),
        ("processes", "0014_process_author_source_formsets"),
        ("processes", "0015_processauthor_ordering"),
        ("processes", "0016_remove_process_parent"),
    ]

    initial = True

    dependencies = [
        ("bibliography", "0001_squashed_0012"),
        ("materials", "0001_squashed_0032"),
        ("properties", "0001_squashed_0010"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AppPermission",
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
            ],
            options={
                "permissions": [("access_app_feature", "Can access the app feature")],
                "managed": False,
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="Process",
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "short_description",
                    models.CharField(
                        blank=True,
                        help_text="One sentence summary used in cards and list views.",
                        max_length=512,
                    ),
                ),
                (
                    "mechanism",
                    models.CharField(
                        blank=True,
                        help_text="Dominant conversion mechanism (e.g. fermentation, pyrolysis).",
                        max_length=255,
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        blank=True,
                        help_text="Optional illustrative image for cards or detail views.",
                        null=True,
                        upload_to="processes/process_images/",
                    ),
                ),
                (
                    "process_technology",
                    models.TextField(
                        blank=True,
                        help_text="Technology description, equipment, and process conditions.",
                    ),
                ),
                (
                    "supplementary_document",
                    models.FileField(
                        blank=True,
                        help_text="Optional supplementary PDF document, such as a process flow sheet.",
                        null=True,
                        upload_to="processes/supplementary_documents/",
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=["pdf"]
                            )
                        ],
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
                "permissions": [("can_moderate_process", "Can moderate processes")],
                "verbose_name_plural": "Processes",
            },
        ),
        migrations.CreateModel(
            name="ProcessAuthor",
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
                ("position", models.PositiveIntegerField(default=1)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="process_author_links",
                        to="bibliography.author",
                    ),
                ),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="process_authors",
                        to="processes.process",
                    ),
                ),
            ],
            options={
                "ordering": ["position", "author_id", "id"],
            },
        ),
        migrations.AddField(
            model_name="process",
            name="authors",
            field=models.ManyToManyField(
                blank=True,
                help_text="Authors or contributors shown on the process detail page.",
                related_name="processes",
                through="processes.ProcessAuthor",
                to="bibliography.author",
            ),
        ),
        migrations.CreateModel(
            name="ProcessCategory",
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
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "supplementary_document",
                    models.FileField(
                        blank=True,
                        help_text="Optional supplementary PDF document with combined information for related processes.",
                        null=True,
                        upload_to="processes/category_supplementary_documents/",
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=["pdf"]
                            )
                        ],
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
                "verbose_name": "Process category",
                "verbose_name_plural": "Process categories",
                "permissions": [
                    ("can_moderate_processcategory", "Can moderate process categories")
                ],
            },
        ),
        migrations.AddField(
            model_name="process",
            name="categories",
            field=models.ManyToManyField(
                blank=True,
                help_text="High level categories such as thermochemical or biochemical.",
                related_name="processes",
                to="processes.processcategory",
            ),
        ),
        migrations.CreateModel(
            name="ProcessInfoResource",
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
                ("title", models.CharField(max_length=255)),
                (
                    "resource_type",
                    models.CharField(
                        choices=[
                            ("internal", "Internal page"),
                            ("document", "Document upload"),
                            ("external", "External link"),
                        ],
                        default="external",
                        max_length=20,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "url",
                    models.CharField(
                        blank=True,
                        help_text="Target URL for internal or external resources.",
                        max_length=1023,
                        validators=[processes.models.validate_internal_or_external_url],
                    ),
                ),
                (
                    "document",
                    models.FileField(
                        blank=True, null=True, upload_to="processes/info_resources/"
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="info_resources",
                        to="processes.process",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ProcessLink",
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
                ("label", models.CharField(max_length=255)),
                (
                    "url",
                    models.CharField(
                        help_text="Relative or absolute URL to navigate to.",
                        max_length=1023,
                        validators=[processes.models.validate_internal_or_external_url],
                    ),
                ),
                (
                    "open_in_new_tab",
                    models.BooleanField(
                        default=False,
                        help_text="Open the link in a new browser tab/window.",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="links",
                        to="processes.process",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ProcessMaterial",
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
                        choices=[("input", "Input"), ("output", "Output")],
                        max_length=10,
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0, help_text="Optional order for display purposes."
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Additional context such as required pre-treatment or quality specs.",
                    ),
                ),
                (
                    "optional",
                    models.BooleanField(
                        default=False,
                        help_text="Flag inputs/outputs that are optional rather than mandatory.",
                    ),
                ),
                (
                    "quantity_value",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        help_text="Representative quantity for the material (e.g. 2.5).",
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    "stage",
                    models.CharField(
                        blank=True,
                        help_text="Stage of the process where this material is relevant (e.g. preprocessing).",
                        max_length=128,
                    ),
                ),
                (
                    "stream_label",
                    models.CharField(
                        blank=True,
                        help_text="Optional label to distinguish parallel streams for the same material.",
                        max_length=128,
                    ),
                ),
                (
                    "material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="process_materials",
                        to="materials.material",
                    ),
                ),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="process_materials",
                        to="processes.process",
                    ),
                ),
                (
                    "quantity_unit",
                    models.ForeignKey(
                        blank=True,
                        help_text="Unit describing the quantity when provided.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="properties.unit",
                    ),
                ),
            ],
            options={
                "ordering": ["role", "order", "id"],
                "unique_together": set(),
            },
        ),
        migrations.AddField(
            model_name="process",
            name="materials",
            field=models.ManyToManyField(
                blank=True,
                related_name="processes",
                through="processes.ProcessMaterial",
                to="materials.material",
            ),
        ),
        migrations.CreateModel(
            name="ProcessOperatingParameter",
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
                    "parameter",
                    models.CharField(
                        choices=[
                            ("temperature", "Temperature"),
                            ("pressure", "Pressure"),
                            ("residence_time", "Residence time"),
                            ("throughput", "Throughput"),
                            ("energy_demand", "Specific energy demand"),
                            ("yield", "Yield"),
                            ("ph", "pH"),
                            ("custom", "Custom"),
                        ],
                        help_text="Type of operating parameter (e.g. temperature, yield).",
                        max_length=32,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        blank=True,
                        help_text="Override label for the parameter (used for custom entries).",
                        max_length=255,
                    ),
                ),
                (
                    "value_min",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        help_text="Lower bound for the operating window.",
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    "value_max",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        help_text="Upper bound for the operating window.",
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    "nominal_value",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        help_text="Single representative value when no range is required.",
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    "basis",
                    models.CharField(
                        blank=True,
                        help_text="Basis or conditions for the measurement (e.g. wet basis).",
                        max_length=100,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="operating_parameters",
                        to="processes.process",
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        help_text="Unit describing the parameter values.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="properties.unit",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ProcessSource",
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
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="process_sources",
                        to="processes.process",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="process_source_links",
                        to="bibliography.source",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.AddField(
            model_name="process",
            name="sources",
            field=models.ManyToManyField(
                blank=True,
                help_text="Bibliography sources used by this process.",
                related_name="processes",
                through="processes.ProcessSource",
                to="bibliography.source",
            ),
        ),
        migrations.AddConstraint(
            model_name="processauthor",
            constraint=models.UniqueConstraint(
                fields=("process", "author"),
                name="processes_processauthor_unique_author",
            ),
        ),
        migrations.AddIndex(
            model_name="processmaterial",
            index=models.Index(
                fields=["process", "role", "order"],
                name="processes_p_process_807014_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="processoperatingparameter",
            index=models.Index(
                fields=["process", "parameter", "order"],
                name="processes_p_process_ebf597_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="processsource",
            constraint=models.UniqueConstraint(
                fields=("process", "source"),
                name="processes_processsource_unique_source",
            ),
        ),
    ]
