from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("roadside_trees", "0003_remove_green_areas_model"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="hamburgroadsidetrees",
            table="roadside_trees_hamburgroadsidetrees",
        ),
    ]
