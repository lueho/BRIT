from collections.abc import Mapping

from django.contrib.gis.db.models.fields import GeometryField
from django.contrib.gis.geos import (
    GeometryCollection,
    GEOSGeometry,
    MultiPolygon,
    Polygon,
)
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, models
from django.db.models import QuerySet

from maps.models import Catchment, GeoDataset
from maps.runtime_adapters import (
    IDENTIFIER_PATTERN,
    get_dataset_runtime_adapter,
)
from utils.properties.units import get_unit_registry

from .exceptions import EmptyQueryset


class InventoryAlgorithmsBase:
    @staticmethod
    def avg_point_yield(**kwargs):
        """
        Assignes a global average and standard deviation to all points that are found within the scenario catchment.
        Required keyword arguments:
        catchment_id
        source_model
        point_yield = {'value': <value>, 'standard_deviation': <std>}
        Optional keyword arguments:
        yield_unit = '<unit>' — input unit for point_yield value (default: 'kg').
                      The result is converted to Mg/a (megagrams per year).
        """
        catchment = Catchment.objects.get(id=kwargs.get("catchment_id"))
        model = kwargs.get("source_model")
        clipped = model.objects.filter(geom__intersects=catchment.geom)
        count = clipped.count()
        point_yield = kwargs.get("point_yield")
        total_production = point_yield["value"] * count

        yield_unit = kwargs.get("yield_unit", "kg")
        registry = get_unit_registry()
        if registry is not None:
            try:
                quantity = registry.Quantity(total_production, yield_unit)
                total_production_mg = quantity.to("megagram").magnitude
            except Exception:
                total_production_mg = total_production / 1000
        else:
            total_production_mg = total_production / 1000

        # If result is a gis layer, it must have a list of features under key ['features']. Each feature must have
        # an entry for the key 'geom'
        result = {
            "aggregated_values": [],
            "aggregated_distributions": [],
            "features": [],
        }

        result["aggregated_values"].append(
            {"name": "Count", "value": count, "unit": ""}
        )

        result["aggregated_values"].append(
            {
                "name": "Total production",
                "value": total_production_mg,
                "unit": "Mg/a",
            }
        )

        for feature in clipped:
            result["features"].append(
                {
                    "geom": feature.geom,
                    "point_yield_average": point_yield["value"],
                    "point_yield_standard_deviation": point_yield["standard_deviation"],
                }
            )
        result["aggregated_distributions"] = []

        return result

    @staticmethod
    def avg_area_yield(**kwargs):
        """
        Assignes a global average and standard deviation to park areas that where found in the scenario catchment.
        Required keyword arguments:
        - catchment_id
        - source_model
        - keep_columns: [str]
        - area_yield: {'value': <value>}
        """
        model = kwargs.get("source_model")
        catchment = Catchment.objects.get(id=kwargs.get("catchment_id"))
        input_qs = model.objects.all()
        keep_columns = kwargs.get("keep_columns")
        clipped_polygons = InventoryAlgorithmsBase.clip_polygons(
            input_qs, catchment.geom, keep_columns=keep_columns
        )

        result = {
            "aggregated_values": [],
            "aggregated_distributions": [],
            "features": [],
        }

        result["aggregated_values"].append(
            {"name": "Total area", "value": 0, "unit": "m²"}
        )

        result["aggregated_values"].append(
            {"name": "Total production", "value": 0, "unit": "kg"}
        )

        area_yield = kwargs.get("area_yield")
        for polygon in clipped_polygons:
            result["aggregated_values"][0]["value"] += polygon["area"]
            result["aggregated_values"][1]["value"] += (
                polygon["area"] * area_yield["value"]
            )
            result["features"].append(
                {
                    "geom": polygon["geom"],
                    "area": polygon["area"],
                    "yield_average": polygon["area"] * area_yield["value"],
                }
            )

        return result

    @staticmethod
    def nantes_greenhouse_yield(**kwargs):
        catchment = Catchment.objects.get(id=kwargs.get("catchment_id"))
        model = kwargs.get("source_model")
        clipped = model.objects.filter(geom__intersects=catchment.geom)
        count = clipped.count()

        point_yield = kwargs.get("point_yield")
        total_production = point_yield["value"] * count

        result = {
            "aggregated_values": [],
            "aggregated_distributions": [],
            "features": [],
        }

        result["aggregated_values"].append(
            {"name": "Count", "value": count, "unit": ""}
        )

        result["aggregated_values"].append(
            {"name": "Total production", "value": total_production, "unit": "kg"}
        )

        for feature in clipped:
            result["features"].append(
                {
                    "geom": feature.geom,
                    "point_yield_average": point_yield["value"],
                    "point_yield_standard_deviation": point_yield["standard_deviation"],
                }
            )

        component_list = kwargs.get("materialcomponent-list")
        distribution = kwargs.get("seasonal_distribution")

        for component in component_list:
            result["aggregated_distributions"].append(
                {"name": component, "type": "seasonal", "distribution": distribution}
            )

        return result

    @staticmethod
    def clip_polygons(
        input_qs: QuerySet, mask_geom: GEOSGeometry, keep_columns: [str] = None
    ):
        if not input_qs:
            raise EmptyQueryset

        if not mask_geom:
            raise EmptyQueryset

        # Clean up column names and remove any non existing column names
        # noinspection PyProtectedMember
        input_fields_names = [field.name for field in input_qs.model._meta.get_fields()]
        columns = []
        if keep_columns is not None:
            for column_name in keep_columns:
                if column_name in input_fields_names:
                    columns.append(column_name)

        if columns:
            columns_str = ", ".join(["input." + name for name in columns]) + ","
        else:
            columns_str = ""

        # noinspection PyProtectedMember
        input_table_name = input_qs.model._meta.db_table
        input_pk_name = input_qs.model._meta.pk.attname
        input_ids = (
            "("
            + ", ".join(
                str(id_) for id_ in input_qs.values_list(input_pk_name, flat=True)
            )
            + ")"
        )

        # Query based on: https://postgis.net/docs/ST_Intersection.html
        query = f"""-- noinspection SqlResolve
                        WITH mask AS (SELECT ST_GeomFromEWKT(%s) AS geom)
                        SELECT clipped.*, ST_Area(clipped.geom::geography) AS area
                        FROM (
                            SELECT
                                {columns_str}
                                ST_Multi(
                                    ST_Buffer(ST_Intersection(mask.geom, input.geom), 0.0)
                                ) AS geom
                            FROM (SELECT * FROM {input_table_name} WHERE {input_pk_name} IN {input_ids}) AS input
                            CROSS JOIN mask
                            WHERE ST_Intersects(mask.geom, input.geom)
                            AND NOT ST_IsEmpty(ST_Buffer(ST_Intersection(mask.geom, input.geom), 0.0))) clipped;
                    """

        with connection.cursor() as cursor:
            cursor.execute(query, [mask_geom.ewkt])
            columns = [column[0] for column in cursor.description]
            features = [
                dict(zip(columns, row, strict=False)) for row in cursor.fetchall()
            ]
        # The cursor gets the geometry only as string representation. Create a geometry objects from it with GEOS API
        for feature in features:
            feature["geom"] = GEOSGeometry(feature["geom"])

        return features


