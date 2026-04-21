from collections import Counter, defaultdict
from decimal import Decimal

from utils.properties.models import Unit
from utils.properties.units import UnitConversionError

from .models import MaterialComponent


def get_sample_composition_settings_by_group(sample):
    composition_settings_by_group = {}
    queryset = sample.compositions.select_related(
        "group", "fractions_of"
    ).prefetch_related("shares__component")
    for composition in queryset.order_by("order", "id"):
        composition_settings_by_group.setdefault(composition.group_id, composition)
    return composition_settings_by_group


def get_group_sort_key(group, composition_settings_by_group):
    composition_setting = composition_settings_by_group.get(group.pk)
    if composition_setting is None:
        return (1, group.name.lower(), group.pk)
    return (0, composition_setting.order, group.name.lower(), group.pk)


def get_sorted_component_measurements(
    sample,
    *,
    composition_settings_by_group=None,
    component_measurements=None,
):
    if composition_settings_by_group is None:
        composition_settings_by_group = get_sample_composition_settings_by_group(sample)
    if component_measurements is None:
        component_measurements = (
            sample.component_measurements.select_related(
                "group",
                "component",
                "component__comparable_component",
                "basis_component",
                "analytical_method",
                "unit",
            )
            .prefetch_related("sources")
            .order_by("group__name", "component__name", "id")
        )
    return sorted(
        component_measurements,
        key=lambda measurement: (
            get_group_sort_key(measurement.group, composition_settings_by_group),
            -Decimal(measurement.average),
            measurement.component.name.lower(),
            measurement.pk,
        ),
    )


def get_sample_normalized_compositions(
    sample,
    *,
    component_measurements=None,
    composition_settings_by_group=None,
):
    if composition_settings_by_group is None:
        composition_settings_by_group = get_sample_composition_settings_by_group(sample)
    if component_measurements is None:
        component_measurements = get_sorted_component_measurements(
            sample,
            composition_settings_by_group=composition_settings_by_group,
        )

    measurements_by_group = defaultdict(list)
    for measurement in component_measurements:
        measurements_by_group[measurement.group_id].append(measurement)

    group_ids = set(composition_settings_by_group)
    group_ids.update(measurements_by_group)
    if not group_ids:
        return []

    groups = {}
    for group_id, composition in composition_settings_by_group.items():
        groups[group_id] = composition.group
    for group_measurements in measurements_by_group.values():
        if group_measurements:
            groups[group_measurements[0].group_id] = group_measurements[0].group

    compositions = []
    for group_id in sorted(
        group_ids,
        key=lambda group_pk: get_group_sort_key(
            groups[group_pk],
            composition_settings_by_group,
        ),
    ):
        group = groups[group_id]
        composition_setting = composition_settings_by_group.get(group_id)
        group_measurements = measurements_by_group.get(group_id, [])
        persisted_composition = None
        if composition_setting is not None and composition_setting.shares.exists():
            persisted_composition = composition_setting

        raw_composition = _build_raw_derived_group_composition(
            sample=sample,
            group=group,
            measurements=group_measurements,
            composition_setting=composition_setting,
        )
        if raw_composition is not None:
            if persisted_composition is not None and _compositions_differ(
                raw_composition,
                persisted_composition,
            ):
                raw_composition["warnings"].append(
                    "Raw measurements differ from the saved normalized composition for this group."
                )
                raw_composition["warning_count"] = len(raw_composition["warnings"])
            compositions.append(raw_composition)
            continue

        if persisted_composition is not None:
            fallback_composition = _serialize_persisted_composition(
                persisted_composition,
                sample=sample,
            )
            if group_measurements:
                fallback_composition["warnings"].append(
                    "Raw measurements exist for this group but could not be normalized; using the saved composition as fallback."
                )
                fallback_composition["warning_count"] = len(
                    fallback_composition["warnings"]
                )
            compositions.append(fallback_composition)

    return compositions


