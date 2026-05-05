"""
Data migration for issue #100 – configure allowed_units for the 11
MaterialProperty records that previously had none.

What this migration does:
1. Creates missing Unit records for units that were only recorded as a
   legacy plain-text ``unit`` field on the property.
2. Populates ``MaterialProperty.allowed_units`` for all 11 affected rows.
3. Corrects the legacy ``unit`` text field where it contained typos
   (ADF / ADL had a leading single-quote).
4. Updates the two existing MaterialPropertyValue rows whose ``unit``
   was the placeholder "No unit" to use the canonical unit for their
   property.
"""

from django.conf import settings
from django.db import migrations


def _get_or_create_unit(Unit, User, name, symbol=""):
    username = getattr(settings, "DEFAULT_OWNER_USERNAME", "flexibi")
    owner, _ = User.objects.get_or_create(
        username=username, defaults={"is_active": True}
    )
    unit, _ = Unit.objects.get_or_create(
        name=name, owner=owner, defaults={"symbol": symbol}
    )
    return unit


def configure_allowed_units(apps, schema_editor):
    MaterialProperty = apps.get_model("materials", "MaterialProperty")
    MaterialPropertyValue = apps.get_model("materials", "MaterialPropertyValue")
    Unit = apps.get_model("properties", "Unit")
    User = apps.get_model("auth", "User")

    # --- create / fetch all required units ---

    # id=2 Temperature – °C already exists (id=58)
    unit_celsius = _get_or_create_unit(Unit, User, "°C", symbol="degC")

    # id=1 Bulk density – Mg/m³
    unit_mg_m3 = _get_or_create_unit(Unit, User, "Mg/m³", symbol="Mg/m**3")

    # id=3 Porosity – vol.-%
    unit_vol_pct = _get_or_create_unit(Unit, User, "vol.-%", symbol="")

    # id=6 Soluble Salts – mmhos/cm and dS/m (equivalent, both in use)
    unit_mmhos = _get_or_create_unit(Unit, User, "mmhos/cm", symbol="")
    unit_ds_m = _get_or_create_unit(Unit, User, "dS/m", symbol="")

    # id=7 Particle Size – mm and in
    unit_mm = _get_or_create_unit(Unit, User, "mm", symbol="mm")
    unit_inch = _get_or_create_unit(Unit, User, "in", symbol="in")

    # id=8/9/10 NDF / ADF / ADL – % (already exists as id=43)
    unit_pct = Unit.objects.filter(name="%").first()
    if unit_pct is None:
        unit_pct = _get_or_create_unit(Unit, User, "%", symbol="percent")

    # id=11 Settlement – % (same)

    # id=12 Electrical Conductivity – µS/l
    unit_us_l = _get_or_create_unit(Unit, User, "µS/l", symbol="")

    # id=46 Biomethane potential (BMP) – mL(CH4)/g(oTS)
    unit_bmp = _get_or_create_unit(Unit, User, "mL(CH4)/g(oTS)", symbol="")

    # --- wire allowed_units M2M ---

    property_allowed_units = {
        1: [unit_mg_m3],  # Bulk density
        2: [unit_celsius],  # Temperature
        3: [unit_vol_pct],  # Porosity
        6: [unit_mmhos, unit_ds_m],  # Soluble Salts
        7: [unit_mm, unit_inch],  # Particle Size
        8: [unit_pct],  # NDF
        9: [unit_pct],  # ADF
        10: [unit_pct],  # ADL
        11: [unit_pct],  # Settlement
        12: [unit_us_l],  # Electrical Conductivity
        46: [unit_bmp],  # Biomethane potential (BMP)
    }

    for prop_id, units in property_allowed_units.items():
        try:
            prop = MaterialProperty.objects.get(id=prop_id)
        except MaterialProperty.DoesNotExist:
            continue
        prop.allowed_units.set(units)

    # --- fix legacy unit text-field typos ---

    for prop_id, correct_unit_str in [(9, "% / abs DM"), (10, "% / abs DM")]:
        try:
            prop = MaterialProperty.objects.get(id=prop_id)
            prop.unit = correct_unit_str
            prop.save(update_fields=["unit"])
        except MaterialProperty.DoesNotExist:
            continue

    # --- correct MaterialPropertyValue rows that used "No unit" as a placeholder ---

    # Bulk density MPV (id=3) should use Mg/m³
    MaterialPropertyValue.objects.filter(property_id=1, unit__name="No unit").update(
        unit=unit_mg_m3
    )

    # BMP MPV (id=37) should use mL(CH4)/g(oTS)
    MaterialPropertyValue.objects.filter(property_id=46, unit__name="No unit").update(
        unit=unit_bmp
    )


def reverse_configure_allowed_units(apps, schema_editor):
    MaterialProperty = apps.get_model("materials", "MaterialProperty")
    Unit = apps.get_model("properties", "Unit")

    # Remove allowed_units from the 11 properties
    for prop_id in [1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 46]:
        try:
            prop = MaterialProperty.objects.get(id=prop_id)
            prop.allowed_units.clear()
        except MaterialProperty.DoesNotExist:
            continue

    # Restore leading-quote typo in ADF / ADL unit text field
    for prop_id, bad_unit_str in [(9, "'% / abs DM"), (10, "'% / abs DM")]:
        try:
            prop = MaterialProperty.objects.get(id=prop_id)
            prop.unit = bad_unit_str
            prop.save(update_fields=["unit"])
        except MaterialProperty.DoesNotExist:
            continue

    # Revert MPV units back to "No unit"
    no_unit = Unit.objects.filter(name="No unit").first()
    if no_unit:
        from django.db.models import Q

        MaterialPropertyValue = apps.get_model("materials", "MaterialPropertyValue")
        MaterialPropertyValue.objects.filter(
            Q(property_id=1) | Q(property_id=46),
            unit__name__in=["Mg/m³", "mL(CH4)/g(oTS)"],
        ).update(unit=no_unit)


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0017_unique_published_basematerial_name_type"),
        ("properties", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            configure_allowed_units,
            reverse_configure_allowed_units,
        ),
    ]