GENERIC_MODULE_PATH = "inventories.algorithms"

# Kwargs that wire the run to the scenario context; every other keyword argument
# is treated as a factor in the production chain. ``feature_filter`` restricts
# the features that feed the inventory (encoded as "column=value").
RESERVED_ALGORITHM_KWARGS = frozenset(
    (
        "catchment_id",
        "scenario_id",
        "feedstock_id",
        "geodataset_id",
        "feature_filter",
    )
)

# Equal-area projection used to measure polygon areas of model features.
AREA_MEASUREMENT_SRID = 6933

GENERIC_FUNCTION_LABELS = {
    "count_based_production": "Count-based production",
    "area_based_production": "Area-based production",
}

# Which generic functions a dataset's geometry family supports. Datasets whose
# geometry cannot be classified (mixed collections, unresolvable sources)
# offer all generic functions — the algorithms degrade gracefully.
GEOMETRY_FAMILY_FUNCTIONS = {
    "point": ("count_based_production",),
    "polygon": ("area_based_production",),
}

_GEOMETRY_TYPE_FAMILIES = {
    "POINT": "point",
    "MULTIPOINT": "point",
    "POLYGON": "polygon",
    "MULTIPOLYGON": "polygon",
    "LINESTRING": "line",
    "MULTILINESTRING": "line",
}


