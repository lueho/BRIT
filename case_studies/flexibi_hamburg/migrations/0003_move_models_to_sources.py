from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("flexibi_hamburg", "0002_hamburgroadsidetrees_flexibi_ham_baumid_4f523a_idx_and_more"),
        ("roadside_trees", "0001_move_legacy_models"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="HamburgGreenAreas"),
                migrations.DeleteModel(name="HamburgRoadsideTrees"),
            ],
        )
    ]
