from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        (
            "waste_atlas",
            "0014_alter_wasteatlasrenderingsettings_export_legend_item_flow",
        ),
        ("waste_atlas", "0014_seed_rp_map_configurations"),
    ]

    operations = []
