from collections import defaultdict
from decimal import Decimal

from utils.properties.units import UnitConversionError, convert_weight_fraction_value

from .models import MaterialComponent, MeasurementValueQualifier

WARNING_MULTIPLE_BASIS_COMPONENTS = "multiple_basis_components"
WARNING_AGGREGATE_COMPONENTS_EXCLUDED = "aggregate_components_excluded"
WARNING_INVALID_UNITS = "invalid_units"
WARNING_REMAINING_FRACTION_ASSIGNED_TO_OTHER = "remaining_fraction_assigned_to_other"
WARNING_SHARES_SCALED_TO_100 = "shares_scaled_to_100"
WARNING_LEGACY_OTHER_IGNORED = "legacy_other_measurements_ignored"


def get_sample_composition_settings_by_group(sample):
    composition_settings_by_group = {}
    queryset = sample.compositions.select_related("group", "fractions_of")
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
            _measurement_sort_value(measurement),
            measurement.component.name.lower(),
            measurement.pk,
        ),
    )


def _measurement_sort_value(measurement):
    value = Decimal(str(measurement.average))
    return -value if value.is_finite() else Decimal("0")


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
        raw_composition = _build_raw_derived_group_composition(
            sample=sample,
            group=group,
            measurements=group_measurements,
            composition_setting=composition_setting,
        )
        if raw_composition is not None:
            compositions.append(raw_composition)

    return compositions


def _unavailable_group_composition(sample, group, composition_setting, code, message):
    return {
        "id": f"derived-{group.pk}",
        "group": group.pk,
        "group_name": group.name,
        "sample": sample.pk,
        "fractions_of": None,
        "fractions_of_name": None,
        "shares": [],
        "share_total_percent": None,
        "is_derived": True,
        "origin": "raw_derived",
        "normalization_status": "unavailable",
        "warnings": [message],
        "warning_codes": [code],
        "warning_count": 1,
        "settings_pk": composition_setting.pk
        if composition_setting is not None
        else None,
    }


