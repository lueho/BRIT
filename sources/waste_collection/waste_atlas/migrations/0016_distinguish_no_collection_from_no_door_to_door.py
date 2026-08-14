"""Keep absence of collection distinct from absence of door-to-door service."""

from django.db import migrations

NO_DOOR_TO_DOOR_LABEL = "No separate door-to-door biowaste collection"

DOOR_TO_DOOR_BIOWASTE_CONFIGS = {
    "biowaste_collection_count",
    "biowaste_fee_system",
    "biowaste_frequency",
    "biowaste_min_bin_size",
    "biowaste_required_bin_capacity",
    "collection_count_ratio",
    "combined_collection_count",
    "combined_fee_system",
    "combined_frequency",
    "connection_rate",
    "min_bin_size_ratio",
    "rp_biowaste_collection_count",
    "rp_collection_count_ratio",
}

NO_DOOR_TO_DOOR_VALUES = {
    "no_bio",
    "no_d2d",
    "no_door_to_door",
    "no_bio_collection",
}


def distinguish_no_door_to_door(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")

    for stored in configuration_model.objects.filter(
        key__in=DOOR_TO_DOOR_BIOWASTE_CONFIGS
    ):
        configuration = dict(stored.configuration)
        categories = [dict(category) for category in configuration["categories"]]

        if stored.key == "biowaste_fee_system":
            configuration["transformName"] = "biowasteFeeSystem"
            configuration["dataField"] = "_classified"
            for category in categories:
                if category.get("value") == "No separate collection":
                    category["value"] = "no_door_to_door"

        for category in categories:
            value = category.get("value") or category.get("classValue")
            if value in NO_DOOR_TO_DOOR_VALUES:
                category["label"] = NO_DOOR_TO_DOOR_LABEL
                if "exportLabel" in category:
                    category["exportLabel"] = NO_DOOR_TO_DOOR_LABEL

        configuration["categories"] = categories
        stored.configuration = configuration
        stored.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0015_merge_legend_flow_and_rp_configurations"),
    ]

    operations = [
        migrations.RunPython(
            distinguish_no_door_to_door,
            migrations.RunPython.noop,
        )
    ]
