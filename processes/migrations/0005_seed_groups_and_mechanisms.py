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
        "description": (
            "For TBN the available lignin-containing biomass (e.g. wood and agricultural "
            "residues) is usually of lower quality compared to industrial pulpwood grades. "
            "Fibre production from these biomasses can be performed using a thermo-chemical "
            "disintegration or a chemical delignification process. In most cases, the "
            "resulting fibres contain lignin and have low brightness or a brown colour. "
            "These grades can be used for packaging papers, e.g. corrugated board, in "
            "combination with fibres from waste paper recycling. Fibres with low lignin "
            "content can be further bleached to produce white fibres with high brightness, "
            "suitable for graphic papers. In this case the technology is more complex and "
            "requires larger facilities, often not compatible with TBN.\n\n"
            "Pulping is a general process for converting raw biomass like wood or straw "
            "into pulp, a key input for paper and other fibre-based products. It involves "
            "breaking down the fibrous material through mechanical, chemical, or "
            "semi-chemical means to separate the fibres. The resulting pulp can then be "
            "processed into various grades for different applications. This overview "
            "provides access to specific pulping technologies and related information."
        ),
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

# Maps ProcessType name → {input: [...], output: [...], source_url: str}
PROCESS_MATERIALS = {
    "Anaerobic Digestion": {
        "input": ["Manure", "Organic Waste"],
        "output": ["Biogas", "Digestate"],
        "source_url": "https://www.tech4biowaste.eu/wiki/Anaerobic_digestion",
        "source_title": "Tech4Biowaste: Anaerobic Digestion",
    },
    "Gasification": {
        "input": ["Wood Chips", "Biomass"],
        "output": ["Syngas", "Biochar"],
        "source_url": "https://www.tech4biowaste.eu/wiki/Gasification",
        "source_title": "Tech4Biowaste: Gasification",
    },
    "Pyrolysis": {
        "input": ["Forest Residues", "Straw"],
        "output": ["Bio-oil", "Biochar", "Syngas"],
        "source_url": "https://www.tech4biowaste.eu/wiki/Pyrolysis",
        "source_title": "Tech4Biowaste: Pyrolysis",
    },
    "Composting": {
        "input": ["Organic Waste", "Green Waste"],
        "output": ["Compost"],
        "source_url": "https://www.tech4biowaste.eu/wiki/Composting",
        "source_title": "Tech4Biowaste: Composting",
    },
    "Hydrothermal Processing": {
        "input": ["Wet Biomass"],
        "output": ["Hydrochar", "Process Water"],
        "source_url": "https://www.tech4biowaste.eu/wiki/Hydrothermal_processing",
        "source_title": "Tech4Biowaste: Hydrothermal Processing",
    },
    "Torrefaction": {
        "input": ["Biomass"],
        "output": ["Torrified Biomass"],
        "source_url": "https://www.tech4biowaste.eu/wiki/Torrefaction",
        "source_title": "Tech4Biowaste: Torrefaction",
    },
    "Steam Explosion": {
        "input": ["Lignocellulosic Biomass"],
        "output": ["Exploded Biomass"],
        "source_url": "https://www.tech4biowaste.eu/wiki/Steam_explosion",
        "source_title": "Tech4Biowaste: Steam Explosion",
    },
    "Ultrasonication": {
        "input": ["Sludge"],
        "output": ["Disintegrated Sludge"],
        "source_url": "https://www.tech4biowaste.eu/wiki/Ultrasonication",
        "source_title": "Tech4Biowaste: Ultrasonication",
    },
    "Biocomposite Processing": {
        "input": ["Biopolymers", "Natural Fibres"],
        "output": ["Biocomposite"],
        "source_url": "https://www.tech4biowaste.eu/wiki/Biocomposite_processing",
        "source_title": "Tech4Biowaste: Biocomposite Processing",
    },
}

# Collect all unique material names from the mock data
ALL_MATERIAL_NAMES = sorted(
    {n for info in PROCESS_MATERIALS.values() for n in info["input"] + info["output"]}
)


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

    # Seed materials
    Material = apps.get_model("materials", "Material")
    materials = {}
    for mat_name in ALL_MATERIAL_NAMES:
        obj, _ = Material.objects.get_or_create(
            name=mat_name,
            owner=owner,
            defaults={
                "type": "material",
                "publication_status": "published",
            },
        )
        materials[mat_name] = obj

    # Seed sources and link materials to process types
    Source = apps.get_model("bibliography", "Source")
    for pt_name, info in PROCESS_MATERIALS.items():
        for pt in ProcessType.objects.filter(name=pt_name):
            for mat_name in info["input"]:
                pt.input_materials.add(materials[mat_name])
            for mat_name in info["output"]:
                pt.output_materials.add(materials[mat_name])
            source, _ = Source.objects.get_or_create(
                url=info["source_url"],
                owner=owner,
                defaults={
                    "title": info["source_title"],
                    "type": "website",
                    "publication_status": "published",
                },
            )
            pt.sources.add(source)


def reverse_seed(apps, schema_editor):
    ProcessGroup = apps.get_model("processes", "ProcessGroup")
    MechanismCategory = apps.get_model("processes", "MechanismCategory")
    ProcessType = apps.get_model("processes", "ProcessType")
    Material = apps.get_model("materials", "Material")
    Source = apps.get_model("bibliography", "Source")

    # Clear material/source M2M assignments and delete seeded sources
    source_urls = [info["source_url"] for info in PROCESS_MATERIALS.values()]
    for pt_name in PROCESS_MATERIALS:
        for pt in ProcessType.objects.filter(name=pt_name):
            pt.input_materials.clear()
            pt.output_materials.clear()
            pt.sources.clear()
    Source.objects.filter(url__in=source_urls).delete()
    Material.objects.filter(name__in=ALL_MATERIAL_NAMES).delete()

    # Clear mechanism M2M assignments
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
        ("materials", "0005_alter_analyticalmethod_publication_status_and_more"),
        ("bibliography", "0004_alter_author_publication_status_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_data, reverse_seed),
    ]
