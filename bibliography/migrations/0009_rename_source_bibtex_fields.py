from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bibliography", "0008_source_article_number"),
    ]

    operations = [
        migrations.RenameField(
            model_name="source",
            old_name="issue",
            new_name="number",
        ),
        migrations.RenameField(
            model_name="source",
            old_name="article_number",
            new_name="eid",
        ),
        migrations.RenameField(
            model_name="source",
            old_name="abbreviation",
            new_name="citation_key",
        ),
    ]
