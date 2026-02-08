from django.contrib import admin

from .models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteComponent,
    WasteFlyer,
    WasteStream,
)


@admin.register(Collector)
class CollectorAdmin(admin.ModelAdmin):
    list_display = ("name", "website", "catchment", "owner", "publication_status")
    search_fields = ("name", "description")
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(CollectionSystem)
class CollectionSystemAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(WasteCategory)
class WasteCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(WasteComponent)
class WasteComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(WasteStream)
class WasteStreamAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "owner", "publication_status")
    search_fields = ("name", "category__name")
    list_filter = ("publication_status", "category")
    ordering = ("name",)
    filter_horizontal = ("allowed_materials", "forbidden_materials", "composition")


@admin.register(WasteFlyer)
class WasteFlyerAdmin(admin.ModelAdmin):
    list_display = ("__str__", "url", "url_valid", "owner", "publication_status")
    search_fields = ("url", "title")
    list_filter = ("publication_status", "url_valid")
    ordering = ("url",)


@admin.register(CollectionSeason)
class CollectionSeasonAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "distribution",
        "first_timestep",
        "last_timestep",
        "owner",
        "publication_status",
    )
    list_filter = ("publication_status",)
    ordering = ("first_timestep",)


@admin.register(CollectionFrequency)
class CollectionFrequencyAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status", "type")
    ordering = ("name",)


@admin.register(FeeSystem)
class FeeSystemAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "collector",
        "catchment",
        "collection_system",
        "valid_from",
        "valid_until",
        "owner",
        "publication_status",
    )
    search_fields = ("name", "collector__name", "catchment__name")
    list_filter = ("publication_status", "connection_type", "collection_system")
    ordering = ("name",)
    autocomplete_fields = ("sources",)
    filter_horizontal = ("samples", "flyers", "predecessors")


@admin.register(CollectionPropertyValue)
class CollectionPropertyValueAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "collection",
        "property",
        "average",
        "year",
        "owner",
        "publication_status",
    )
    search_fields = ("collection__name", "property__name")
    list_filter = ("publication_status",)
    ordering = ("collection", "property")
    autocomplete_fields = ("sources",)


@admin.register(AggregatedCollectionPropertyValue)
class AggregatedCollectionPropertyValueAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "property",
        "average",
        "year",
        "owner",
        "publication_status",
    )
    search_fields = ("property__name",)
    list_filter = ("publication_status",)
    ordering = ("property",)
    autocomplete_fields = ("sources",)
    filter_horizontal = ("collections",)
