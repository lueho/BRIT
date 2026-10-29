import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("properties", "0001_squashed_0010"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="property",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="unit",
            name="content_revision",
            field=models.PositiveBigIntegerField(default=1, editable=False),
        ),
        migrations.AlterField(
            model_name="property",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="property",
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
            model_name="property",
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
            model_name="property",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="unit",
            name="approved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="unit",
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
            model_name="unit",
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
            model_name="unit",
            name="submitted_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
