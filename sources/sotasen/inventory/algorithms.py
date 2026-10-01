"""
Inventory algorithms for the Sötåsen case study.

The grass-to-protein demo inventory queries a local-relation GeoDataset of
agricultural land use parcels at the Sötåsen research farm (Töreboda, Sweden),
selects the grassland polygons and estimates annual biomass and recovered
protein from selectable parameters.

Parameter semantics (these are labelled the same way in the database objects
created by ``setup_sotasen_demo_inventory``):

- ``dry_matter_yield`` [t DM/ha/a]: default 9.0 is a demo assumption, not a
  measured value.
- ``crude_protein_fraction`` [kg CP / kg DM]: default 0.20 is a demo
  assumption, not a measured value.
- ``protein_recovery_fraction`` [-]: 0.04 and 0.20 are the endpoints of the
  recovery range observed in the project; 0.12 is a midpoint demo assumption
  (not a measured mean); 0.42 is a literature benchmark reported in
  Thomas 2025, "Biorefinery Modules (Swedish showcase)".

Each parameter may be passed either as a plain number or, as done by the
scenario evaluation pipeline, as a ``{"value": ..., "standard_deviation": ...}``
mapping keyed by the parameter's ``short_name``.
"""

import json
from collections.abc import Mapping

from django.contrib.gis.geos import (
    GeometryCollection,
    GEOSGeometry,
    MultiPolygon,
    Polygon,
)
from django.core.exceptions import ImproperlyConfigured

from inventories.algorithms import InventoryAlgorithmsBase
from inventories.models import ScenarioInventoryConfiguration
from maps.models import Catchment, GeoDataset
from maps.runtime_adapters import get_dataset_runtime_adapter

SOURCE_MODULE_PATH = "sources.sotasen.inventory.algorithms"
GRASS_TO_PROTEIN_FUNCTION = "sotasen_grass_to_protein"

LAND_USE_FIELD = "land_use"
AREA_FIELD = "area_ha"
GRASSLAND_LAND_USE = "Grassland"
AREA_SRID = 6933

DEFAULT_DRY_MATTER_YIELD = 9.0
DEFAULT_CRUDE_PROTEIN_FRACTION = 0.20
DEFAULT_PROTEIN_RECOVERY_FRACTION = 0.12


