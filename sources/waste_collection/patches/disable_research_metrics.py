"""Disable expensive metric loading on the research list serializer."""

from __future__ import annotations

from collections import OrderedDict

from sources.waste_collection import serializers as wc_serializers


def _patched_collection_flat_serializer_to_representation(self, instance):
    representation = super(wc_serializers.CollectionFlatSerializer, self).to_representation(  # type: ignore[name-defined]
        instance
    )

    ordered_representation = OrderedDict()

    for field in self.Meta.fields:  # type: ignore[attr-defined]
        ordered_representation[field] = representation.get(field, None)
        if field == "nuts_or_lau_id":
            try:
                region = instance.catchment.region
            except AttributeError:
                region = None
            if region is not None:
                nuts_hierarchy = wc_serializers._get_nuts_hierarchy(region)
                for level in sorted(nuts_hierarchy):
                    nuts_id, nuts_name = nuts_hierarchy[level]
                    ordered_representation[f"nuts_{level}_id"] = nuts_id
                    ordered_representation[f"nuts_{level}_name"] = nuts_name

    region_attributes = ["Population", "Population density"]
    try:
        region = instance.catchment.region
    except AttributeError:
        region = None
    if region is not None:
        for attr_name in region_attributes:
            col_prefix = attr_name.lower().replace(" ", "_")
            rav_qs = (
                region.regionattributevalue_set.filter(property__name=attr_name)
                .select_related("property", "unit")
                .order_by("date")
            )
            for rav in rav_qs:
                year = rav.date.year if rav.date else None
                col = f"{col_prefix}_{year}" if year else col_prefix
                ordered_representation[col] = rav.value
                unit = rav.measurement_unit_label
                ordered_representation[f"{col}_unit"] = unit if unit else ""

    if getattr(self, "include_collection_metrics", True):
        additional_properties = [
            "specific waste collected",
            "total waste collected",
            "Connection rate",
        ]
        user = (
            getattr(self.context.get("request"), "user", None) if self.context else None
        )
        for property_name in additional_properties:
            specific_property = wc_serializers.Property.objects.filter(  # type: ignore[attr-defined]
                name=property_name
            ).first()
            if not specific_property:
                continue

            values = [
                value
                for value in instance.collectionpropertyvalues_for_display(user=user)
                if value.property_id == specific_property.pk
            ]

            if not values:
                values = [
                    value
                    for value in instance.aggregatedcollectionpropertyvalues_for_display(
                        user=user
                    )
                    if value.property_id == specific_property.pk
                ]
                is_aggregated = bool(values)
            else:
                is_aggregated = False

            for value in values:
                column_name = f"{property_name.lower().replace(' ', '_')}_{value.year}"
                ordered_representation[column_name] = value.average
                ordered_representation[f"{column_name}_unit"] = (
                    str(value.unit) if value.unit else ""
                )
                if is_aggregated:
                    ordered_representation["aggregated"] = True

    return ordered_representation


def _patch_collection_serializers() -> None:
    if getattr(
        wc_serializers.CollectionFlatSerializer, "_metrics_patch_applied", False
    ):
        return

    wc_serializers.CollectionFlatSerializer.to_representation = (  # type: ignore[assignment]
        _patched_collection_flat_serializer_to_representation
    )
    wc_serializers.CollectionFlatSerializer._metrics_patch_applied = True  # type: ignore[attr-defined]
    wc_serializers.CollectionResearchSerializer.include_collection_metrics = False


_patch_collection_serializers()
