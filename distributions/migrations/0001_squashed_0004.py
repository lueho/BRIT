import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import utils.object_management.models


class Migration(migrations.Migration):
    replaces = [
        ("distributions", "0001_initial"),
        ("distributions", "0002_period_approved_at_period_approved_by_and_more"),
        ("distributions", "0003_alter_period_publication_status_and_more"),
        ("distributions", "0004_alter_period_publication_status_and_more"),
    ]

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TemporalDistribution",
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
                "unique_together": {("name", "owner")},
            },
        ),
        migrations.CreateModel(
            name="Timestep",
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
                    "distribution",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="distributions.temporaldistribution",
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
                "ordering": ["order"],
                "unique_together": {("name", "owner")},
            },
        ),
        migrations.CreateModel(
            name="Period",
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
                    "distribution",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="distributions.temporaldistribution",
                    ),
                ),
                (
                    "first_timestep",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="first_of_periods",
                        to="distributions.timestep",
                    ),
                ),
                (
                    "last_timestep",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="last_of_periods",
                        to="distributions.timestep",
                    ),
                ),
            ],
            options={
                "unique_together": {
                    ("distribution", "first_timestep", "last_timestep")
                },
            },
        ),
    ]
