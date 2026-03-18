from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bibliography", "0006_alter_source_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="source",
            name="month",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="source",
            name="pages",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="source",
            name="volume",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
