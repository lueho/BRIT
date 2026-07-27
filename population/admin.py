from django.contrib import admin

from .models import (
    PopulationDataset,
    PopulationEstimate,
    PopulationImportRun,
    PopulationObservation,
)


@admin.register(PopulationDataset)
class PopulationDatasetAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "provider",
        "source_code",
        "geographic_scope",
        "temporal_basis",
        "is_canonical",
    )
    search_fields = ("slug", "name", "provider", "source_code")


@admin.register(PopulationImportRun)
class PopulationImportRunAdmin(admin.ModelAdmin):
    list_display = (
        "dataset",
        "extracted_at",
        "upstream_updated_at",
        "created_count",
        "updated_count",
        "unchanged_count",
    )
    list_filter = ("dataset",)


@admin.register(PopulationObservation)
class PopulationObservationAdmin(admin.ModelAdmin):
    list_display = ("dataset", "region", "year", "value", "source_status")
    list_filter = ("dataset", "year", "source_status")
    raw_id_fields = ("region", "import_run")


@admin.register(PopulationEstimate)
class PopulationEstimateAdmin(admin.ModelAdmin):
    list_display = (
        "region",
        "year",
        "value",
        "is_mixed_provenance",
        "is_provisional",
        "calculated_at",
    )
    raw_id_fields = ("region",)
