from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("processes", "0006_alter_process_publication_status_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="process",
            options={
                "ordering": ["name", "id"],
                "permissions": [
                    ("can_moderate_process", "Can moderate processes"),
                ],
                "verbose_name_plural": "Processes",
            },
        ),
        migrations.AddField(
            model_name="process",
            name="author_institution",
            field=models.CharField(
                blank=True,
                help_text="Institutional affiliation for the process author.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="process",
            name="author_name",
            field=models.CharField(
                blank=True,
                help_text="Author or contributor name shown on the process detail page.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="process",
            name="contact_email",
            field=models.EmailField(
                blank=True,
                help_text="Contact email address for the process author.",
                max_length=254,
            ),
        ),
        migrations.AddField(
            model_name="process",
            name="process_technology",
            field=models.TextField(
                blank=True,
                help_text="Technology description, equipment, and process conditions.",
            ),
        ),
    ]
