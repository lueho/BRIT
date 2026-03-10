from django.db import migrations, models
from django.db.models import Count


def cleanup_derived_cpvs(apps, schema_editor):
    CollectionPropertyValue = apps.get_model("soilcom", "CollectionPropertyValue")

    # Remove stale derived rows when a manual counterpart exists for the same key.
    manual_keys = set(
        CollectionPropertyValue.objects.filter(is_derived=False).values_list(
            "collection_id", "property_id", "year"
        )
    )
    stale_ids = []
    for pk, collection_id, property_id, year in (
        CollectionPropertyValue.objects.filter(is_derived=True).values_list(
            "pk", "collection_id", "property_id", "year"
        )
    ).iterator():
        if (collection_id, property_id, year) in manual_keys:
            stale_ids.append(pk)
    if stale_ids:
        CollectionPropertyValue.objects.filter(pk__in=stale_ids).delete()

    # Deduplicate derived rows by keeping the newest row per (collection, property, year).
    duplicate_keys = (
        CollectionPropertyValue.objects.filter(is_derived=True)
        .values("collection_id", "property_id", "year")
        .annotate(row_count=Count("id"))
        .filter(row_count__gt=1)
    )
    for key in duplicate_keys.iterator():
        dup_ids = list(
            CollectionPropertyValue.objects.filter(
                is_derived=True,
                collection_id=key["collection_id"],
                property_id=key["property_id"],
                year=key["year"],
            )
            .order_by("-lastmodified_at", "-pk")
            .values_list("pk", flat=True)
        )
        if len(dup_ids) > 1:
            CollectionPropertyValue.objects.filter(pk__in=dup_ids[1:]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("soilcom", "0006_add_is_derived_to_collectionpropertyvalue"),
    ]

    operations = [
        migrations.RunPython(cleanup_derived_cpvs, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="collectionpropertyvalue",
            constraint=models.UniqueConstraint(
                fields=("collection", "property", "year"),
                condition=models.Q(is_derived=True),
                name="soilcom_unique_derived_cpv_per_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="collectionpropertyvalue",
            constraint=models.UniqueConstraint(
                fields=("collection", "property"),
                condition=models.Q(is_derived=True, year__isnull=True),
                name="soilcom_unique_derived_cpv_per_key_null_year",
            ),
        ),
    ]
