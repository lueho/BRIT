from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("processes", "0014_process_author_source_formsets"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="processauthor",
            options={"ordering": ["position", "author_id", "id"]},
        ),
    ]
