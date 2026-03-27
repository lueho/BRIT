import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.core.management.color import no_style
from django.db import migrations, models

import utils.object_management.models


def copy_attributes_to_region_properties(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Attribute = apps.get_model("maps", "Attribute")
    RegionProperty = apps.get_model("maps", "RegionProperty")

    for attribute in Attribute.objects.using(db_alias).all().iterator():
        RegionProperty.objects.using(db_alias).update_or_create(
            pk=attribute.pk,
            defaults={
                "name": attribute.name,
                "description": attribute.description,
                "unit": attribute.unit,
                "owner_id": attribute.owner_id,
                "publication_status": attribute.publication_status,
                "submitted_at": attribute.submitted_at,
                "approved_at": attribute.approved_at,
                "approved_by_id": attribute.approved_by_id,
                "created_at": attribute.created_at,
                "lastmodified_at": attribute.lastmodified_at,
                "created_by_id": attribute.created_by_id,
                "lastmodified_by_id": attribute.lastmodified_by_id,
            },
        )

    sequence_sql = schema_editor.connection.ops.sequence_reset_sql(
        no_style(),
        [RegionProperty],
    )
    with schema_editor.connection.cursor() as cursor:
        for sql in sequence_sql:
            cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0008_regionattributevalue_unit"),
    ]

    operations = [
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
                ("unit", models.CharField(max_length=127)),
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
        migrations.RunPython(
            copy_attributes_to_region_properties,
            migrations.RunPython.noop,
        ),
    ]
