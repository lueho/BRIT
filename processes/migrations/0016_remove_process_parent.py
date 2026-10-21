from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("processes", "0015_processauthor_ordering"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="process",
            name="parent",
        ),
    ]
