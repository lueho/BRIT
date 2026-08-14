"""Use fixed percentage bands for the connection-rate map."""

from django.db import migrations


def disable_connection_rate_quartiles(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    stored = configuration_model.objects.get(key="connection_rate")
    configuration = dict(stored.configuration)
    configuration["enableQuartiles"] = False
    stored.configuration = configuration
    stored.save(update_fields=["configuration"])


def restore_connection_rate_quartiles(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    stored = configuration_model.objects.get(key="connection_rate")
    configuration = dict(stored.configuration)
    configuration.pop("enableQuartiles", None)
    stored.configuration = configuration
    stored.save(update_fields=["configuration"])


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0016_distinguish_no_collection_from_no_door_to_door"),
    ]

    operations = [
        migrations.RunPython(
            disable_connection_rate_quartiles,
            restore_connection_rate_quartiles,
        )
    ]
