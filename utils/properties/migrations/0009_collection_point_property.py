from django.db import migrations


def ensure_collection_point_property(apps, schema_editor):
    from django.conf import settings

    Property = apps.get_model("properties", "Property")
    Unit = apps.get_model("properties", "Unit")
    User = apps.get_model("auth", "User")

    username = (
        getattr(settings, "DEFAULT_OBJECT_OWNER_USERNAME", None)
        or getattr(settings, "ADMIN_USERNAME", None)
        or getattr(settings, "DEFAULT_OWNER_USERNAME", "flexibi")
    )
    owner, _ = User.objects.get_or_create(
        username=username,
        defaults={"is_active": True},
    )
    no_unit, _ = Unit.objects.get_or_create(
        owner=owner,
        name="No unit",
        defaults={"dimensionless": True},
    )
    prop, _ = Property.objects.get_or_create(
        owner=owner,
        name="number of collection points",
        defaults={
            "unit": "No unit",
            "publication_status": "published",
        },
    )
    prop.allowed_units.add(no_unit)


def remove_collection_point_property(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    Property.objects.filter(name="number of collection points").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("properties", "0008_materialproperty_unit_optional"),
    ]

    operations = [
        migrations.RunPython(
            ensure_collection_point_property,
            remove_collection_point_property,
        ),
    ]