def _build_raw_derived_group_composition(
    *, sample, group, measurements, composition_setting
):
    positive_measurements = []
    basis_components = []
    is_dm_basis = True
    grouped_components = defaultdict(list)
    skipped_measurement_count = 0

    for measurement in measurements:
        average = Decimal(measurement.average)
        if average <= 0:
            continue
        positive_measurements.append(measurement)
        if not _is_percent_of_dm_measurement(measurement):
            is_dm_basis = False
        if measurement.basis_component is not None:
            basis_components.append(measurement.basis_component)
        grouped_components[measurement.component].append(measurement)

    if not positive_measurements:
        return None

    other_component = MaterialComponent.objects.other()
    percent_unit = Unit.objects.filter(name="%").first() or Unit(
        name="%", symbol="percent"
    )

    if composition_setting is not None and composition_setting.fractions_of_id:
        reference_component = composition_setting.fractions_of
    elif basis_components:
        basis_counts = Counter(component.pk for component in basis_components)
        reference_component_id = max(
            basis_counts,
            key=lambda component_id: basis_counts[component_id],
        )
        reference_component = next(
            component
            for component in basis_components
            if component.pk == reference_component_id
        )
    else:
        reference_component = MaterialComponent.objects.default()
    display_unit = "% of DM" if is_dm_basis else "%"

    warnings = []
    if len({component.pk for component in basis_components}) > 1:
        warnings.append(
            "Multiple basis components were present; using the most common reference component."
        )

    shares = []
    for component, component_measurements in grouped_components.items():
        component_percent = Decimal("0.0")
        for measurement in component_measurements:
            measurement_value = Decimal(measurement.average)
            if is_dm_basis:
                component_percent += measurement_value
                continue
            converted = _to_weight_percent(
                measurement_value,
                measurement.unit,
                percent_unit,
            )
            if converted is None:
                skipped_measurement_count += 1
                continue
            component_percent += converted

        if component_percent <= 0:
            continue

        shares.append({
            "component": component.pk,
            "component_name": component.name,
            "average": float(component_percent / Decimal("100")),
            "standard_deviation": None,
            "as_percentage": f"{round(component_percent, 1)}{display_unit}",
        })

    if not shares:
        return None

    if skipped_measurement_count:
        warnings.append(
            "Some raw measurements could not be converted to weight percent and were omitted from normalization."
        )

    total_percent = sum(
        (Decimal(str(share["average"])) * Decimal("100") for share in shares),
        Decimal("0.0"),
    )
    if total_percent < Decimal("100"):
        other_gap = Decimal("100") - total_percent
        other_share = next(
            (share for share in shares if share["component"] == other_component.pk),
            None,
        )
        if other_share is not None:
            existing_percent = Decimal(str(other_share["average"])) * Decimal("100")
            updated_percent = existing_percent + other_gap
            other_share["average"] = float(updated_percent / Decimal("100"))
            other_share["as_percentage"] = f"{round(updated_percent, 1)}{display_unit}"
        else:
            shares.append({
                "component": other_component.pk,
                "component_name": other_component.name,
                "average": float(other_gap / Decimal("100")),
                "standard_deviation": None,
                "as_percentage": f"{round(other_gap, 1)}{display_unit}",
            })
        warnings.append(
            "Raw measurements did not sum to 100%; the remaining fraction was assigned to Other."
        )

    shares.sort(
        key=lambda share: (
            share["component"] == other_component.pk,
            0 if share["component"] == other_component.pk else -share["average"],
            share["component_name"].lower(),
        )
    )

    return {
        "id": f"derived-{group.pk}",
        "group": group.pk,
        "group_name": group.name,
        "sample": sample.pk,
        "fractions_of": reference_component.pk,
        "fractions_of_name": reference_component.name,
        "shares": shares,
        "is_derived": True,
        "origin": "raw_derived",
        "warnings": warnings,
        "warning_count": len(warnings),
        "settings_pk": composition_setting.pk
        if composition_setting is not None
        else None,
    }


def _serialize_persisted_composition(composition, *, sample):
    other_component = MaterialComponent.objects.other()
    ordered_shares = list(composition.shares.exclude(component=other_component))
    other_share = composition.shares.filter(component=other_component).first()
    if other_share is not None:
        ordered_shares.append(other_share)
    return {
        "id": composition.pk,
        "group": composition.group.pk,
        "group_name": composition.group.name,
        "sample": sample.pk,
        "fractions_of": composition.fractions_of.pk
        if composition.fractions_of_id
        else None,
        "fractions_of_name": composition.fractions_of.name
        if composition.fractions_of_id
        else "",
        "shares": [
            {
                "component": share.component.pk,
                "component_name": share.component.name,
                "average": share.average,
                "standard_deviation": share.standard_deviation,
                "as_percentage": share.as_percentage,
            }
            for share in ordered_shares
        ],
        "is_derived": False,
        "origin": "persisted_fallback",
        "warnings": [],
        "warning_count": 0,
        "settings_pk": composition.pk,
    }


def _compositions_differ(raw_composition, persisted_composition):
    raw_fractions_of = raw_composition.get("fractions_of")
    persisted_fractions_of = (
        persisted_composition.fractions_of.pk
        if persisted_composition.fractions_of_id
        else None
    )
    if raw_fractions_of != persisted_fractions_of:
        return True

    raw_shares = {
        share["component"]: Decimal(str(share["average"])).quantize(Decimal("0.000001"))
        for share in raw_composition["shares"]
    }
    persisted_shares = {
        share.component_id: share.average.quantize(Decimal("0.000001"))
        for share in persisted_composition.shares.all()
    }
    return raw_shares != persisted_shares


def _normalize_unit_name(unit):
    return (getattr(unit, "name", "") or "").strip().lower().replace(" ", "")


def _normalize_component_name(component):
    return (getattr(component, "name", "") or "").strip().lower().replace(" ", "")


def _is_percent_of_dm_measurement(measurement):
    unit_name = _normalize_unit_name(measurement.unit)
    basis_name = _normalize_component_name(measurement.basis_component)
    return unit_name in {"%", "percent"} and basis_name in {"dm", "drymatter"}


def _to_weight_percent(value, unit, percent_unit):
    if percent_unit is None:
        return None
    try:
        converted_value = unit.convert(value, percent_unit)
    except UnitConversionError:
        return None
    return Decimal(str(converted_value))
