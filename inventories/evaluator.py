"""Declarative evaluation of inventory streams.

A stream describes the arising of one material in a catchment as plain data:

    amount = base quantity x factor_1 x factor_2 x ...

The base quantity is measured from a geodataset inside the catchment (feature
count, clipped polygon area, sum of a numeric column) or entered directly.
Base and factors are named terms with a value, an optional standard deviation
and a unit. The names are the extension point for formulas: an expression over
the same symbols can later replace the plain product without changing how
streams are stored.
"""

from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured
from django.db import models

from utils.properties.units import get_unit_registry

from .algorithms import PRODUCTION_DEVIATION_NAME, InventoryAlgorithms


class BaseKind(models.TextChoices):
    FEATURE_COUNT = "feature_count", "Number of features"
    AREA = "area", "Polygon area"
    COLUMN_SUM = "column_sum", "Sum of a numeric column"
    DIRECT = "direct", "Directly entered amount"


DATASET_BASE_KINDS = frozenset(
    (BaseKind.FEATURE_COUNT, BaseKind.AREA, BaseKind.COLUMN_SUM)
)

# The base quantity each legacy generic function measures.
LEGACY_FUNCTION_BASE_KINDS = {
    "count_based_production": BaseKind.FEATURE_COUNT,
    "area_based_production": BaseKind.AREA,
}


def available_base_kinds(geodataset):
    """Base quantities that can be measured from ``geodataset``.

    The geometry decides between counting and area; a column sum needs a
    numeric attribute column.
    """
    kinds = [
        LEGACY_FUNCTION_BASE_KINDS[function_name]
        for function_name in InventoryAlgorithms.generic_functions(geodataset)
    ]
    try:
        has_numeric_column = bool(InventoryAlgorithms.numeric_columns(geodataset))
    except Exception:
        has_numeric_column = False
    if has_numeric_column:
        kinds.append(BaseKind.COLUMN_SUM)
    return kinds


FILTER_OPERATORS = {
    "eq": "is",
    "ne": "is not",
    "in": "is one of",
    "gte": "is at least",
    "lte": "is at most",
}


@dataclass(frozen=True)
class Term:
    """A named quantity of the chain."""

    symbol: str
    value: float
    standard_deviation: float | None = None
    unit: str = ""


@dataclass(frozen=True)
class Condition:
    """Restricts the features of a dataset by one attribute column."""

    column: str
    operator: str
    value: str


@dataclass(frozen=True)
class StreamSpec:
    base_kind: str
    geodataset: object = None
    base_column: str = ""
    base_unit: str = ""
    base: Term | None = None
    filters: tuple = ()
    factors: tuple = ()


def evaluate(spec, catchment_geom):
    """Evaluate ``spec`` inside ``catchment_geom`` (EPSG:4326).

    Returns the result structure consumed by ``Layer.objects.create_or_replace``.
    """
    try:
        measure = _BASE_MEASURES[BaseKind(spec.base_kind)]
    except (KeyError, ValueError):
        raise ImproperlyConfigured(
            f"Unknown base quantity '{spec.base_kind}'."
        ) from None
    if spec.base_kind in DATASET_BASE_KINDS and spec.geodataset is None:
        raise ImproperlyConfigured("This base quantity requires a geodataset.")
    for condition in spec.filters:
        if condition.operator not in FILTER_OPERATORS:
            raise ImproperlyConfigured(
                f"Unknown filter operator '{condition.operator}'."
            )
    return measure(spec, catchment_geom)


def _chain(spec):
    return [
        {
            "name": term.symbol,
            "value": float(term.value),
            "standard_deviation": abs(float(term.standard_deviation))
            if term.standard_deviation
            else None,
            "unit": term.unit or "",
        }
        for term in spec.factors
    ]


def _append_deviation(result, deviation, unit):
    if deviation is not None:
        result["aggregated_values"].append(
            {"name": PRODUCTION_DEVIATION_NAME, "value": deviation, "unit": unit}
        )


def _feature_count(spec, catchment_geom):
    """amount = (features intersecting the catchment) x product(factors)"""
    factors = _chain(spec)
    geometries = InventoryAlgorithms._intersecting_geometries(
        spec.geodataset, catchment_geom, spec.filters
    )
    count = float(len(geometries))
    per_feature, _ = InventoryAlgorithms._production(1.0, "", factors)
    total, unit = InventoryAlgorithms._production(count, "", factors)
    per_feature_deviation = InventoryAlgorithms._production_deviation(1.0, "", factors)
    result = {
        "aggregated_values": [
            {"name": "Count", "value": len(geometries), "unit": ""},
            {"name": "Total production", "value": total, "unit": unit},
        ],
        "aggregated_distributions": [],
        "features": [{"geom": geom, "production": per_feature} for geom in geometries],
        "geom_type": "Point",
    }
    total_deviation = InventoryAlgorithms._production_deviation(count, "", factors)
    _append_deviation(result, total_deviation, unit)
    if total_deviation is not None:
        for feature in result["features"]:
            feature["production_standard_deviation"] = per_feature_deviation
    return result


