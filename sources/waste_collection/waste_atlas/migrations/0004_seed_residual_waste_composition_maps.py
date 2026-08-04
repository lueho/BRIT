from django.db import migrations

NO_DATA_COLOR = "#e0e0e0"
QUARTILE_COLORS = ["#fee5d9", "#fcae91", "#fb6a4a", "#cb181d"]
QUARTILE_CATEGORIES = [
    {"value": "q1", "label": "Quartile 1", "color": QUARTILE_COLORS[0]},
    {"value": "q2", "label": "Quartile 2", "color": QUARTILE_COLORS[1]},
    {"value": "q3", "label": "Quartile 3", "color": QUARTILE_COLORS[2]},
    {"value": "q4", "label": "Quartile 4", "color": QUARTILE_COLORS[3]},
]
DATA_URL = "/waste_collection/api/waste-atlas/residual-waste-composition/"
ANALYSIS_YEAR_TOOLTIP = {"field": "analysis_year", "label": "Analysis year"}
AMOUNT_BASIS_YEAR_TOOLTIP = {
    "field": "amount_basis_year",
    "label": "Amount basis year",
}


def _config(*, title, numeric_field, legend_title, file_base, tooltip_fields):
    return {
        "title": title,
        "dataUrl": DATA_URL,
        "dataField": "_classified",
        "categories": QUARTILE_CATEGORIES,
        "noDataColor": NO_DATA_COLOR,
        "noDataLabel": "No data",
        "legendTitle": legend_title,
        "fileBase": file_base,
        "numericField": numeric_field,
        "quartileColors": QUARTILE_COLORS,
        "enableQuartiles": True,
        "tooltipFields": tooltip_fields,
    }


MAP_CONFIGS = {
    "bw_rw_percentage": _config(
        title="Total biowaste in residual waste",
        numeric_field="bw_rw_percentage",
        legend_title="Share of residual waste (%)",
        file_base="rp_bw_rw_percentage",
        tooltip_fields=[ANALYSIS_YEAR_TOOLTIP],
    ),
    "bw_rw_kg": _config(
        title="Total biowaste in residual waste",
        numeric_field="bw_rw_kg",
        legend_title="Amount (kg/cap/a)",
        file_base="rp_bw_rw_kg",
        tooltip_fields=[ANALYSIS_YEAR_TOOLTIP, AMOUNT_BASIS_YEAR_TOOLTIP],
    ),
    "fwtot_rw_kg": _config(
        title="Total food waste in residual waste",
        numeric_field="fwtot_rw_kg",
        legend_title="Amount (kg/cap/a)",
        file_base="rp_fwtot_rw_kg",
        tooltip_fields=[ANALYSIS_YEAR_TOOLTIP, AMOUNT_BASIS_YEAR_TOOLTIP],
    ),
}


def seed_map_configurations(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    for key, configuration in MAP_CONFIGS.items():
        configuration_model.objects.update_or_create(
            key=key,
            defaults={"configuration": configuration},
        )


def remove_map_configurations(apps, schema_editor):
    configuration_model = apps.get_model(
        "waste_atlas",
        "WasteAtlasMapConfiguration",
    )
    configuration_model.objects.filter(key__in=MAP_CONFIGS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("waste_atlas", "0003_seed_target_waste_category"),
    ]

    operations = [
        migrations.RunPython(
            seed_map_configurations,
            remove_map_configurations,
        )
    ]
