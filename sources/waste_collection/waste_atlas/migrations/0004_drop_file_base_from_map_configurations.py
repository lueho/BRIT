"""Drop the obsolete ``fileBase`` key from stored map configurations.

Export file names are now derived deterministically from each map page's
map set and theme (see ``waste_atlas.templatetags.atlas_tags.export_file_base``),
so the per-configuration ``fileBase`` value seeded by migrations 0002 and
0003 is no longer read.  This migration strips it from every stored
configuration so the column stays clean.
"""

from django.db import migrations


def drop_file_base(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    for configuration in configuration_model.objects.all():
        if "fileBase" in configuration.configuration:
            configuration.configuration.pop("fileBase")
            configuration.save(update_fields=["configuration"])


def noop(apps, schema_editor):
    """The original ``fileBase`` values are gone; restore is not meaningful."""


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0003_seed_target_waste_category"),
    ]

    operations = [
        migrations.RunPython(drop_file_base, noop),
    ]