def _area(spec, catchment_geom):
    """amount = (polygon area clipped to the catchment) x product(factors)"""
    factors = _chain(spec)
    clipped = InventoryAlgorithms._clipped_areas(
        spec.geodataset, catchment_geom, spec.filters
    )
    registry = get_unit_registry()
    total_area_m2 = sum(area for _, area in clipped)
    total_area_ha = (
        registry.Quantity(total_area_m2, "meter ** 2").to("hectare").magnitude
        if registry is not None
        else total_area_m2 / 10000
    )
    result = {
        "aggregated_values": [
            {"name": "Total area", "value": total_area_ha, "unit": "ha"},
        ],
        "aggregated_distributions": [],
        "features": [],
        "geom_type": "MultiPolygon",
    }
    # The unit is derived from the chain even for an empty layer, so it
    # matches populated layers of the same chain.
    _, unit = InventoryAlgorithms._production(0.0, "meter ** 2", factors)
    total = 0.0
    for geom, area in clipped:
        production, _unit = InventoryAlgorithms._production(area, "meter ** 2", factors)
        total += production
        feature = {"geom": geom, "area_ha": area / 10000, "production": production}
        deviation = InventoryAlgorithms._production_deviation(
            area, "meter ** 2", factors
        )
        if deviation is not None:
            feature["production_standard_deviation"] = deviation
        result["features"].append(feature)
    result["aggregated_values"].append(
        {"name": "Total production", "value": total, "unit": unit}
    )
    _append_deviation(
        result,
        InventoryAlgorithms._production_deviation(total_area_m2, "meter ** 2", factors),
        unit,
    )
    return result


def _column_sum(spec, catchment_geom):
    """amount = (sum of a column over features in the catchment) x product(factors)

    A feature that intersects the catchment contributes its whole value.
    """
    if not spec.base_column:
        raise ImproperlyConfigured("A column is required to sum feature values.")
    factors = _chain(spec)
    valued = InventoryAlgorithms._intersecting_values(
        spec.geodataset, catchment_geom, spec.base_column, spec.filters
    )
    base_unit = spec.base_unit or ""
    total_value = sum(value for _, value in valued)
    total, unit = InventoryAlgorithms._production(total_value, base_unit, factors)
    result = {
        "aggregated_values": [
            {"name": "Sum", "value": total_value, "unit": base_unit},
            {"name": "Total production", "value": total, "unit": unit},
        ],
        "aggregated_distributions": [],
        "features": [],
        "geom_type": _GEOMETRY_TYPES.get(
            InventoryAlgorithms.geometry_family(spec.geodataset), "Point"
        ),
    }
    for geom, value in valued:
        production, _unit = InventoryAlgorithms._production(value, base_unit, factors)
        feature = {"geom": geom, "value": value, "production": production}
        deviation = InventoryAlgorithms._production_deviation(value, base_unit, factors)
        if deviation is not None:
            feature["production_standard_deviation"] = deviation
        result["features"].append(feature)
    _append_deviation(
        result,
        InventoryAlgorithms._production_deviation(total_value, base_unit, factors),
        unit,
    )
    return result


def _direct(spec, catchment_geom):
    """amount = entered amount x product(factors), located on the catchment."""
    if spec.base is None:
        raise ImproperlyConfigured("A directly entered amount is required.")
    base = spec.base
    factors = _chain(spec)
    total, unit = InventoryAlgorithms._production(base.value, base.unit, factors)
    deviation = InventoryAlgorithms._production_deviation(
        base.value, base.unit, factors, base.standard_deviation
    )
    feature = {"geom": catchment_geom, "production": total}
    if deviation is not None:
        feature["production_standard_deviation"] = deviation
    result = {
        "aggregated_values": [
            {"name": "Total production", "value": total, "unit": unit},
        ],
        "aggregated_distributions": [],
        "features": [feature],
        "geom_type": catchment_geom.geom_type,
    }
    _append_deviation(result, deviation, unit)
    return result


_GEOMETRY_TYPES = {
    "point": "Point",
    "polygon": "MultiPolygon",
    "line": "MultiLineString",
}

_BASE_MEASURES = {
    BaseKind.FEATURE_COUNT: _feature_count,
    BaseKind.AREA: _area,
    BaseKind.COLUMN_SUM: _column_sum,
    BaseKind.DIRECT: _direct,
}
