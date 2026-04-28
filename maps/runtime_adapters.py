import json
import re
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.http import Http404

from maps.filters import NutsRegionFilterSet
from maps.models import NutsRegion
from sources.registry import get_source_domain_dataset_runtime_compatibility

LEGACY_DATASET_RUNTIME_COMPATIBILITY = {
    "NutsRegion": {
        "model": NutsRegion,
        "filterset_class": NutsRegionFilterSet,
        "template_name": "nuts_region_map.html",
        "features_api_basename": "api-nuts-region",
        "apply_user_visibility_filter": True,
    }
}

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_LOCAL_RELATION_ROWS = 1000


@dataclass(frozen=True)
class DatasetRuntimeAdapter:
    dataset: object
    runtime_model_name: str
    model: type
    filterset_class: type
    template_name: str
    features_api_basename: str
    apply_user_visibility_filter: bool = True

    def configure_view(self, view, *, template_name=None):
        view.model = self.model
        view.filterset_class = self.filterset_class
        view.template_name = template_name or self.template_name
        view.apply_user_visibility_filter = self.apply_user_visibility_filter
        view.model_name = self.runtime_model_name
        view.features_layer_api_basename = self.features_api_basename

    def get_visible_column_policies(self):
        return list(
            self.dataset.column_policies.filter(is_visible=True).order_by("column_name")
        )

    @staticmethod
    def get_policy_label(policy):
        return policy.display_label or policy.column_name.replace("_", " ").title()

    @staticmethod
    def get_column_value(obj, column_name):
        value = obj
        for attr in column_name.split("__"):
            value = getattr(value, attr, None)
            if value is None:
                return ""
        return value


class LocalRelationRecord:
    def __init__(self, pk, label, values):
        self.pk = pk
        self._label = label
        self._values = values

    def __getattr__(self, name):
        try:
            return self._values[name]
        except KeyError as err:
            raise AttributeError(name) from err

    def __str__(self):
        return str(self._label or self.pk)


