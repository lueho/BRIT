"""Give the Rhineland-Palatinate collection maps their own stored configuration.

Those four maps classify their catchments differently from the shared themes
(annual counts and count ratios instead of weekly/biweekly classes), so they
used to override categories, legend title and transform in ``pages.py``. Page
overrides win over the stored configuration, which made the maps ignore what
maintainers edited in the configuration UI. Their configuration now lives in the
database like every other map's.
"""

from django.db import migrations

# Fields the region configuration keeps from the shared theme it is derived
# from, so a maintainer edit made before this migration is not dropped.
# ``numericField`` also drives the year-comparison map, which shows how much a
# value changed only when it knows which field holds it.
INHERITED_KEYS = (
    "title",
    "dataUrl",
    "dataField",
    "noDataLabel",
    "numericField",
    "exportLegendTitle",
)

NO_COLLECTION_LABEL = "No separate door-to-door biowaste collection"

COLLECTION_COUNT_CATEGORIES = [
    {"value": "under_13", "label": "< 13", "color": "#fdd0a2"},
    {"value": "13", "label": "13", "color": "#f7fbff"},
    {"value": "14_25", "label": "14 - 25", "color": "#c6dbef"},
    {"value": "26", "label": "26", "color": "#9ecae1"},
    {"value": "27_39", "label": "27 - 39", "color": "#6baed6"},
    {"value": "40_51", "label": "40 - 51", "color": "#3182bd"},
    {"value": "52", "label": "52", "color": "#08519c"},
    {"value": "over_52", "label": "> 52", "color": "#08306b"},
]

# ``colorRef`` takes the fill from ``WasteAtlasRenderingSettings`` at render
# time, so these entries follow the atlas-wide no-collection colour.
NO_COLLECTION_REF = {"colorRef": "no_collection"}

RP_CONFIGURATIONS = {
    "rp_combined_frequency": {
        "derived_from": "combined_frequency",
        "configuration": {
            "legendTitle": "Collection frequency structure: Biowaste / Residual waste",
            "legendColumns": 2,
            "exportLegendColumns": 2,
            "exportLegendItemFlow": "row",
            "showOnlyPresentCategories": True,
            "transformName": "combinedFrequency",
            "categories": [
                {
                    "value": "bio_seasonal_res_flexible",
                    "label": "SEASONAL / FLEXIBLE",
                    "color": "#2e8b57",
                },
                {
                    "value": "bio_flexible_res_flexible",
                    "label": "FLEXIBLE / FLEXIBLE",
                    "color": "#4169e1",
                },
                {
                    "value": "bio_fixed_res_flexible",
                    "label": "FIXED / FLEXIBLE",
                    "color": "#9ecae1",
                },
                {
                    "value": "bio_seasonal_res_fixed",
                    "label": "SEASONAL / FIXED",
                    "color": "#66cdaa",
                },
                {
                    "value": "bio_flexible_res_fixed",
                    "label": "FLEXIBLE / FIXED",
                    "color": "#e08840",
                },
                {
                    "value": "bio_fixed_res_fixed",
                    "label": "FIXED / FIXED",
                    "color": "#6a51a3",
                },
                {
                    "value": "no_bio_collection",
                    "label": NO_COLLECTION_LABEL.upper(),
                    **NO_COLLECTION_REF,
                },
            ],
        },
    },
    "rp_residual_collection_count": {
        "derived_from": "residual_collection_count",
        "configuration": {
            "legendTitle": "Annual residual waste collection count",
            "enableQuartiles": False,
            "showOnlyPresentCategories": True,
            "transformName": "rpResidualCollectionCount",
            "categories": COLLECTION_COUNT_CATEGORIES,
        },
    },
    "rp_biowaste_collection_count": {
        "derived_from": "biowaste_collection_count",
        "configuration": {
            "legendTitle": "Annual biowaste collection count",
            "enableQuartiles": False,
            "showOnlyPresentCategories": True,
            "transformName": "rpBiowasteCollectionCount",
            "categories": [
                *COLLECTION_COUNT_CATEGORIES,
                {
                    "value": "no_door_to_door",
                    "label": NO_COLLECTION_LABEL,
                    **NO_COLLECTION_REF,
                },
            ],
        },
    },
    "rp_collection_count_ratio": {
        "derived_from": "collection_count_ratio",
        "configuration": {
            "legendTitle": "Annual collection count ratio - Biowaste : Residual waste",
            "showOnlyPresentCategories": True,
            "transformName": "rpCollectionCountRatio",
            "categories": [
                {"value": "two_to_one", "label": "2:1", "color": "#1b9e77"},
                {
                    "value": "between_two_and_one",
                    "label": "< 2:1 > 1:1",
                    "color": "#7570b3",
                },
                {"value": "one_to_one", "label": "1:1", "color": "#d95f02"},
                {"value": "below_one_to_one", "label": "< 1:1", "color": "#a6761d"},
                {
                    "value": "no_bio",
                    "label": NO_COLLECTION_LABEL,
                    **NO_COLLECTION_REF,
                },
            ],
        },
    },
}


def seed_rp_map_configurations(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")

    for key, definition in RP_CONFIGURATIONS.items():
        base = dict(
            configuration_model.objects.values_list("configuration", flat=True).get(
                key=definition["derived_from"]
            )
        )
        configuration = {
            inherited: base[inherited]
            for inherited in INHERITED_KEYS
            if inherited in base
        }
        configuration.update(definition["configuration"])
        configuration_model.objects.update_or_create(
            key=key,
            defaults={"configuration": configuration},
        )


def remove_rp_map_configurations(apps, schema_editor):
    configuration_model = apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    configuration_model.objects.filter(key__in=RP_CONFIGURATIONS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0013_centralize_acpv_marker_appearance"),
    ]

    operations = [
        migrations.RunPython(
            seed_rp_map_configurations,
            remove_rp_map_configurations,
        ),
    ]
