"""Retroactive backfill of approval metadata for pre-workflow published rows.

Rows that were published before the formal review/approval workflow existed
were migrated into the ``published`` state without ``approved_at`` /
``approved_by``. This migration backfills them with ``approved_at =
created_at`` and ``approved_by = owner`` so the publication audit trail is
complete and the save-time invariant (``published`` requires approval
metadata) can be enforced going forward. See issue #93.
"""

from django.db import migrations
from django.db.models import F

REQUIRED_FIELDS = {
    "publication_status",
    "approved_at",
    "approved_by",
    "owner",
    "created_at",
}


def backfill_approval_metadata(apps, schema_editor):
    for model in apps.get_app_config("materials").get_models():
        if model._meta.proxy:
            continue
        field_names = {field.name for field in model._meta.fields}
        if not REQUIRED_FIELDS <= field_names:
            continue
        published = model.objects.filter(publication_status="published")
        published.filter(approved_at__isnull=True).update(approved_at=F("created_at"))
        published.filter(approved_by__isnull=True).update(approved_by_id=F("owner_id"))


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0033_measurement_limit_type"),
    ]

    operations = [
        migrations.RunPython(
            backfill_approval_metadata,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
