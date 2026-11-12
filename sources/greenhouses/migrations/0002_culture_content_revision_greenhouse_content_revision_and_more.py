import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("greenhouses", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="culture",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="greenhouse",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="greenhousegrowthcycle",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="growthshare",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AlterField(
            model_name="culture",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="culture",
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
            model_name="culture",
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
            model_name="culture",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="greenhouse",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="greenhouse",
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
            model_name="greenhouse",
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
            model_name="greenhouse",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="greenhousegrowthcycle",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="greenhousegrowthcycle",
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
            model_name="greenhousegrowthcycle",
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
            model_name="greenhousegrowthcycle",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="growthshare",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="growthshare",
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
            model_name="growthshare",
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
            model_name="growthshare",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
