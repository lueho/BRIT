from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0019_materialproperty_unit_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="sample",
            name="image_alt_text",
            field=models.CharField(
                blank=True,
                help_text="Accessible description of the image.",
                max_length=255,
                verbose_name="image alt text",
            ),
        ),
        migrations.AddField(
            model_name="sample",
            name="image_caption",
            field=models.CharField(
                blank=True,
                help_text="Caption displayed with the image.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="sample",
            name="image_rights_notice",
            field=models.CharField(
                blank=True,
                help_text="Copyright, license, or attribution notice for the image.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="sampleseries",
            name="image_alt_text",
            field=models.CharField(
                blank=True,
                help_text="Accessible description of the image.",
                max_length=255,
                verbose_name="image alt text",
            ),
        ),
        migrations.AddField(
            model_name="sampleseries",
            name="image_caption",
            field=models.CharField(
                blank=True,
                help_text="Caption displayed with the image.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="sampleseries",
            name="image_rights_notice",
            field=models.CharField(
                blank=True,
                help_text="Copyright, license, or attribution notice for the image.",
                max_length=255,
            ),
        ),
    ]