@dataclass(frozen=True)
class LocalRelationDatasetRuntimeAdapter:
    dataset: object
    runtime_configuration: object
    uses_local_relation: bool = True
    apply_user_visibility_filter: bool = False

    def __post_init__(self):
        missing_fields = [
            field_name
            for field_name in (
                "schema_name",
                "relation_name",
                "geometry_column",
                "primary_key_column",
            )
            if not getattr(self.runtime_configuration, field_name)
        ]
        if missing_fields:
            raise ImproperlyConfigured(
                "Local relation dataset runtime configuration is missing: "
                f"{', '.join(missing_fields)}."
            )
        self._validate_identifier(self.runtime_configuration.schema_name)
        self._validate_identifier(self.runtime_configuration.relation_name)
        self._validate_identifier(self.runtime_configuration.geometry_column)
        self._validate_identifier(self.runtime_configuration.primary_key_column)
        if self.runtime_configuration.label_field:
            self._validate_identifier(self.runtime_configuration.label_field)

    @staticmethod
    def _validate_identifier(identifier):
        if not IDENTIFIER_PATTERN.fullmatch(identifier):
            raise ImproperlyConfigured(
                f"Invalid local relation identifier: {identifier}."
            )

    @property
    def relation_identifier(self):
        return ".".join(
            [
                connection.ops.quote_name(self.runtime_configuration.schema_name),
                connection.ops.quote_name(self.runtime_configuration.relation_name),
            ]
        )

    @property
    def features_api_basename(self):
        return self.runtime_configuration.features_api_basename

    def configure_view(self, view, *, template_name=None):
        view.model = None
        view.filterset_class = None
        view.template_name = template_name or "filtered_map.html"
        view.apply_user_visibility_filter = self.apply_user_visibility_filter
        view.model_name = ""
        view.features_layer_api_basename = self.features_api_basename

    def get_visible_column_policies(self):
        return list(
            self.dataset.column_policies.filter(is_visible=True).order_by("column_name")
        )

    def get_filterable_column_names(self):
        return set(
            self.dataset.column_policies.filter(is_filterable=True).values_list(
                "column_name", flat=True
            )
        )

    def get_relation_columns(self):
        policies = {
            policy.column_name: policy for policy in self.dataset.column_policies.all()
        }
        return [
            {
                "name": column["column_name"],
                "data_type": column["data_type"],
                "udt_name": column["udt_name"],
                "is_geometry": (
                    column["column_name"] == self.runtime_configuration.geometry_column
                ),
                "is_primary_key": (
                    column["column_name"]
                    == self.runtime_configuration.primary_key_column
                ),
                "is_label": (
                    column["column_name"] == self.runtime_configuration.label_field
                ),
                "is_configured": column["column_name"] in policies,
                "is_visible": (
                    policies[column["column_name"]].is_visible
                    if column["column_name"] in policies
                    else False
                ),
                "is_filterable": (
                    policies[column["column_name"]].is_filterable
                    if column["column_name"] in policies
                    else False
                ),
                "is_searchable": (
                    policies[column["column_name"]].is_searchable
                    if column["column_name"] in policies
                    else False
                ),
                "is_exportable": (
                    policies[column["column_name"]].is_exportable
                    if column["column_name"] in policies
                    else False
                ),
            }
            for column in self._get_existing_columns()
        ]

    @staticmethod
    def get_policy_label(policy):
        return policy.display_label or policy.column_name.replace("_", " ").title()

    @staticmethod
    def get_column_value(obj, column_name):
        return getattr(obj, column_name, "")

    def get_records(self, query_params=None):
        return self._fetch_records(query_params=query_params)

    def get_record(self, pk):
        records = self._fetch_records(pk=pk)
        if not records:
            raise Http404("No feature found for this dataset.")
        return records[0]

    def get_geojson_feature_collection(self, query_params=None):
        records = self._fetch_records(query_params=query_params, include_geometry=True)
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": record.pk,
                    "geometry": record.geometry,
                    "properties": record.properties,
                }
                for record in records
            ],
        }

    def _fetch_records(self, query_params=None, pk=None, include_geometry=False):
        self._validate_configured_columns()
        selected_columns = self._get_selected_columns()
        select_sql = [
            f"{connection.ops.quote_name(column)} AS {connection.ops.quote_name(column)}"
            for column in selected_columns
        ]
        if include_geometry:
            select_sql.append(
                "ST_AsGeoJSON("
                f"{connection.ops.quote_name(self.runtime_configuration.geometry_column)}"
                ") AS __geometry_geojson"
            )
        where_sql = []
        params = []
        if pk is not None:
            where_sql.append(
                f"{connection.ops.quote_name(self.runtime_configuration.primary_key_column)} = %s"
            )
            params.append(pk)
        elif query_params:
            filterable_columns = self.get_filterable_column_names()
            for column in sorted(filterable_columns):
                if column in query_params and query_params.get(column) != "":
                    self._validate_identifier(column)
                    where_sql.append(f"{connection.ops.quote_name(column)} = %s")
                    params.append(query_params.get(column))
        sql = (
            f"SELECT {', '.join(select_sql)} FROM {self.relation_identifier}"
            f"{' WHERE ' + ' AND '.join(where_sql) if where_sql else ''}"
            f" ORDER BY {connection.ops.quote_name(self.runtime_configuration.primary_key_column)}"
            " LIMIT %s"
        )
        params.append(MAX_LOCAL_RELATION_ROWS)
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return [
            self._build_record(row, selected_columns, include_geometry=include_geometry)
            for row in rows
        ]

    def _get_selected_columns(self):
        columns = [
            self.runtime_configuration.primary_key_column,
            *[
                policy.column_name
                for policy in self.get_visible_column_policies()
                if policy.column_name != self.runtime_configuration.primary_key_column
            ],
        ]
        if (
            self.runtime_configuration.label_field
            and self.runtime_configuration.label_field not in columns
        ):
            columns.append(self.runtime_configuration.label_field)
        return columns

    def _build_record(self, row, selected_columns, *, include_geometry=False):
        value_count = len(selected_columns)
        values = dict(zip(selected_columns, row[:value_count], strict=True))
        pk = values[self.runtime_configuration.primary_key_column]
        label = (
            values.get(self.runtime_configuration.label_field)
            if self.runtime_configuration.label_field
            else pk
        )
        record = LocalRelationRecord(pk=pk, label=label, values=values)
        if include_geometry:
            geometry_json = row[value_count]
            record.geometry = json.loads(geometry_json) if geometry_json else None
            record.properties = {
                column: value
                for column, value in values.items()
                if column != self.runtime_configuration.primary_key_column
            }
        return record

    def _validate_configured_columns(self):
        existing_column_metadata = self._get_existing_columns()
        existing_columns = {
            column["column_name"] for column in existing_column_metadata
        }
        for column_name in self.dataset.column_policies.values_list(
            "column_name", flat=True
        ):
            self._validate_identifier(column_name)
        configured_columns = {
            self.runtime_configuration.primary_key_column,
            self.runtime_configuration.geometry_column,
            *self.dataset.column_policies.values_list("column_name", flat=True),
        }
        if self.runtime_configuration.label_field:
            configured_columns.add(self.runtime_configuration.label_field)
        missing_columns = sorted(configured_columns - existing_columns)
        if missing_columns:
            raise ImproperlyConfigured(
                "Local relation dataset references missing columns: "
                f"{', '.join(missing_columns)}."
            )
        geometry_column = next(
            column
            for column in existing_column_metadata
            if column["column_name"] == self.runtime_configuration.geometry_column
        )
        if geometry_column["udt_name"] != "geometry":
            raise ImproperlyConfigured(
                "Local relation dataset geometry column is not a geometry column: "
                f"{self.runtime_configuration.geometry_column}."
            )

    def _get_existing_columns(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                [
                    self.runtime_configuration.schema_name,
                    self.runtime_configuration.relation_name,
                ],
            )
            columns = [
                {
                    "column_name": row[0],
                    "data_type": row[1],
                    "udt_name": row[2],
                }
                for row in cursor.fetchall()
            ]
        if not columns:
            raise ImproperlyConfigured(
                "Local relation dataset runtime relation was not found: "
                f"{self.runtime_configuration.schema_name}."
                f"{self.runtime_configuration.relation_name}."
            )
        return columns


