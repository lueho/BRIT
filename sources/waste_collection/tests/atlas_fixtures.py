"""Test-only Waste Atlas fixture helpers.

Preserved test databases can miss the seeded ``WasteAtlasMapConfiguration``
rows and their later amendments.  These fixtures replay the same migration
``RunPython`` operations in order rather than relying on production
bootstrap or a snapshot of the initial seed state.
"""

from importlib import import_module

from django.apps import apps
from django.db import migrations

ATLAS_CONFIG_MIGRATIONS = (
    "0002_seed_map_configurations",
    "0003_seed_target_waste_category",
    "0004_drop_file_base_from_map_configurations",
    "0004_seed_residual_waste_composition_maps",
    "0006_add_residual_collection_amount_acpv_overlay",
    "0007_add_waste_ratio_aggregated_overlay",
    "0008_drop_redundant_no_data_color",
    "0013_centralize_acpv_marker_appearance",
    "0014_seed_rp_map_configurations",
    "0015_merge_legend_flow_and_rp_configurations",
    "0016_distinguish_no_collection_from_no_door_to_door",
    "0017_disable_connection_rate_quartiles",
    "0018_configure_connection_rate_boundaries",
    "0019_include_all_connection_rates_in_quartiles",
    "0020_reclassify_min_bin_sizes",
    "0021_hide_absent_min_bin_size_categories",
    "0022_add_access_control_legend_note",
    "0023_add_organic_amount_no_collection",
    "0024_group_access_control_export_legend",
    "0025_compact_system_access_control_legend",
    "0026_add_organic_ratio_no_collection",
    "0027_move_stored_urls_to_atlas_prefix",
)


def seed_atlas_map_configurations():
    for name in ATLAS_CONFIG_MIGRATIONS:
        module = import_module(
            f"sources.waste_collection.waste_atlas.migrations.{name}"
        )
        for operation in module.Migration.operations:
            if isinstance(operation, migrations.RunPython):
                operation.code(apps, None)
