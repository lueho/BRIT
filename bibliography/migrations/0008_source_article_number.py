from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bibliography", "0007_source_article_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="source",
            name="article_number",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
