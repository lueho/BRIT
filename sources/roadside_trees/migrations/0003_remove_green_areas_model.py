from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("roadside_trees", "0002_update_content_types"),
        ("urban_green_spaces", "0001_move_green_areas_from_roadside_trees"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="HamburgGreenAreas"),
            ],
        )
    ]