class InventoryAlgorithms(InventoryAlgorithmsBase):
    """Generic, dataset-agnostic inventory algorithms.

    Each function resolves the feature source from the ``geodataset_id`` kwarg
    (``InventoryAlgorithm.execute`` injects the algorithm's configured
    ``GeoDataset`` automatically) and supports both model-backed datasets and
    ``local_relation`` datasets.

    Every keyword argument beyond the reserved scenario context
    (:data:`RESERVED_ALGORITHM_KWARGS`) is a factor in the production chain,
    given either as a number or as ``{"value": ..., "standard_deviation": ...,
    "unit": ...}``. Units are pint-aware: the chain is converted to ``Mg/a``
    when possible, then to ``Mg``, otherwise the computed unit is reported.
    """

    @classmethod
    def count_based_production(cls, **kwargs):
        """production = (features intersecting the catchment) x product(factors)"""
        geodataset = cls._resolve_geodataset(kwargs)
        catchment_geom = cls._catchment_geometry(kwargs)
        factors = cls._factors(kwargs)
        feature_filter = cls._feature_filter(kwargs)
        geometries = cls._intersecting_geometries(
            geodataset, catchment_geom, feature_filter
        )

        per_feature, _ = cls._production(1.0, "", factors)
        total, unit = cls._production(float(len(geometries)), "", factors)
        result = {
            "aggregated_values": [
                {"name": "Count", "value": len(geometries), "unit": ""},
                {"name": "Total production", "value": total, "unit": unit},
            ],
            "aggregated_distributions": [],
            "features": [
                {"geom": geom, "production": per_feature} for geom in geometries
            ],
            "geom_type": "Point",
        }
        return result

    @classmethod
    def area_based_production(cls, **kwargs):
        """production = (total clipped polygon area) x product(factors)"""
        geodataset = cls._resolve_geodataset(kwargs)
        catchment_geom = cls._catchment_geometry(kwargs)
        factors = cls._factors(kwargs)
        feature_filter = cls._feature_filter(kwargs)
        clipped = cls._clipped_areas(geodataset, catchment_geom, feature_filter)

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
        total = 0.0
        total_unit = "Mg/a"
        for geom, area in clipped:
            production, unit = cls._production(area, "meter ** 2", factors)
            total_unit = unit
            total += production
            result["features"].append(
                {"geom": geom, "area_ha": area / 10000, "production": production}
            )
        result["aggregated_values"].append(
            {"name": "Total production", "value": total, "unit": total_unit}
        )
        return result

    # -- generic helpers -----------------------------------------------------

    @staticmethod
    def _resolve_geodataset(kwargs):
        geodataset_id = kwargs.get("geodataset_id")
        if geodataset_id is None:
            raise ImproperlyConfigured(
                "Generic inventory algorithms require a 'geodataset_id' "
                "keyword argument."
            )
        return GeoDataset.objects.get(id=geodataset_id)

    @staticmethod
    def _catchment_geometry(kwargs):
        catchment = Catchment.objects.get(id=kwargs.get("catchment_id"))
        geom = catchment.geom
        if geom is None or geom.empty:
            raise ValueError("A catchment boundary is required for evaluation.")
        return geom.transform(4326, clone=True)

    @staticmethod
    def _factors(kwargs):
        factors = []
        for name, raw in kwargs.items():
            if name in RESERVED_ALGORITHM_KWARGS:
                continue
            if isinstance(raw, Mapping):
                value = raw.get("value")
                unit = raw.get("unit") or ""
            else:
                value, unit = raw, ""
            try:
                factors.append({"name": name, "value": float(value), "unit": unit})
            except (TypeError, ValueError):
                raise ImproperlyConfigured(
                    f"Parameter '{name}' is not a numeric factor."
                ) from None
        return factors

    @staticmethod
    def _production(base_magnitude, base_unit, factors):
        """Multiply a base quantity by all factor values.

        Returns ``(value, unit_label)``. With pint available the product is
        converted to ``Mg/a`` first, then ``Mg``; otherwise the chain's
        computed unit is reported. Without pint the magnitudes are multiplied
        verbatim and reported as ``Mg/a``.
        """
        registry = get_unit_registry()
        if registry is not None:
            quantity = registry.Quantity(float(base_magnitude))
            if base_unit:
                quantity = registry.Quantity(float(base_magnitude), base_unit)
            for factor in factors:
                try:
                    factor_quantity = registry.Quantity(factor["value"], factor["unit"])
                except Exception:
                    raise ImproperlyConfigured(
                        f"Unknown unit '{factor['unit']}' for parameter "
                        f"'{factor['name']}'."
                    ) from None
                if factor["unit"]:
                    quantity *= factor_quantity
                else:
                    quantity *= factor["value"]
            for target, label in (("megagram / year", "Mg/a"), ("megagram", "Mg")):
                try:
                    return quantity.to(target).magnitude, label
                except Exception:
                    continue
            return quantity.magnitude, f"{quantity.units:~}"
        value = float(base_magnitude)
        for factor in factors:
            value *= factor["value"]
        return value, "Mg/a"

    @staticmethod
    def _feature_filter(kwargs):
        """Parse the optional feature filter ("column=value").

        Accepts the selection-value dict produced by the execution plan
        (``{"selection": "column=value", ...}``) or a plain string. Returns a
        ``(column, value)`` tuple or None.
        """
        raw = kwargs.get("feature_filter")
        if not raw:
            return None
        spec = (
            raw.get("selection") or raw.get("value") or ""
            if isinstance(raw, Mapping)
            else str(raw)
        )
        column, sep, value = str(spec).partition("=")
        column, value = column.strip(), value.strip()
        if not sep or not column or not value:
            raise ImproperlyConfigured(
                "feature_filter must be given as 'column=value'."
            )
        return column, value

    @classmethod
    def feature_columns(cls, geodataset):
        """Filterable feature attribute columns with sampled distinct values.

        Returns ``[{"name": ..., "values": [...]}]`` for non-geometry,
        non-primary-key columns — e.g. the crop column of a parcels dataset.
        """
        adapter = get_dataset_runtime_adapter(geodataset)
        if getattr(adapter, "uses_local_relation", False):
            return cls._relation_feature_columns(adapter)
        return cls._model_feature_columns(adapter.model)

    _FEATURE_COLUMN_FIELD_TYPES = (
        models.CharField,
        models.TextField,
        models.IntegerField,
        models.BooleanField,
    )

    @classmethod
    def _model_feature_columns(cls, model):
        columns = []
        for field in model._meta.get_fields():
            if (
                not getattr(field, "concrete", False)
                or field.is_relation
                or field.primary_key
                or not isinstance(field, cls._FEATURE_COLUMN_FIELD_TYPES)
            ):
                continue
            values = (
                model.objects.exclude(**{f"{field.name}__isnull": True})
                .order_by(field.name)
                .values_list(field.name, flat=True)
                .distinct()[:51]
            )
            columns.append({"name": field.name, "values": [str(v) for v in values]})
        return columns

    @staticmethod
    def _relation_feature_columns(adapter):
        config = adapter.runtime_configuration
        excluded = {
            config.primary_key_column,
            config.geometry_column,
        }
        columns = []
        for column in adapter._get_existing_columns():
            name = column["column_name"]
            if name in excluded or column["udt_name"] == "geometry":
                continue
            values = adapter._get_distinct_filter_values(name)[:50]
            columns.append({"name": name, "values": [str(v) for v in values]})
        return columns

    @classmethod
    def _validate_feature_filter(cls, adapter, feature_filter):
        """Ensure the filtered column actually exists on the dataset source."""
        if feature_filter is None:
            return
        column, _value = feature_filter
        adapter_getter = getattr(adapter, "uses_local_relation", False)
        if adapter_getter:
            existing = {c["column_name"] for c in adapter._get_existing_columns()}
            if column not in existing:
                raise ImproperlyConfigured(f"Unknown feature filter column '{column}'.")
            if not IDENTIFIER_PATTERN.match(column):
                raise ImproperlyConfigured(f"Invalid feature filter column '{column}'.")
            return
        try:
            adapter.model._meta.get_field(column)
        except Exception:
            raise ImproperlyConfigured(
                f"Unknown feature filter column '{column}'."
            ) from None

    @classmethod
    def _geometry_field(cls, model):
        """Return the model's GeometryField, following a one-level FK
        indirection (e.g. Region.borders -> GeoPolygon.geom)."""
        for field in model._meta.get_fields():
            if isinstance(field, GeometryField):
                return field
        for field in model._meta.get_fields():
            if isinstance(field, models.ForeignKey) and field.related_model:
                for related in field.related_model._meta.get_fields():
                    if isinstance(related, GeometryField):
                        return related
        return None

    @classmethod
    def _geometry_accessor(cls, model):
        """Return the ORM path to the model's geometry ('geom' or e.g.
        'borders__geom' for models that hold geometry on a related object)."""
        for field in model._meta.get_fields():
            if isinstance(field, GeometryField):
                return field.name
        for field in model._meta.get_fields():
            if isinstance(field, models.ForeignKey) and field.related_model:
                for related in field.related_model._meta.get_fields():
                    if isinstance(related, GeometryField):
                        return f"{field.name}__{related.name}"
        raise ImproperlyConfigured(f"{model._meta.label} has no geometry field.")

    # -- geometry family / function discovery --------------------------------

    @staticmethod
    def _family_for_geometry_type(geom_type):
        """Map a PostGIS type name ('POINT', 'ST_MultiPolygon', ...) to a
        geometry family: 'point', 'polygon', 'line' or None."""
        normalized = str(geom_type or "").upper()
        normalized = normalized.removeprefix("ST_")
        return _GEOMETRY_TYPE_FAMILIES.get(normalized)

    @classmethod
    def _relation_geometry_family(cls, adapter):
        """Geometry family of a local_relation dataset, from the PostGIS
        geometry_columns metadata, falling back to sampling actual rows."""
        config = adapter.runtime_configuration
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT type FROM geometry_columns
                WHERE f_table_schema = %s AND f_table_name = %s
                  AND f_geometry_column = %s
                """,
                [
                    config.schema_name,
                    config.relation_name,
                    config.geometry_column,
                ],
            )
            types = [row[0] for row in cursor.fetchall() if row[0]]
            if not types or any(t == "GEOMETRY" for t in types):
                geom_col = connection.ops.quote_name(config.geometry_column)
                cursor.execute(
                    f"SELECT DISTINCT ST_GeometryType(t.{geom_col}) "
                    f"FROM {adapter.relation_identifier} t "
                    f"WHERE t.{geom_col} IS NOT NULL LIMIT 5"
                )
                types = [row[0] for row in cursor.fetchall() if row[0]]
        families = {cls._family_for_geometry_type(t) for t in types}
        families.discard(None)
        return families.pop() if len(families) == 1 else None

    @classmethod
    def geometry_family(cls, geodataset):
        """Return 'point', 'polygon', 'line' or None for a GeoDataset.

        None means the geometry could not be classified — either the dataset
        source cannot be resolved or the geometry column holds mixed types.
        """
        try:
            adapter = get_dataset_runtime_adapter(geodataset)
        except ImproperlyConfigured:
            return None
        if getattr(adapter, "uses_local_relation", False):
            return cls._relation_geometry_family(adapter)
        field = cls._geometry_field(adapter.model)
        if field is None:
            return None
        return cls._family_for_geometry_type(field.geom_type)

    @classmethod
    def generic_functions(cls, geodataset):
        """Return the generic function names applicable to a dataset,
        determined by its geometry family."""
        family = cls.geometry_family(geodataset)
        return list(
            GEOMETRY_FAMILY_FUNCTIONS.get(family, GENERIC_FUNCTION_LABELS.keys())
        )

    @staticmethod
    def _get_feature_geom(obj, accessor):
        for part in accessor.split("__"):
            obj = getattr(obj, part, None)
            if obj is None:
                return None
        return obj

    @classmethod
    def _apply_feature_filter(cls, queryset, adapter, feature_filter):
        """Restrict a model queryset to the features matching the filter."""
        cls._validate_feature_filter(adapter, feature_filter)
        if feature_filter is None:
            return queryset
        column, value = feature_filter
        return queryset.filter(**{column: value})

    @staticmethod
    def _relation_filter_sql(adapter, feature_filter):
        """Return ``(sql_fragment, params)`` restricting a relation query to
        features matching the filter, or ``("", [])``."""
        if feature_filter is None:
            return "", []
        column, value = feature_filter
        quoted = connection.ops.quote_name(column)
        return f" AND t.{quoted} = %s", [value]

    @classmethod
    def _intersecting_geometries(cls, geodataset, catchment_geom, feature_filter=None):
        """Return a list of 4326 geometries of all dataset features that
        intersect the catchment boundary."""
        adapter = get_dataset_runtime_adapter(geodataset)
        if getattr(adapter, "uses_local_relation", False):
            cls._validate_feature_filter(adapter, feature_filter)
            return cls._relation_geometries(adapter, catchment_geom, feature_filter)
        model = adapter.model
        accessor = cls._geometry_accessor(model)
        queryset = model.objects.filter(**{f"{accessor}__intersects": catchment_geom})
        queryset = cls._apply_feature_filter(queryset, adapter, feature_filter)
        geometries = []
        for obj in queryset:
            geom = cls._get_feature_geom(obj, accessor)
            if geom is None or geom.empty:
                continue
            geometries.append(
                geom if geom.srid == 4326 else geom.transform(4326, clone=True)
            )
        return geometries

    @classmethod
    def _clipped_areas(cls, geodataset, catchment_geom, feature_filter=None):
        """Return ``(clipped 4326 MultiPolygon, area in m^2)`` pairs for all
        polygon features intersecting the catchment boundary."""
        adapter = get_dataset_runtime_adapter(geodataset)
        if getattr(adapter, "uses_local_relation", False):
            cls._validate_feature_filter(adapter, feature_filter)
            return cls._relation_clipped_areas(adapter, catchment_geom, feature_filter)
        model = adapter.model
        accessor = cls._geometry_accessor(model)
        queryset = model.objects.filter(**{f"{accessor}__intersects": catchment_geom})
        queryset = cls._apply_feature_filter(queryset, adapter, feature_filter)
        clipped = []
        for obj in queryset:
            geom = cls._get_feature_geom(obj, accessor)
            if geom is None or geom.empty:
                continue
            geom = geom.transform(4326, clone=True)
            parts = cls._polygon_parts(geom.intersection(catchment_geom))
            if not parts:
                continue
            multi = MultiPolygon(parts, srid=4326)
            area = multi.transform(AREA_MEASUREMENT_SRID, clone=True).area
            clipped.append((multi, area))
        return clipped

    @classmethod
    def _polygon_parts(cls, geom):
        if geom is None or geom.empty:
            return []
        if isinstance(geom, Polygon):
            return [geom]
        if isinstance(geom, (MultiPolygon, GeometryCollection)):
            return [polygon for part in geom for polygon in cls._polygon_parts(part)]
        return []

    # -- local_relation backend ----------------------------------------------

    @staticmethod
    def _relation_columns(adapter):
        runtime_configuration = adapter.runtime_configuration
        return (
            adapter.relation_identifier,
            connection.ops.quote_name(runtime_configuration.geometry_column),
            connection.ops.quote_name(runtime_configuration.primary_key_column),
        )

    @classmethod
    def _relation_geometries(cls, adapter, catchment_geom, feature_filter=None):
        relation, geom_col, _pk_col = cls._relation_columns(adapter)
        filter_sql, filter_params = cls._relation_filter_sql(adapter, feature_filter)
        query = f"""-- noinspection SqlResolve
            WITH mask AS (SELECT ST_GeomFromEWKT(%s) AS geom)
            SELECT ST_AsEWKT(ST_Transform(t.{geom_col}, 4326)) AS geom
            FROM {relation} t, mask
            WHERE t.{geom_col} IS NOT NULL
              AND ST_Intersects(ST_Transform(t.{geom_col}, 4326), mask.geom)
              {filter_sql}
            ORDER BY t.{_pk_col}
        """
        with connection.cursor() as cursor:
            cursor.execute(query, [catchment_geom.ewkt, *filter_params])
            return [GEOSGeometry(row[0]) for row in cursor.fetchall()]

    @classmethod
    def _relation_clipped_areas(cls, adapter, catchment_geom, feature_filter=None):
        relation, geom_col, pk_col = cls._relation_columns(adapter)
        filter_sql, filter_params = cls._relation_filter_sql(adapter, feature_filter)
        query = f"""-- noinspection SqlResolve
            WITH mask AS (SELECT ST_GeomFromEWKT(%s) AS geom)
            SELECT ST_AsEWKT(ST_Multi(clipped.geom)) AS geom,
                   ST_Area(clipped.geom::geography) AS area
            FROM (
                SELECT t.{pk_col} AS id,
                       ST_Intersection(mask.geom, ST_Transform(t.{geom_col}, 4326)) AS geom
                FROM {relation} t, mask
                WHERE t.{geom_col} IS NOT NULL
                  AND ST_Intersects(mask.geom, ST_Transform(t.{geom_col}, 4326))
                  {filter_sql}
            ) clipped
            WHERE ST_Dimension(clipped.geom) = 2
            ORDER BY clipped.id
        """
        with connection.cursor() as cursor:
            cursor.execute(query, [catchment_geom.ewkt, *filter_params])
            return [(GEOSGeometry(row[0]), float(row[1])) for row in cursor.fetchall()]
