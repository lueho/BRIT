from django.db import migrations


def ensure_catalonia_kpi_properties(apps, schema_editor):
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

    # Ensure the % unit exists (may already be present with id=43)
    pct_unit, _ = Unit.objects.get_or_create(
        name="%",
        defaults={"owner": owner, "dimensionless": False},
    )

    # Ensure the d/wk unit exists
    days_per_wk_unit, _ = Unit.objects.get_or_create(
        name="d/wk",
        defaults={"owner": owner, "dimensionless": False},
    )

    # Biowaste impurity rate property
    impurity_prop, _ = Property.objects.get_or_create(
        name="biowaste impurity rate",
        defaults={
            "owner": owner,
            "unit": "%",
            "publication_status": "published",
        },
    )
    impurity_prop.allowed_units.add(pct_unit)

    # Weekly bring-point access days property
    bp_days_prop, _ = Property.objects.get_or_create(
        name="weekly bring-point access days",
        defaults={
            "owner": owner,
            "unit": "d/wk",
            "publication_status": "published",
        },
    )
    bp_days_prop.allowed_units.add(days_per_wk_unit)


def remove_catalonia_kpi_properties(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    Unit = apps.get_model("properties", "Unit")
    Property.objects.filter(
        name__in=["biowaste impurity rate", "weekly bring-point access days"]
    ).delete()
    Unit.objects.filter(name="d/wk").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("properties", "0009_collection_point_property"),
    ]

    operations = [
        migrations.RunPython(
            ensure_catalonia_kpi_properties,
            remove_catalonia_kpi_properties,
        ),
    ]
