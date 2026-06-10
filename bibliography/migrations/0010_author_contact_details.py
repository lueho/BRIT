from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bibliography", "0009_rename_source_bibtex_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="author",
            name="contact_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="author",
            name="institution",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
