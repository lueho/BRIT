import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bibliography", "0010_author_contact_details"),
        ("materials", "0020_sample_image_metadata"),
    ]

    operations = [
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
            ],
            options={"ordering": ["source__title", "external_id"]},
        ),
        migrations.AddField(
            model_name="componentmeasurement",
            name="analysis_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="componentmeasurement",
            name="analysis_laboratory",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="componentmeasurement",
            name="detection_limit",
            field=models.DecimalField(
                blank=True, decimal_places=15, max_digits=30, null=True
            ),
        ),
        migrations.AddField(
            model_name="componentmeasurement",
            name="raw_detection_limit",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="componentmeasurement",
            name="raw_value",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="componentmeasurement",
            name="value_qualifier",
            field=models.CharField(
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
        migrations.AddField(
            model_name="materialpropertyvalue",
            name="analysis_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="materialpropertyvalue",
            name="analysis_laboratory",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="materialpropertyvalue",
            name="comment",
            field=models.TextField(
                blank=True,
                help_text="Additional comments about the measurement.",
            ),
        ),
        migrations.AddField(
            model_name="materialpropertyvalue",
            name="detection_limit",
            field=models.DecimalField(
                blank=True, decimal_places=15, max_digits=30, null=True
            ),
        ),
        migrations.AddField(
            model_name="materialpropertyvalue",
            name="raw_detection_limit",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="materialpropertyvalue",
            name="raw_value",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="materialpropertyvalue",
            name="value_qualifier",
            field=models.CharField(
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
        migrations.AddField(
            model_name="sampleexternalrecord",
            name="sample",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="external_records",
                to="materials.sample",
            ),
        ),
        migrations.AddField(
            model_name="sampleexternalrecord",
            name="source",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="external_sample_records",
                to="bibliography.source",
            ),
        ),
        migrations.AddConstraint(
            model_name="sampleexternalrecord",
            constraint=models.UniqueConstraint(
                fields=("source", "external_id"),
                name="unique_external_sample_source_id",
            ),
        ),
        migrations.AddConstraint(
            model_name="sampleexternalrecord",
            constraint=models.UniqueConstraint(
                fields=("sample", "source"),
                name="unique_external_source_per_sample",
            ),
        ),
    ]
