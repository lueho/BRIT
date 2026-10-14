import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import utils.object_management.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Author",
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
                (
                    "first_names",
                    models.CharField(blank=True, max_length=1023, null=True),
                ),
                (
                    "middle_names",
                    models.CharField(blank=True, max_length=1023, null=True),
                ),
                (
                    "last_names",
                    models.CharField(blank=True, max_length=1023, null=True),
                ),
                ("suffix", models.CharField(blank=True, max_length=100, null=True)),
                (
                    "preferred_citation",
                    models.CharField(blank=True, max_length=2046, null=True),
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
                ("contact_email", models.EmailField(blank=True, max_length=254)),
                ("institution", models.CharField(blank=True, max_length=255)),
                (
                    "author_type",
                    models.CharField(
                        choices=[
                            ("person", "Person"),
                            ("organization", "Organization"),
                        ],
                        default="person",
                        max_length=20,
                    ),
                ),
                (
                    "organization_abbreviation",
                    models.CharField(blank=True, max_length=255),
                ),
                ("organization_name", models.CharField(blank=True, max_length=1023)),
            ],
            options={
                "ordering": ["last_names", "first_names"],
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="Licence",
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
                ("reference_url", models.URLField(blank=True, null=True)),
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
            },
        ),
        migrations.CreateModel(
            name="Source",
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
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("article", "Journal article"),
                            ("book", "Book"),
                            ("incollection", "Book chapter"),
                            ("proceedings", "Conference proceedings"),
                            ("inproceedings", "Conference paper"),
                            ("report", "Report"),
                            ("thesis", "Thesis"),
                            ("preprint", "Preprint"),
                            ("dataset", "Dataset"),
                            ("standard", "Standard"),
                            ("patent", "Patent"),
                            ("online", "Online resource"),
                            ("periodical", "Periodical"),
                            ("misc", "Miscellaneous"),
                        ],
                        default="misc",
                        max_length=255,
                    ),
                ),
                ("publisher", models.CharField(blank=True, max_length=127, null=True)),
                ("title", models.CharField(max_length=500)),
                ("journal", models.CharField(blank=True, max_length=500, null=True)),
                ("year", models.IntegerField(blank=True, null=True)),
                ("abstract", models.TextField(blank=True, null=True)),
                ("attributions", models.TextField(blank=True, null=True)),
                ("url", models.URLField(blank=True, max_length=2083, null=True)),
                ("url_valid", models.BooleanField(default=False)),
                ("url_checked", models.DateField(blank=True, null=True)),
                ("doi", models.CharField(blank=True, max_length=255, null=True)),
                ("last_accessed", models.DateField(blank=True, null=True)),
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
                    "licence",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="bibliography.licence",
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
                ("month", models.CharField(blank=True, max_length=50, null=True)),
                ("pages", models.CharField(blank=True, max_length=255, null=True)),
                ("volume", models.CharField(blank=True, max_length=255, null=True)),
                ("number", models.CharField(blank=True, max_length=255, null=True)),
                ("eid", models.CharField(blank=True, max_length=255, null=True)),
                ("citation_key", models.CharField(blank=True, max_length=50)),
            ],
            options={
                "verbose_name": "Source",
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="SourceAuthor",
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
                ("position", models.PositiveIntegerField()),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sourceauthors",
                        to="bibliography.author",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sourceauthors",
                        to="bibliography.source",
                    ),
                ),
            ],
            options={
                "ordering": ["position"],
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.AddField(
            model_name="source",
            name="authors",
            field=models.ManyToManyField(
                related_name="sources",
                through="bibliography.SourceAuthor",
                to="bibliography.author",
            ),
        ),
    ]
