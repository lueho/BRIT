from django.db import migrations


def populate_region_type(apps, schema_editor):
    """Set type field for existing regions based on subclass tables."""
    Region = apps.get_model("maps", "Region")
    NutsRegion = apps.get_model("maps", "NutsRegion")
    LauRegion = apps.get_model("maps", "LauRegion")

    nuts_ids = NutsRegion.objects.values_list("region_ptr_id", flat=True)
    Region.objects.filter(id__in=nuts_ids).update(type="nuts")

    lau_ids = LauRegion.objects.values_list("region_ptr_id", flat=True)
    Region.objects.filter(id__in=lau_ids).update(type="lau")

    # Everything else stays "custom" (the field default)


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0004_region_type_field"),
    ]

    operations = [
        migrations.RunPython(
            populate_region_type,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
