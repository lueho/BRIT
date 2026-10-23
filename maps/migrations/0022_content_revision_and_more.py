import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0021_regionattributevalue_sources"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="catchment",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="catchmentrevision",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="categoricalattribute",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="geodataset",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="location",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="mapconfiguration",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="maplayerconfiguration",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="maplayerstyle",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="region",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="regionattributetextvalue",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="regionattributevalue",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="regionproperty",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AlterField(
            model_name="catchment",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="catchment",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="catchment",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="catchment",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="catchmentrevision",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="catchmentrevision",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="catchmentrevision",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="catchmentrevision",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="categoricalattribute",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="categoricalattribute",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="categoricalattribute",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="categoricalattribute",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="geodataset",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="geodataset",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="geodataset",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="geodataset",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="location",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="location",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="location",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="location",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="mapconfiguration",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="mapconfiguration",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="mapconfiguration",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="mapconfiguration",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="maplayerconfiguration",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="maplayerconfiguration",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="maplayerconfiguration",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="maplayerconfiguration",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="maplayerstyle",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="maplayerstyle",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="maplayerstyle",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="maplayerstyle",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="region",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="region",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="region",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="region",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="regionattributetextvalue",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="regionattributetextvalue",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="regionattributetextvalue",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="regionattributetextvalue",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="regionattributevalue",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="regionattributevalue",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="regionattributevalue",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="regionattributevalue",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="regionproperty",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="regionproperty",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="regionproperty",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("review", "Review"),
                    ("published", "Published"),
                    ("declined", "Declined"),
                    ("archived", "Archived"),
                ],
                default="private",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="regionproperty",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
