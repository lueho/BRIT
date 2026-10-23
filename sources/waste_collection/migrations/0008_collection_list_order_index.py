from django.conf import settings
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        (
            "bibliography",
            "0001_squashed_0012",
        ),
        ("materials", "0023_remove_component_kind"),
        ("waste_collection", "0007_alter_collectioncountoptions_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="collection",
            index=models.Index(fields=["name", "id"], name="collection_name_id_idx"),
        ),
    ]
