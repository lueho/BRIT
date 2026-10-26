from django.contrib import admin

from utils.object_management.admin import NamedUserCreatedObjectAdmin, PolicyAdminMixin

from .models import (
    AggregatedCollectionPropertyValue,
    BinConfiguration,
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
)


@admin.register(Collector)
class CollectorAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = ("name", "website", "catchment", "owner", "publication_status")
    search_fields = ("name", "description")


@admin.register(CollectionSystem)
class CollectionSystemAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    pass


@admin.register(BinConfiguration)
class BinConfigurationAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    pass


@admin.register(WasteCategory)
class WasteCategoryAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    pass


@admin.register(WasteComponent)
class WasteComponentAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    pass


@admin.register(WasteFlyer)
class WasteFlyerAdmin(PolicyAdminMixin, admin.ModelAdmin):
    list_display = ("__str__", "url", "url_valid", "owner", "publication_status")
    search_fields = ("url", "title")
    list_filter = ("publication_status", "url_valid")
    ordering = ("url",)


@admin.register(CollectionSeason)
class CollectionSeasonAdmin(PolicyAdminMixin, admin.ModelAdmin):
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
class CollectionFrequencyAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    list_display = ("name", "type", "owner", "publication_status")
    list_filter = ("publication_status", "type")


@admin.register(FeeSystem)
class FeeSystemAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
    pass


@admin.register(Collection)
class CollectionAdmin(PolicyAdminMixin, NamedUserCreatedObjectAdmin):
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
    list_filter = (
        "publication_status",
        "participation_policy",
        "collection_system",
        "bin_configuration",
    )
    autocomplete_fields = ("sources",)
    filter_horizontal = ("samples", "flyers", "predecessors")


@admin.register(CollectionPropertyValue)
class CollectionPropertyValueAdmin(PolicyAdminMixin, admin.ModelAdmin):
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
class AggregatedCollectionPropertyValueAdmin(PolicyAdminMixin, admin.ModelAdmin):
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