def _build_raw_derived_group_composition(
    *, sample, group, measurements, composition_setting
):
    measurements = list(measurements)
    if not measurements:
        return None
    other_component = MaterialComponent.objects.other()
    excluded_aggregate_names = set()
    observations = []
    for measurement in measurements:
        if measurement.component_id == other_component.pk:
            continue
        if measurement.component.is_aggregate:
            excluded_aggregate_names.add(measurement.component.name)
            continue
        observations.append(measurement)
    if not observations:
        return None

    def unavailable(code, message):
        return _unavailable_group_composition(
            sample, group, composition_setting, code, message
        )

    if not group.is_compositional:
        return unavailable(
            "non_compositional_group",
            "This analytical group is non-compositional. Raw measurements are shown without normalization.",
        )
    bases = {measurement.basis_component_id for measurement in observations}
    if len(bases) > 1:
        return unavailable(
            WARNING_MULTIPLE_BASIS_COMPONENTS,
            "Measurements have different or missing bases. Separate them into compatible analytical groups before normalization.",
        )
    observed_basis = next(iter(bases))
    if (
        composition_setting is not None
        and composition_setting.fractions_of_id
        and observed_basis is not None
        and composition_setting.fractions_of_id != observed_basis
    ):
        return unavailable(
            "configured_basis_mismatch",
            "The configured composition basis differs from the measurement basis. No basis conversion has been applied.",
        )
    if len({measurement.component_id for measurement in observations}) != len(
        observations
    ):
        return unavailable(
            "repeated_component_measurements",
            "This group contains repeated component observations. Resolve their analytical context or select observations before normalization.",
        )
    zero_qualifiers = {
        MeasurementValueQualifier.LESS_THAN,
        MeasurementValueQualifier.BELOW_DETECTION_LIMIT,
    }
    censored_count = 0
    for measurement in observations:
        if measurement.value_qualifier not in {
            MeasurementValueQualifier.EXACT,
            *zero_qualifiers,
        }:
            return unavailable(
                "unsupported_value_qualifier",
                "This group contains qualified values without an agreed aggregation policy. Raw measurements remain unchanged.",
            )
        numbers = (
            measurement.average,
            measurement.standard_deviation,
            measurement.detection_limit,
        )
        if any(
            value is not None
            and (not Decimal(str(value)).is_finite() or Decimal(str(value)) < 0)
            for value in numbers
        ):
            return unavailable(
                "invalid_measurement_value",
                "This group contains a negative or non-finite concentration, uncertainty, or detection limit. Review the raw measurements before normalization.",
            )
        try:
            percentage = to_weight_percent(
                Decimal(str(measurement.average)), measurement.unit
            )
        except UnitConversionError:
            return unavailable(
                WARNING_INVALID_UNITS,
                "This group contains a unit that is not a mass fraction. Such observations belong in property measurements.",
            )
        if percentage > 100:
            return unavailable(
                "invalid_mass_fraction",
                "This group contains an individual mass fraction above 100%. Review the raw measurements before normalization.",
            )
        censored_count += measurement.value_qualifier in zero_qualifiers

    positive_measurements = []
    basis_components = []
    is_dm_basis = True
    grouped_components = defaultdict(list)
    invalid_unit_names = set()
    legacy_other_count = 0

    for measurement in measurements:
        average = (
            Decimal("0")
            if measurement.value_qualifier in zero_qualifiers
            else Decimal(measurement.average)
        )
        if average <= 0:
            continue
        if measurement.component_id == other_component.pk:
            legacy_other_count += 1
            continue
        if measurement.component.is_aggregate:
            excluded_aggregate_names.add(measurement.component.name)
            continue
        if not _is_dry_matter_basis(measurement):
            is_dm_basis = False
        positive_measurements.append(measurement)
        if measurement.basis_component is not None:
            basis_components.append(measurement.basis_component)
        grouped_components[measurement.component].append(measurement)

    if not positive_measurements:
        if censored_count:
            return unavailable(
                "censored_values_approximated_as_zero",
                "Detection-limit observations are approximated as zero for aggregation; no positive exact measurements remain. Raw values are unchanged.",
            )
        return None

    if composition_setting is not None and composition_setting.fractions_of_id:
        reference_component = composition_setting.fractions_of
    elif basis_components:
        reference_component = basis_components[0]
    else:
        reference_component = MaterialComponent.objects.default()
    display_unit = "% of DM" if is_dm_basis else "%"

    warnings = []
    warning_codes = []
    if censored_count:
        warnings.append(
            f"{censored_count} detection-limit observation(s) were approximated as zero for aggregation; their stored values are unchanged."
        )
        warning_codes.append("censored_values_approximated_as_zero")
    if excluded_aggregate_names:
        warnings.append(
            "Aggregate components were excluded from the normalized shares: "
            + ", ".join(sorted(excluded_aggregate_names))
            + "."
        )
        warning_codes.append(WARNING_AGGREGATE_COMPONENTS_EXCLUDED)
    if legacy_other_count:
        warning_codes.append(WARNING_LEGACY_OTHER_IGNORED)

    shares = []
    for component, component_measurements in grouped_components.items():
        component_percent = Decimal("0.0")
        for measurement in component_measurements:
            try:
                component_percent += to_weight_percent(
                    Decimal(measurement.average), measurement.unit
                )
            except UnitConversionError:
                invalid_unit_names.add(str(measurement.unit))

        if component_percent <= 0:
            continue

        shares.append(
            {
                "component": component.pk,
                "component_name": component.name,
                "average": float(component_percent / Decimal("100")),
                "standard_deviation": None,
                "as_percentage": f"{round(component_percent, 1)}{display_unit}",
            }
        )

    if not shares:
        return None

    if invalid_unit_names:
        warnings.append(
            "Measurements with non weight-fraction units could not be normalized: "
            + ", ".join(sorted(invalid_unit_names))
            + ". Correct their unit to include them."
        )
        warning_codes.append(WARNING_INVALID_UNITS)

    total_percent = sum(
        (Decimal(str(share["average"])) * Decimal("100") for share in shares),
        Decimal("0.0"),
    )
    if total_percent > Decimal("100"):
        for share in shares:
            scaled_percent = (
                Decimal(str(share["average"])) * Decimal("100") / total_percent * 100
            )
            share["average"] = float(scaled_percent / Decimal("100"))
            share["as_percentage"] = f"{round(scaled_percent, 1)}{display_unit}"
        warning_codes.append(WARNING_SHARES_SCALED_TO_100)
    elif total_percent < Decimal("100"):
        other_gap = Decimal("100") - total_percent
        shares.append(
            {
                "component": other_component.pk,
                "component_name": other_component.name,
                "average": float(other_gap / Decimal("100")),
                "standard_deviation": None,
                "as_percentage": f"{round(other_gap, 1)}{display_unit}",
            }
        )
        warning_codes.append(WARNING_REMAINING_FRACTION_ASSIGNED_TO_OTHER)

    shares.sort(
        key=lambda share: (
            share["component"] == other_component.pk,
            0 if share["component"] == other_component.pk else -share["average"],
            share["component_name"].lower(),
        )
    )
    for share in shares:
        share["percent"] = round(share["average"] * 100, 1)
    share_total_percent = round(sum(share["average"] * 100 for share in shares), 1)

    return {
        "id": f"derived-{group.pk}",
        "group": group.pk,
        "group_name": group.name,
        "sample": sample.pk,
        "fractions_of": reference_component.pk,
        "fractions_of_name": reference_component.name,
        "shares": shares,
        "share_total_percent": share_total_percent,
        "is_derived": True,
        "origin": "raw_derived",
        "normalization_status": "normalized",
        "warnings": warnings,
        "warning_codes": warning_codes,
        "warning_count": len(warnings),
        "settings_pk": composition_setting.pk
        if composition_setting is not None
        else None,
    }


def _normalize_component_name(component):
    return (getattr(component, "name", "") or "").strip().lower().replace(" ", "")


def _is_dry_matter_basis(measurement):
    basis_name = _normalize_component_name(measurement.basis_component)
    return basis_name in {"dm", "drymatter"}


def to_weight_percent(value, unit):
    """Express a weight-fraction measurement in percent, whatever its unit."""
    for token in (getattr(unit, "symbol", ""), getattr(unit, "name", "")):
        try:
            return convert_weight_fraction_value(value, token, "%")
        except UnitConversionError:
            continue
    raise UnitConversionError(f"'{unit}' is not a weight-fraction unit.")
