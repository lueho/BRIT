"""Hide unused minimum-bin-size categories from each rendered legend."""

from django.db import migrations

MIN_BIN_SIZE_CONFIGURATIONS = (
    "biowaste_min_bin_size",
    "residual_min_bin_size",
)


def set_show_only_present_categories(apps, schema_editor, *, enabled):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    for configuration in configuration_model.objects.filter(
        key__in=MIN_BIN_SIZE_CONFIGURATIONS
    ):
        stored = dict(configuration.configuration)
        if enabled:
            stored["showOnlyPresentCategories"] = True
        else:
            stored.pop("showOnlyPresentCategories", None)
        configuration.configuration = stored
        configuration.save(update_fields=["configuration"])


def enable(apps, schema_editor):
    set_show_only_present_categories(apps, schema_editor, enabled=True)


def disable(apps, schema_editor):
    set_show_only_present_categories(apps, schema_editor, enabled=False)


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0020_reclassify_min_bin_sizes"),
    ]

    operations = [migrations.RunPython(enable, disable)]
