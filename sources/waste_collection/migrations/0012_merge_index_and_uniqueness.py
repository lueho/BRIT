import django.db.migrations.migration


class Migration(django.db.migrations.migration.Migration):
    dependencies = [
        ("waste_collection", "0009_collection_collection_pub_status_idx_and_more"),
        ("waste_collection", "0011_generated_cpv_source_uniqueness"),
    ]
