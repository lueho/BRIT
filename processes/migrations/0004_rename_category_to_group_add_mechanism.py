import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import utils.object_management.models


class Migration(migrations.Migration):
    dependencies = [
        ("processes", "0003_seed_initial_categories"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Rename ProcessCategory → ProcessGroup (preserves table data & FK)
        migrations.RenameModel(
            old_name="ProcessCategory",
            new_name="ProcessGroup",
        ),
        migrations.AlterModelOptions(
            name="processgroup",
            options={
                "verbose_name": "Process Group",
                "verbose_name_plural": "Process Groups",
            },
        ),
        # 2. Rename FK field category → group on ProcessType (preserves data)
        migrations.RenameField(
            model_name="processtype",
            old_name="category",
            new_name="group",
        ),
        migrations.AlterField(
            model_name="processtype",
            name="group",
            field=models.ForeignKey(
                blank=True,
                help_text="Functional process group (e.g. Pulping).",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="process_types",
                to="processes.processgroup",
            ),
        ),
        # 3. Create new MechanismCategory model
        migrations.CreateModel(
            name="MechanismCategory",
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
                "verbose_name": "Mechanism Category",
                "verbose_name_plural": "Mechanism Categories",
                "unique_together": {("name", "owner")},
            },
        ),
        # 4. Add M2M mechanism_categories field on ProcessType
        migrations.AddField(
            model_name="processtype",
            name="mechanism_categories",
            field=models.ManyToManyField(
                blank=True,
                help_text="Scientific mechanism classifications (e.g. Physical, Biochemical).",
                related_name="process_types",
                to="processes.mechanismcategory",
            ),
        ),
    ]
