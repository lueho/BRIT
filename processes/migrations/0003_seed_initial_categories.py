from django.db import migrations


INITIAL_CATEGORIES = [
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
    {
        "name": "Material",
        "description": "Processes for manufacturing composite or advanced bio-based materials.",
    },
    {
        "name": "Pulping",
        "description": "Processes for disintegrating biomass into individual fibres.",
    },
]


def seed_categories(apps, schema_editor):
    ProcessCategory = apps.get_model("processes", "ProcessCategory")
    User = apps.get_model("auth", "User")
    try:
        owner = User.objects.get(username="admin")
    except User.DoesNotExist:
        owner = User.objects.first()
    if owner is None:
        return
    for cat in INITIAL_CATEGORIES:
        ProcessCategory.objects.get_or_create(
            name=cat["name"],
            owner=owner,
            defaults={
                "description": cat["description"],
                "publication_status": "published",
            },
        )


def reverse_seed(apps, schema_editor):
    ProcessCategory = apps.get_model("processes", "ProcessCategory")
    names = [c["name"] for c in INITIAL_CATEGORIES]
    ProcessCategory.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("processes", "0002_processcategory_processtype_delete_apppermission"),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_seed),
    ]