def get_dataset_runtime_compatibility(runtime_model_name):
    compatibility = LEGACY_DATASET_RUNTIME_COMPATIBILITY.get(runtime_model_name)
    if compatibility is not None:
        return compatibility
    return get_source_domain_dataset_runtime_compatibility(runtime_model_name)


def get_dataset_runtime_adapter(dataset):
    runtime_configuration = dataset.get_runtime_configuration()
    if (
        runtime_configuration is not None
        and runtime_configuration.backend_type == "local_relation"
    ):
        return LocalRelationDatasetRuntimeAdapter(
            dataset=dataset,
            runtime_configuration=runtime_configuration,
        )
    runtime_model_name = dataset.get_runtime_model_name()
    compatibility = get_dataset_runtime_compatibility(runtime_model_name)
    if compatibility is None:
        raise ImproperlyConfigured(
            f"No dataset runtime compatibility registered for {runtime_model_name}."
        )
    if isinstance(compatibility, dict):
        model = compatibility["model"]
        filterset_class = compatibility["filterset_class"]
        template_name = compatibility["template_name"]
        apply_user_visibility_filter = compatibility["apply_user_visibility_filter"]
        features_api_basename = compatibility["features_api_basename"]
    else:
        model = compatibility.resolve_model()
        filterset_class = compatibility.resolve_filterset_class()
        template_name = compatibility.template_name
        apply_user_visibility_filter = compatibility.apply_user_visibility_filter
        features_api_basename = compatibility.features_api_basename
    return DatasetRuntimeAdapter(
        dataset=dataset,
        runtime_model_name=runtime_model_name,
        model=model,
        filterset_class=filterset_class,
        template_name=template_name,
        features_api_basename=(
            dataset.get_features_api_basename() or features_api_basename
        ),
        apply_user_visibility_filter=apply_user_visibility_filter,
    )
