from django.db import migrations

MECHANISM_CATEGORIES = [
    {
        "name": "Biochemical",
        "description": "Processes driven by biological agents such as microorganisms or enzymes.",
    },
    {
        "name": "Thermochemical",
        "description": "Processes that use heat to convert biomass into fuels, chemicals, or energy.",
    },
    {
        "name": "Physical",
        "description": "Processes based on mechanical or physical forces without chemical change.",
    },
    {
        "name": "Physicochemical",
        "description": "Processes combining physical and chemical mechanisms.",
    },
]

PROCESS_GROUPS = [
    {
        "name": "Pulping",
        "description": "Processes for disintegrating biomass into individual fibres.",
    },
    {
        "name": "Material",
        "description": "Processes for manufacturing composite or advanced bio-based materials.",
    },
]

# Maps ProcessType name → ProcessGroup name
GROUP_ASSIGNMENTS = {
    "Liquor Circulation Digesters for Wood": "Pulping",
    "Horizontal Tube Digester for Straw": "Pulping",
    "Steam Explosion": "Pulping",
    "Biocomposite Processing": "Material",
}

# Maps ProcessType name → list of MechanismCategory names
MECHANISM_ASSIGNMENTS = {
    "Composting": ["Biochemical"],
    "Anaerobic Digestion": ["Biochemical"],
    "Torrefaction": ["Thermochemical"],
    "Hydrothermal Processing": ["Thermochemical"],
    "Pyrolysis": ["Thermochemical"],
    "Gasification": ["Thermochemical"],
    "Ultrasonication": ["Physical"],
    "Biocomposite Processing": ["Physical"],
    "Steam Explosion": ["Physical", "Thermochemical"],
    "Liquor Circulation Digesters for Wood": ["Physicochemical"],
    "Horizontal Tube Digester for Straw": ["Physicochemical"],
}


def seed_data(apps, schema_editor):
    ProcessGroup = apps.get_model("processes", "ProcessGroup")
    MechanismCategory = apps.get_model("processes", "MechanismCategory")
    ProcessType = apps.get_model("processes", "ProcessType")
    User = apps.get_model("auth", "User")

    try:
        owner = User.objects.get(username="admin")
    except User.DoesNotExist:
        owner = User.objects.first()
    if owner is None:
        return

    # Seed ProcessGroups (re-seed since 0003 data may have been lost)
    groups = {}
    for g in PROCESS_GROUPS:
        obj, _ = ProcessGroup.objects.get_or_create(
            name=g["name"],
            owner=owner,
            defaults={
                "description": g["description"],
                "publication_status": "published",
            },
        )
        groups[g["name"]] = obj

    # Seed MechanismCategories
    mechanisms = {}
    for m in MECHANISM_CATEGORIES:
        obj, _ = MechanismCategory.objects.get_or_create(
            name=m["name"],
            owner=owner,
            defaults={
                "description": m["description"],
                "publication_status": "published",
            },
        )
        mechanisms[m["name"]] = obj

    # Clean up stale MechanismCategory records that are actually group concepts
    # (created if old seed migration 0003 data ended up in the renamed table)
    stale_mech_names = [g["name"] for g in PROCESS_GROUPS]
    MechanismCategory.objects.filter(
        name__in=stale_mech_names, process_types__isnull=True
    ).delete()

    # Assign ProcessTypes to groups
    for pt_name, group_name in GROUP_ASSIGNMENTS.items():
        ProcessType.objects.filter(name=pt_name, group__isnull=True).update(
            group=groups[group_name]
        )

    # Assign ProcessTypes to mechanism categories
    for pt_name, mech_names in MECHANISM_ASSIGNMENTS.items():
        for pt in ProcessType.objects.filter(name=pt_name):
            for mech_name in mech_names:
                pt.mechanism_categories.add(mechanisms[mech_name])


def reverse_seed(apps, schema_editor):
    ProcessGroup = apps.get_model("processes", "ProcessGroup")
    MechanismCategory = apps.get_model("processes", "MechanismCategory")
    ProcessType = apps.get_model("processes", "ProcessType")

    # Clear M2M assignments
    for pt_name in MECHANISM_ASSIGNMENTS:
        for pt in ProcessType.objects.filter(name=pt_name):
            pt.mechanism_categories.clear()

    # Clear group assignments
    ProcessType.objects.filter(name__in=GROUP_ASSIGNMENTS.keys()).update(group=None)

    # Delete seeded records
    group_names = [g["name"] for g in PROCESS_GROUPS]
    ProcessGroup.objects.filter(name__in=group_names).delete()

    mech_names = [m["name"] for m in MECHANISM_CATEGORIES]
    MechanismCategory.objects.filter(name__in=mech_names).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("processes", "0004_rename_category_to_group_add_mechanism"),
    ]

    operations = [
        migrations.RunPython(seed_data, reverse_seed),
    ]