class InventoryAlgorithms(InventoryAlgorithmsBase):
    @classmethod
    def sotasen_grass_to_protein(cls, **kwargs):
        """
        Aggregate grassland area at Sötåsen and estimate annual dry matter and
        recovered protein production.

        Required keyword arguments (supplied by the scenario execution plan):
        ``catchment_id``, ``scenario_id`` and ``feedstock_id``. The land use
        GeoDataset is resolved from the scenario's inventory configuration; it
        can be overridden for tests with ``geodataset_id``.
        """
        geodataset = cls._resolve_geodataset(kwargs)
        adapter = get_dataset_runtime_adapter(geodataset)
        if not callable(getattr(adapter, "get_geojson_feature_collection", None)):
            raise ImproperlyConfigured(
                f"GeoDataset {geodataset.pk} is not backed by a local relation "
                "and cannot be used by the Sötåsen grass-to-protein inventory."
            )

        dry_matter_yield = cls._parameter_value(
            kwargs, "dry_matter_yield", DEFAULT_DRY_MATTER_YIELD
        )
        crude_protein_fraction = cls._parameter_value(
            kwargs, "crude_protein_fraction", DEFAULT_CRUDE_PROTEIN_FRACTION
        )
        protein_recovery_fraction = cls._parameter_value(
            kwargs, "protein_recovery_fraction", DEFAULT_PROTEIN_RECOVERY_FRACTION
        )
        cls._validate_parameters(
            dry_matter_yield, crude_protein_fraction, protein_recovery_fraction
        )

        catchment_geom = None
        catchment_id = kwargs.get("catchment_id")
        if catchment_id is not None:
            catchment = Catchment.objects.select_related("region__borders").get(
                pk=catchment_id
            )
            catchment_geom = catchment.geom
            if catchment_geom is None or catchment_geom.empty:
                raise ValueError("A catchment boundary is required for evaluation.")
            catchment_geom = catchment_geom.transform(4326, clone=True)

        feature_collection = adapter.get_geojson_feature_collection(
            query_params={LAND_USE_FIELD: GRASSLAND_LAND_USE}
        )

        result = {
            "aggregated_values": [],
            "aggregated_distributions": [],
            "features": [],
        }
        if catchment_geom is not None:
            result["geom_type"] = "MultiPolygon"

        total_area_ha = 0.0
        for feature in feature_collection.get("features", []):
            properties = feature.get("properties") or {}
            area_raw = properties.get(AREA_FIELD)
            area_ha = float(area_raw) if area_raw is not None else 0.0
            geometry = feature.get("geometry")
            if geometry is None:
                if catchment_geom is None:
                    total_area_ha += area_ha
                continue
            geom = GEOSGeometry(
                geometry if isinstance(geometry, str) else json.dumps(geometry),
                srid=4326,
            )
            if catchment_geom is not None:
                polygons = cls._polygon_parts(geom.intersection(catchment_geom))
                if not polygons:
                    continue
                clipped = MultiPolygon(polygons, srid=4326)
                parcel_area = geom.transform(AREA_SRID, clone=True).area
                clipped_area = clipped.transform(AREA_SRID, clone=True).area
                area_ha *= clipped_area / parcel_area
                geom = clipped
            total_area_ha += area_ha
            result["features"].append(
                {
                    "geom": geom,
                    "land_use": str(properties.get(LAND_USE_FIELD) or ""),
                    "area_ha": area_ha,
                    "dry_matter_mg_a": area_ha * dry_matter_yield,
                    "recovered_protein_mg_a": area_ha
                    * dry_matter_yield
                    * crude_protein_fraction
                    * protein_recovery_fraction,
                }
            )

        total_dry_matter = total_area_ha * dry_matter_yield
        total_crude_protein = total_dry_matter * crude_protein_fraction
        total_recovered_protein = total_crude_protein * protein_recovery_fraction

        result["aggregated_values"] = [
            {"name": "Grassland area", "value": total_area_ha, "unit": "ha"},
            {
                "name": "Total production",
                "value": total_dry_matter,
                "unit": "Mg/a",
            },
            {
                "name": "Crude protein in biomass",
                "value": total_crude_protein,
                "unit": "Mg/a",
            },
            {
                "name": "Recovered protein",
                "value": total_recovered_protein,
                "unit": "Mg/a",
            },
        ]

        return result

    @classmethod
    def _polygon_parts(cls, geom: GEOSGeometry) -> list[Polygon]:
        if geom.empty:
            return []
        if isinstance(geom, Polygon):
            return [geom]
        if isinstance(geom, (MultiPolygon, GeometryCollection)):
            return [polygon for part in geom for polygon in cls._polygon_parts(part)]
        return []

    @staticmethod
    def _resolve_geodataset(kwargs):
        geodataset_id = kwargs.get("geodataset_id")
        if geodataset_id is not None:
            return GeoDataset.objects.get(id=geodataset_id)
        config_entry = (
            ScenarioInventoryConfiguration.objects.filter(
                scenario_id=kwargs.get("scenario_id"),
                inventory_algorithm__source_module=SOURCE_MODULE_PATH,
                inventory_algorithm__function_name=GRASS_TO_PROTEIN_FUNCTION,
            )
            .select_related("geodataset")
            .first()
        )
        if config_entry is None or config_entry.geodataset_id is None:
            raise ImproperlyConfigured(
                "Cannot resolve the Sötåsen land use GeoDataset: no "
                "'geodataset_id' was passed and the scenario configuration "
                f"does not reference '{GRASS_TO_PROTEIN_FUNCTION}'."
            )
        return config_entry.geodataset

    @staticmethod
    def _parameter_value(kwargs, name, default):
        raw = kwargs.get(name)
        if isinstance(raw, Mapping):
            raw = raw.get("value")
        if raw is None:
            return float(default)
        return float(raw)

    @staticmethod
    def _validate_parameters(
        dry_matter_yield, crude_protein_fraction, protein_recovery_fraction
    ):
        if dry_matter_yield <= 0:
            raise ValueError("dry_matter_yield must be greater than 0.")
        for name, fraction in (
            ("crude_protein_fraction", crude_protein_fraction),
            ("protein_recovery_fraction", protein_recovery_fraction),
        ):
            if not 0 < fraction <= 1:
                raise ValueError(f"{name} must be in the range (0, 1].")


__all__ = ["InventoryAlgorithms"]
