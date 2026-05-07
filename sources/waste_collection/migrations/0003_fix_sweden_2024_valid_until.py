"""
Data migration: set valid_until = 2024-12-31 for Swedish 2024 collections
that currently have valid_until = NULL.

Swedish annual reports cover a single calendar year, so the validity period
should always be YYYY-01-01 to YYYY-12-31.  The 2024 import left valid_until
as NULL because no subsequent year had been imported to trigger the
predecessor-closing logic in CollectionImporter.
"""

import datetime

from django.db import migrations


def fix_sweden_2024_valid_until(apps, schema_editor):
    Collection = apps.get_model("waste_collection", "Collection")
    updated = Collection.objects.filter(
        valid_from=datetime.date(2024, 1, 1),
        valid_until__isnull=True,
        catchment__region__lauregion__cntr_code="SE",
    ).update(valid_until=datetime.date(2024, 12, 31))
    if updated:
        print(f"  Updated valid_until for {updated} Swedish 2024 collections.")


def reverse_fix(apps, schema_editor):
    Collection = apps.get_model("waste_collection", "Collection")
    Collection.objects.filter(
        valid_from=datetime.date(2024, 1, 1),
        valid_until=datetime.date(2024, 12, 31),
        catchment__region__lauregion__cntr_code="SE",
    ).update(valid_until=None)


class Migration(migrations.Migration):
    dependencies = [
        ("waste_collection", "0002_rename_sortingmethod_binconfiguration_and_more"),
        ("maps", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(fix_sweden_2024_valid_until, reverse_code=reverse_fix),
    ]
