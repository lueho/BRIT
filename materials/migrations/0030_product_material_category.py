"""Create the 'Product' material category.

The category marks materials that are products of bioresource processing
(e.g. in CLOSECYCLE showcases) and is also used for showcase linkage.
"""

from django.conf import settings
from django.db import migrations


def ensure_product_category(apps, schema_editor):
    """Create the default owner user and the 'Product' MaterialCategory."""
    User = apps.get_model("auth", "User")
    MaterialCategory = apps.get_model("materials", "MaterialCategory")
    username = getattr(settings, "DEFAULT_OBJECT_OWNER_USERNAME", None) or getattr(
        settings, "DEFAULT_OWNER_USERNAME", "flexibi"
    )
    user, _ = User.objects.get_or_create(
        username=username, defaults={"is_active": True}
    )
    MaterialCategory.objects.get_or_create(
        name="Product",
        defaults={
            "description": (
                "A product is the output of a production process and is "
                "intentionally created from one or more materials to fulfil "
                "a specific function. It is a good with an intended positive "
                "market value."
            ),
            "publication_status": "published",
            "owner": user,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0029_merge_20260922_1559"),
    ]

    operations = [
        migrations.RunPython(ensure_product_category, migrations.RunPython.noop),
    ]
