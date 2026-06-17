import json

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import (
    Case,
    CharField,
    Count,
    Exists,
    F,
    FloatField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from maps.db_functions import SimplifyPreserveTopology
from maps.mixins import get_unbounded_geojson_rejection_response
from maps.models import LauRegion, NutsRegion, RegionAttributeValue, RegionProperty
from sources.waste_collection.derived_values import (
    convert_total_to_specific,
    get_derived_property_config,
)
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    Collector,
)

from .serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    CatchmentAccessControlSerializer,
    CatchmentBinConfigurationSerializer,
    CatchmentBiowasteImpuritySerializer,
    CatchmentCollectionAmountSerializer,
    CatchmentCollectionCountRatioSerializer,
    CatchmentCollectionCountSerializer,
    CatchmentCollectionPointCountRatioSerializer,
    CatchmentCollectionPointCountSerializer,
    CatchmentCollectionSupportSerializer,
    CatchmentCollectionSystemCountSerializer,
    CatchmentCollectionSystemSerializer,
    CatchmentCombinedCollectionCountSerializer,
    CatchmentCombinedCollectionSystemSerializer,
    CatchmentCombinedFeeSystemSerializer,
    CatchmentCombinedFrequencySerializer,
    CatchmentConnectionRateSerializer,
    CatchmentConnectionTypeSerializer,
    CatchmentFeeSystemSerializer,
    CatchmentFoodWasteCategorySerializer,
    CatchmentFrequencyTypeSerializer,
    CatchmentGeometrySerializer,
    CatchmentMaterialStatusSerializer,
    CatchmentMinBinSizeRatioSerializer,
    CatchmentMinBinSizeSerializer,
    CatchmentOrgaLevelSerializer,
    CatchmentOrganicRatioSerializer,
    CatchmentPopulationSerializer,
    CatchmentRequiredBinCapacitySerializer,
    CatchmentWasteRatioSerializer,
    CatchmentWeeklyBpAccessDaysSerializer,
)

# Material IDs for food waste classification (Karte 4)
_FOOD_WASTE_MATERIAL_IDS = {11, 12, 13, 14}

# Material IDs for collection support items (Karte 5, 6)
_PAPER_BAGS_MATERIAL_ID = 19
_PLASTIC_BAGS_MATERIAL_ID = 17
_REGULAR_PLASTIC_BAGS_MATERIAL_ID = 18

# Waste category names for green waste maps.
_GREEN_WASTE_CATEGORY_NAMES = ["Green waste"]

# Property ID for "Connection rate" (properties_property table)
CONNECTION_RATE_PROPERTY_ID = 4
COLLECTION_POINT_COUNT_PROPERTY_NAME = "number of collection points"
BIOWASTE_IMPURITY_RATE_PROPERTY_NAME = "biowaste impurity rate"
WEEKLY_BP_ACCESS_DAYS_PROPERTY_NAME = "weekly bring-point access days"

# Priority for picking the primary collection system per catchment.
# Lower number = higher priority.
_COLLECTION_SYSTEM_PRIORITY = {
    "Door to door": 1,
    "Mixed door-to-door and bring point": 2,
    "Bring point": 3,
    "Recycling centre": 4,
    "On demand kerbside collection": 5,
    "Home-composting": 6,
    "No separate collection": 7,
}

# Attribute IDs for population data (maps_attribute table)
POPULATION_ATTRIBUTE_ID = 3
POPULATION_DENSITY_ATTRIBUTE_ID = 2


class WasteAtlasViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "waste_atlas"


class WasteAtlasReadOnlyModelViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "waste_atlas"


def _resolve_property_id_by_name(name_setting, default_name):
    target_name = getattr(settings, name_setting, default_name)
    matches = RegionProperty.objects.filter(name=target_name)
    if matches.count() == 1:
        return matches.values_list("pk", flat=True).first()

    raise ImproperlyConfigured(
        f"Could not unambiguously resolve property named '{target_name}'."
    )


def _get_first_configured_setting(*setting_names):
    if not setting_names:
        return None, None
    for setting_name in setting_names:
        if hasattr(settings, setting_name):
            return setting_name, getattr(settings, setting_name)
    return setting_names[0], None


def _resolve_property_id_from_settings(id_setting, name_setting, default_name):
    if isinstance(id_setting, str):
        id_settings = (id_setting,)
    else:
        id_settings = tuple(id_setting)

    if isinstance(name_setting, str):
        name_settings = (name_setting,)
    else:
        name_settings = tuple(name_setting)

    configured_id_setting, configured_id = _get_first_configured_setting(*id_settings)
    if configured_id_setting is not None and configured_id is not None:
        if RegionProperty.objects.filter(pk=configured_id).exists():
            return configured_id
        raise ImproperlyConfigured(
            f"{configured_id_setting}={configured_id} does not exist for property '{default_name}'."
        )

    configured_name_setting, configured_name = _get_first_configured_setting(
        *name_settings
    )
    if configured_name is not None:
        return _resolve_property_id_by_name(configured_name_setting, default_name)

    return _resolve_property_id_by_name(name_settings[0], default_name)


def _resolved_population_attribute_id():
    """Return the configured population attribute ID with a legacy fallback."""
    try:
        return get_derived_property_config().population_attribute_id
    except ImproperlyConfigured:
        return _resolve_property_id_from_settings(
            (),
            (
                "WASTE_COLLECTION_POPULATION_ATTRIBUTE_NAME",
                "SOILCOM_POPULATION_ATTRIBUTE_NAME",
            ),
            "Population",
        )


def _resolved_population_density_attribute_id():
    try:
        return _resolve_property_id_from_settings(
            (
                "WASTE_COLLECTION_POPULATION_DENSITY_ATTRIBUTE_ID",
                "SOILCOM_POPULATION_DENSITY_ATTRIBUTE_ID",
            ),
            (
                "WASTE_COLLECTION_POPULATION_DENSITY_ATTRIBUTE_NAME",
                "SOILCOM_POPULATION_DENSITY_ATTRIBUTE_NAME",
            ),
            "Population density",
        )
    except ImproperlyConfigured:
        return None


def _parse_country_year(request):
    """Extract and validate country/year query params with defaults."""
    country = request.query_params.get("country", "DE")
    year = request.query_params.get("year", "2022")
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = 2022
    return country, year


def _parse_nuts_prefixes(request):
    """Return a list of NUTS-ID prefixes from the ``nuts_prefix`` query param.

    The parameter accepts a comma-separated list of NUTS prefixes, e.g.
    ``nuts_prefix=BE1,BE2`` to restrict results to Brussels and Flanders.
    Returns an empty list when the parameter is absent.
    """
    raw = request.query_params.get("nuts_prefix", "")
    return [p.strip() for p in raw.split(",") if p.strip()]


def _country_filter_q(catchment_path, country):
    prefix = catchment_path
    return (
        Q(**{f"{prefix}region__country": country})
        | Q(**{f"{prefix}parent__region__country": country})
        | Q(**{f"{prefix}parent__parent__region__country": country})
    )


def _apply_nuts_prefix_filter(qs, nuts_prefixes, catchment_path=""):
    """Narrow a queryset to catchments whose NUTS ancestry matches any prefix.

    Walks the catchment parent chain by filtering on NutsRegion rows whose
    ``nuts_id`` starts with one of *nuts_prefixes*.  The filter is applied via
    a subquery on the parent catchment hierarchy (depth ≤ 3).

    *catchment_path* is the ORM path prefix to the catchment FK, e.g.
    ``"catchment__"`` for Collection querysets, or ``""`` for
    CollectionCatchment querysets.
    """
    if not nuts_prefixes:
        return qs

    prefix_q = Q()
    for prefix in nuts_prefixes:
        prefix_q |= Q(
            **{f"{catchment_path}region__nutsregion__nuts_id__startswith": prefix}
        )
        prefix_q |= Q(
            **{
                f"{catchment_path}parent__region__nutsregion__nuts_id__startswith": prefix
            }
        )
        prefix_q |= Q(
            **{
                f"{catchment_path}parent__parent__region__nutsregion__nuts_id__startswith": prefix
            }
        )
    return qs.filter(prefix_q)


def _build_feature_collection(features):
    return {"type": "FeatureCollection", "features": features}


def _filter_by_waste_categories(queryset, categories):
    """Filter collections by inline waste category."""
    return queryset.filter(waste_category__name__in=categories)


def _select_primary_collections(
    country,
    year,
    waste_categories,
    nuts_prefixes=(),
    *,
    extra_fields=(),
    extra_filters=None,
):
    qs = Collection.objects.filter(
        _country_filter_q("catchment__", country),
        valid_from__year=year,
    )
    if waste_categories is not None:
        qs = _filter_by_waste_categories(qs, waste_categories)
    if extra_filters:
        qs = qs.filter(**extra_filters)
    qs = _apply_nuts_prefix_filter(qs, nuts_prefixes, catchment_path="catchment__")
    field_names = tuple(extra_fields)
    rows = qs.order_by("catchment_id", "id").values_list(
        "id",
        "catchment_id",
        "collection_system__name",
        *field_names,
    )

    best = {}
    for row in rows:
        collection_id, catchment_id, system, *extra_values = row
        priority = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
        current = best.get(catchment_id)
        if current is not None and priority >= current["priority"]:
            continue
        selected = {
            "collection_id": collection_id,
            "catchment_id": catchment_id,
            "collection_system": system,
            "priority": priority,
        }
        selected.update(dict(zip(field_names, extra_values, strict=True)))
        best[catchment_id] = selected
    return best


def _collection_version_chains(collection_ids):
    selected_ids = {collection_id for collection_id in collection_ids if collection_id}
    chains = {collection_id: {collection_id} for collection_id in selected_ids}
    if not selected_ids:
        return chains

    through = Collection.predecessors.through
    seen_ids = set(selected_ids)
    frontier_ids = set(selected_ids)
    edges = set()

    while frontier_ids:
        relation_rows = through.objects.filter(
            Q(from_collection_id__in=frontier_ids)
            | Q(to_collection_id__in=frontier_ids)
        ).values_list("from_collection_id", "to_collection_id")

        next_frontier_ids = set()
        for left_id, right_id in relation_rows:
            edges.add((left_id, right_id))
            if left_id not in seen_ids:
                next_frontier_ids.add(left_id)
            if right_id not in seen_ids:
                next_frontier_ids.add(right_id)

        seen_ids.update(next_frontier_ids)
        frontier_ids = next_frontier_ids

    adjacency = {collection_id: set() for collection_id in seen_ids}
    for left_id, right_id in edges:
        adjacency.setdefault(left_id, set()).add(right_id)
        adjacency.setdefault(right_id, set()).add(left_id)

    for selected_id in selected_ids:
        chain_ids = set()
        stack = [selected_id]
        while stack:
            collection_id = stack.pop()
            if collection_id in chain_ids:
                continue
            chain_ids.add(collection_id)
            stack.extend(adjacency.get(collection_id, ()))
        chains[selected_id] = chain_ids

    return chains


def _latest_connection_rate_values(collection_ids):
    version_chains = _collection_version_chains(collection_ids)
    if not version_chains:
        return {}

    all_chain_ids = set()
    for chain_ids in version_chains.values():
        all_chain_ids.update(chain_ids)

    cpv_rows = CollectionPropertyValue.objects.filter(
        collection_id__in=all_chain_ids,
        property_id=CONNECTION_RATE_PROPERTY_ID,
        average__isnull=False,
    ).values("id", "collection_id", "average", "year")

    values_by_collection_id = {}
    for row in cpv_rows:
        values_by_collection_id.setdefault(row["collection_id"], []).append(row)

    latest_by_selected_id = {}
    for selected_id, chain_ids in version_chains.items():
        latest = None
        for chain_id in chain_ids:
            for candidate in values_by_collection_id.get(chain_id, ()):
                candidate_key = (
                    candidate["year"] is not None,
                    candidate["year"] or 0,
                    candidate["id"],
                )
                if latest is None:
                    latest = candidate
                    latest_key = candidate_key
                    continue
                if candidate_key > latest_key:
                    latest = candidate
                    latest_key = candidate_key
        if latest is not None:
            latest_by_selected_id[selected_id] = latest

    return latest_by_selected_id


def _catchment_orga_level_case(catchment_path="catchment__"):
    """Classify the administrative type of the catchment region on a queryset."""
    nuts_exists = Exists(
        NutsRegion.objects.filter(region_ptr_id=OuterRef(f"{catchment_path}region_id"))
    )
    lau_exists = Exists(
        LauRegion.objects.filter(region_ptr_id=OuterRef(f"{catchment_path}region_id"))
    )
    return Case(
        When(nuts_exists, then=Value("nuts")),
        When(lau_exists, then=Value("lau")),
        default=Value("individual"),
        output_field=CharField(),
    )


def _active_collector_scope(country, year, nuts_prefixes):
    """Return collectors with collection records in the selected atlas year."""
    qs = Collector.objects.filter(
        _country_filter_q("catchment__", country),
        catchment__isnull=False,
        collection__valid_from__year=year,
    )
    return _apply_nuts_prefix_filter(qs, nuts_prefixes, catchment_path="catchment__")


class CatchmentViewSet(WasteAtlasReadOnlyModelViewSet):
    """Read-only viewset returning GeoJSON for catchments that have waste collections.

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year of ``valid_from`` on the collection (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/catchment/geojson/?country=DE&year=2022
    """

    serializer_class = CatchmentGeometrySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """Return distinct catchments matching the country/year filter."""
        country, year = _parse_country_year(self.request)
        nuts_prefixes = _parse_nuts_prefixes(self.request)
        qs = (
            CollectionCatchment.objects.filter(
                _country_filter_q("", country),
                collections__valid_from__year=year,
                region__borders__isnull=False,
            )
            .distinct()
            .select_related("region", "region__borders")
        )
        return _apply_nuts_prefix_filter(qs, nuts_prefixes)

    @action(detail=False, methods=["get"])
    def geojson(self, request, *args, **kwargs):
        """Return a GeoJSON FeatureCollection of matching catchments."""
        return self._geojson_response(
            request, self.filter_queryset(self.get_queryset())
        )

    @action(detail=False, methods=["get"], url_path="collection-geojson")
    def collection_geojson(self, request, *args, **kwargs):
        """Return GeoJSON for catchments assigned directly to collections."""
        return self._geojson_response(
            request, self.filter_queryset(self.get_queryset())
        )

    def _geojson_response(self, request, queryset):
        rejection_response = get_unbounded_geojson_rejection_response(
            request,
            queryset.count(),
            bounded_query_params={"country", "id", "nuts_prefix", "year"},
        )
        if rejection_response is not None:
            return rejection_response

        queryset = queryset.annotate(
            simplified_geom=SimplifyPreserveTopology(
                F("region__borders__geom"),
                GEOMETRY_SIMPLIFY_TOLERANCE,
            )
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="collector-geojson")
    def collector_geojson(self, request, *args, **kwargs):
        """Return GeoJSON for catchments assigned directly to collectors."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        collector_scope = _active_collector_scope(country, year, nuts_prefixes).filter(
            catchment__region__borders__isnull=False
        )
        queryset = (
            CollectionCatchment.objects.filter(
                id__in=collector_scope.values("catchment_id")
            )
            .distinct()
            .select_related("region", "region__borders")
        )
        rejection_response = get_unbounded_geojson_rejection_response(
            request,
            queryset.count(),
            bounded_query_params={"country", "id", "nuts_prefix", "year"},
        )
        if rejection_response is not None:
            return rejection_response

        queryset = queryset.annotate(
            simplified_geom=SimplifyPreserveTopology(
                F("region__borders__geom"),
                GEOMETRY_SIMPLIFY_TOLERANCE,
            )
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class OrgaLevelViewSet(WasteAtlasViewSet):
    """Return the organizational level for active collectors.

    Start from collectors active in the selected atlas year, follow their
    assigned catchment, and classify that catchment's region as NUTS, LAU, or
    individual. This keeps the collector-level map separate from collection
    records that use a different operational catchment.

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year of ``valid_from`` on the collection (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/collector-orga-level/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, orga_level}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        qs = (
            _active_collector_scope(country, year, nuts_prefixes)
            .distinct()
            .annotate(orga_level=_catchment_orga_level_case())
            .values("catchment_id", "orga_level")
        )

        data = [
            {"catchment_id": row["catchment_id"], "orga_level": row["orga_level"]}
            for row in qs
        ]
        serializer = CatchmentOrgaLevelSerializer(data, many=True)
        return Response(serializer.data)


class CollectionOrgaLevelViewSet(WasteAtlasViewSet):
    """Return the organizational level for collection catchments.

    This theme starts from collection records in the selected atlas year and
    classifies the regions of those collection catchments. It is intentionally
    separate from the collector-level catchment map.
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, orga_level}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        qs = Collection.objects.filter(
            _country_filter_q("catchment__", country),
            catchment__isnull=False,
            valid_from__year=year,
        )
        qs = _apply_nuts_prefix_filter(qs, nuts_prefixes, catchment_path="catchment__")
        qs = (
            qs.annotate(orga_level=_catchment_orga_level_case())
            .values("catchment_id", "orga_level")
            .distinct()
        )

        data = [
            {"catchment_id": row["catchment_id"], "orga_level": row["orga_level"]}
            for row in qs
        ]
        serializer = CatchmentOrgaLevelSerializer(data, many=True)
        return Response(serializer.data)


class CollectionSystemViewSet(WasteAtlasViewSet):
    """Return the primary biowaste collection system per catchment (Karte 2).

    For each catchment, selects the biowaste / food-waste collection with the
    highest-priority collection system (door-to-door > bring point >
    recycling centre > …).

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year of ``valid_from`` on the collection (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/collection-system/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, collection_system}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        data = [
            {"catchment_id": cid, "collection_system": row["collection_system"]}
            for cid, row in _select_primary_collections(
                country,
                year,
                ["Biowaste", "Food waste"],
                nuts_prefixes,
            ).items()
        ]
        serializer = CatchmentCollectionSystemSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteCollectionSystemViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = [
            {"catchment_id": cid, "collection_system": row["collection_system"]}
            for cid, row in _select_primary_collections(
                country,
                year,
                ["Biowaste", "Food waste"],
                nuts_prefixes,
            ).items()
        ]
        serializer = CatchmentCollectionSystemSerializer(data, many=True)
        return Response(serializer.data)


class ResidualCollectionSystemViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = [
            {"catchment_id": cid, "collection_system": row["collection_system"]}
            for cid, row in _select_primary_collections(
                country,
                year,
                ["Residual waste"],
                nuts_prefixes,
            ).items()
        ]
        serializer = CatchmentCollectionSystemSerializer(data, many=True)
        return Response(serializer.data)


class CombinedCollectionSystemViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        bio = _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
        )
        residual = _select_primary_collections(
            country,
            year,
            ["Residual waste"],
            nuts_prefixes,
        )
        data = [
            {
                "catchment_id": cid,
                "bio_collection_system": bio.get(cid, {}).get("collection_system"),
                "residual_collection_system": residual.get(cid, {}).get(
                    "collection_system"
                ),
            }
            for cid in set(bio) | set(residual)
        ]
        serializer = CatchmentCombinedCollectionSystemSerializer(data, many=True)
        return Response(serializer.data)


class CataloniaSystemAccessControlViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        bio = _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
            extra_fields=("access_control_bp", "access_control_pap"),
        )
        residual = _select_primary_collections(
            country,
            year,
            ["Residual waste"],
            nuts_prefixes,
            extra_fields=("access_control_bp", "access_control_pap"),
        )
        data = []
        for cid in set(bio) | set(residual):
            bio_row = bio.get(cid)
            residual_row = residual.get(cid)
            value = "Other combination"
            if (
                bio_row
                and residual_row
                and bio_row["collection_system"] == residual_row["collection_system"]
            ):
                system = bio_row["collection_system"]
                if system == "Bring point":
                    if bio_row["access_control_bp"] is True:
                        value = "Bring point + access control"
                    elif bio_row["access_control_bp"] is False:
                        value = "Bring point + no access control"
                elif system == "Door to door":
                    if bio_row["access_control_pap"] is True:
                        value = "PAP + use control"
                    elif bio_row["access_control_pap"] is False:
                        value = "PAP + no use control"
            data.append({"catchment_id": cid, "access_control": value})
        serializer = CatchmentAccessControlSerializer(data, many=True)
        return Response(serializer.data)


class AccessControlViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        best = _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
            extra_fields=("access_control_bp", "access_control_pap"),
        )

        data = []
        for cid, row in best.items():
            system = row["collection_system"]
            bp = row["access_control_bp"]
            pap = row["access_control_pap"]
            if system == "No separate collection":
                value = "No separate biowaste collection"
            elif bp is True and pap is True:
                value = "Bring point: yes | Door-to-door: yes"
            elif bp is True and pap is False:
                value = "Bring point: yes | Door-to-door: no"
            elif bp is False and pap is True:
                value = "Bring point: no | Door-to-door: yes"
            elif bp is False and pap is False:
                value = "Bring point: no | Door-to-door: no"
            elif bp is True:
                value = "Bring point: yes"
            elif pap is True:
                value = "Door-to-door: yes"
            elif bp is False:
                value = "Bring point: no"
            elif pap is False:
                value = "Door-to-door: no"
            else:
                value = "no_data"
            data.append({"catchment_id": cid, "access_control": value})

        serializer = CatchmentAccessControlSerializer(data, many=True)
        return Response(serializer.data)


class BinConfigurationViewSet(WasteAtlasViewSet):
    """Return the primary sorting method for biowaste per catchment.

    For each catchment, selects the primary biowaste / food-waste collection via
    collection-system priority and returns its sorting method.
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, bin_configuration}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        best = _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
            extra_fields=("bin_configuration__name",),
        )

        data = []
        for cid, row in best.items():
            system = row["collection_system"]
            bin_configuration = row["bin_configuration__name"]
            if system == "No separate collection":
                value = "No separate collection"
            elif bin_configuration:
                value = bin_configuration
            else:
                value = "no_data"
            data.append({"catchment_id": cid, "bin_configuration": value})

        serializer = CatchmentBinConfigurationSerializer(data, many=True)
        return Response(serializer.data)


class GreenWasteCollectionSystemCountViewSet(WasteAtlasViewSet):
    """Return number of distinct green-waste collection systems per catchment.

    Counts distinct collection systems among Green waste collections
    in the selected country/year.

    Example::

        GET /waste_collection/api/waste-atlas/green-waste-collection-system-count/?country=DE&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, collection_system_count}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        qs = _filter_by_waste_categories(
            Collection.objects.filter(
                _country_filter_q("catchment__", country),
                valid_from__year=year,
            ),
            _GREEN_WASTE_CATEGORY_NAMES,
        )
        qs = _apply_nuts_prefix_filter(qs, nuts_prefixes, catchment_path="catchment__")
        qs = (
            qs.values("catchment_id")
            .annotate(collection_system_count=Count("collection_system", distinct=True))
            .values("catchment_id", "collection_system_count")
        )
        serializer = CatchmentCollectionSystemCountSerializer(qs, many=True)
        return Response(serializer.data)


def _classify_food_waste(material_ids):
    """Classify allowed food waste materials into a legend category.

    Material IDs:
        11 = Non-processed animal-based
        12 = Processed animal-based
        13 = Non-processed plant-based
        14 = Processed plant-based
    """
    mids = material_ids & _FOOD_WASTE_MATERIAL_IDS
    if not mids:
        return "Uncategorized"
    if mids == {13}:
        return "Only raw plant-based"
    if mids <= {13, 14} and not mids & {11, 12}:
        return "No meat"
    if mids <= {12, 13, 14} and 11 not in mids:
        return "No raw meat"
    if mids >= {11, 12, 13, 14}:
        return "All four materials"
    return "Uncategorized"


def _get_material_status(country, year, material_id, nuts_prefixes=()):
    """Return per-catchment allowed/forbidden status for a given material.

    Returns a list of dicts: ``[{catchment_id, status}]`` where *status* is
    one of ``'allowed'``, ``'forbidden'``, ``'No separate collection'``,
    or ``'no_data'``.
    """
    best = _select_primary_collections(
        country,
        year,
        ["Biowaste", "Food waste"],
        nuts_prefixes,
    )

    collection_ids = [
        row["collection_id"]
        for row in best.values()
        if row["collection_id"] is not None
    ]

    # Step 2: batch-fetch allowed / forbidden sets for the target material
    allowed_collections = set(
        Collection.objects.filter(
            id__in=collection_ids,
            allowed_materials__id=material_id,
        ).values_list("id", flat=True)
    )
    forbidden_collections = set(
        Collection.objects.filter(
            id__in=collection_ids,
            forbidden_materials__id=material_id,
        ).values_list("id", flat=True)
    )

    # Step 3: classify
    data = []
    for cid, row in best.items():
        collection_id = row["collection_id"]
        system = row["collection_system"]
        if system == "No separate collection":
            status = "No separate collection"
        elif collection_id in allowed_collections:
            status = "allowed"
        elif collection_id in forbidden_collections:
            status = "forbidden"
        else:
            status = "no_data"
        data.append({"catchment_id": cid, "status": status})
    return data


def _get_collection_count(
    country, year, waste_categories, nuts_prefixes=(), include_missing_primary=False
):
    """Return per-catchment annual collection count for the given waste categories.

    For door-to-door collections, sums ``CollectionCountOptions.standard``
    across all seasons.  Also flags whether the counts vary by season.
    Non-door-to-door catchments are excluded (they have no frequency data).
    """
    qs = _filter_by_waste_categories(
        Collection.objects.filter(
            _country_filter_q("catchment__", country),
            valid_from__year=year,
            collection_system__name="Door to door",
            frequency__isnull=False,
        ),
        waste_categories,
    )
    qs = _apply_nuts_prefix_filter(qs, nuts_prefixes, catchment_path="catchment__")
    rows = qs.values_list(
        "catchment_id",
        "frequency__collectioncountoptions__standard",
    )

    # Gather per-catchment option counts.
    catchment_options: dict[int, list[int]] = {}
    for cid, std in rows:
        if std is None:
            continue
        catchment_options.setdefault(cid, []).append(std)

    data = []
    for cid, options in catchment_options.items():
        data.append(
            {
                "catchment_id": cid,
                "collection_count": sum(options),
                "has_seasonal_variation": len(set(options)) > 1,
                "is_door_to_door": True,
            }
        )
    if include_missing_primary:
        existing_ids = {row["catchment_id"] for row in data}
        best_system = _select_primary_collections(
            country,
            year,
            waste_categories,
            nuts_prefixes,
        )
        for cid, row in best_system.items():
            if cid not in existing_ids:
                data.append(
                    {
                        "catchment_id": cid,
                        "collection_count": None,
                        "has_seasonal_variation": False,
                        "is_door_to_door": row["collection_system"] == "Door to door",
                    }
                )
    return data


def _get_frequency_type(country, year, waste_categories, nuts_prefixes=()):
    """Return per-catchment frequency type for the given waste categories.

    For door-to-door collections, returns the ``CollectionFrequency.type``;
    for other systems, returns the collection system name.
    """
    best = _select_primary_collections(
        country,
        year,
        waste_categories,
        nuts_prefixes,
        extra_fields=("frequency__type",),
    )

    data = []
    for cid, row in best.items():
        system = row["collection_system"]
        freq_type = row["frequency__type"]
        if system == "Door to door" and freq_type:
            val = freq_type
        else:
            val = system
        data.append({"catchment_id": cid, "frequency_type": val})
    return data


class ResidualFrequencyTypeViewSet(WasteAtlasViewSet):
    """Return collection frequency type for residual waste (Karte 8).

    Example::

        GET /waste_collection/api/waste-atlas/residual-frequency-type/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, frequency_type}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_frequency_type(country, year, ["Residual waste"], nuts_prefixes)
        serializer = CatchmentFrequencyTypeSerializer(data, many=True)
        return Response(serializer.data)


class CombinedFrequencyTypeViewSet(WasteAtlasViewSet):
    """Return combined bio + residual frequency type per catchment (Karte 10).

    Example::

        GET /waste_collection/api/waste-atlas/combined-frequency-type/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, bio_frequency, residual_frequency}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        bio = {
            r["catchment_id"]: r["frequency_type"]
            for r in _get_frequency_type(
                country, year, ["Biowaste", "Food waste"], nuts_prefixes
            )
        }
        res = {
            r["catchment_id"]: r["frequency_type"]
            for r in _get_frequency_type(
                country, year, ["Residual waste"], nuts_prefixes
            )
        }
        all_ids = set(bio) | set(res)
        data = []
        for cid in all_ids:
            data.append(
                {
                    "catchment_id": cid,
                    "bio_frequency": bio.get(cid, "no_data"),
                    "residual_frequency": res.get(cid, "no_data"),
                }
            )
        serializer = CatchmentCombinedFrequencySerializer(data, many=True)
        return Response(serializer.data)


class BiowasteFrequencyTypeViewSet(WasteAtlasViewSet):
    """Return collection frequency type for biowaste (Karte 9).

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-frequency-type/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, frequency_type}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_frequency_type(
            country, year, ["Biowaste", "Food waste"], nuts_prefixes
        )
        serializer = CatchmentFrequencyTypeSerializer(data, many=True)
        return Response(serializer.data)


class ResidualCollectionCountViewSet(WasteAtlasViewSet):
    """Return annual collection count for residual waste (Karte 11).

    Example::

        GET /waste_collection/api/waste-atlas/residual-collection-count/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, collection_count, has_seasonal_variation}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_collection_count(country, year, ["Residual waste"], nuts_prefixes)
        serializer = CatchmentCollectionCountSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteCollectionCountViewSet(WasteAtlasViewSet):
    """Return annual collection count for biowaste (Karte 12).

    Includes non-door-to-door catchments with ``collection_count=null``.

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-collection-count/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, collection_count, has_seasonal_variation}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        door_to_door = _get_collection_count(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
            include_missing_primary=True,
        )
        serializer = CatchmentCollectionCountSerializer(door_to_door, many=True)
        return Response(serializer.data)


class CombinedCollectionCountViewSet(WasteAtlasViewSet):
    """Return combined bio + residual collection count per catchment (Karte 13).

    Example::

        GET /waste_collection/api/waste-atlas/combined-collection-count/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, bio_count, residual_count}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        bio = {
            r["catchment_id"]: r
            for r in _get_collection_count(
                country,
                year,
                ["Biowaste", "Food waste"],
                nuts_prefixes,
                include_missing_primary=True,
            )
        }
        res = {
            r["catchment_id"]: r
            for r in _get_collection_count(
                country, year, ["Residual waste"], nuts_prefixes
            )
        }
        all_ids = set(bio) | set(res)
        data = [
            {
                "catchment_id": cid,
                "bio_count": bio.get(cid, {}).get("collection_count"),
                "residual_count": res.get(cid, {}).get("collection_count"),
                "bio_is_door_to_door": bio.get(cid, {}).get("is_door_to_door"),
                "residual_is_door_to_door": res.get(cid, {}).get("is_door_to_door"),
            }
            for cid in all_ids
        ]
        serializer = CatchmentCombinedCollectionCountSerializer(data, many=True)
        return Response(serializer.data)


class CollectionCountRatioViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        bio = {
            r["catchment_id"]: r
            for r in _get_collection_count(
                country,
                year,
                ["Biowaste", "Food waste"],
                nuts_prefixes,
                include_missing_primary=True,
            )
        }
        res = {
            r["catchment_id"]: r
            for r in _get_collection_count(
                country, year, ["Residual waste"], nuts_prefixes
            )
        }
        all_ids = set(bio) | set(res)
        data = []
        for cid in all_ids:
            bio_row = bio.get(cid, {})
            res_row = res.get(cid, {})
            bio_count = bio_row.get("collection_count")
            residual_count = res_row.get("collection_count")
            ratio = None
            if (
                bio_count is not None
                and residual_count is not None
                and residual_count != 0
            ):
                ratio = bio_count / residual_count
            data.append(
                {
                    "catchment_id": cid,
                    "bio_count": bio_count,
                    "residual_count": residual_count,
                    "ratio": ratio,
                    "bio_is_door_to_door": bio_row.get("is_door_to_door"),
                    "residual_is_door_to_door": res_row.get("is_door_to_door"),
                    "bio_has_seasonal_variation": bio_row.get(
                        "has_seasonal_variation", False
                    ),
                }
            )
        serializer = CatchmentCollectionCountRatioSerializer(data, many=True)
        return Response(serializer.data)


class CollectionPointCountViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]
    waste_categories = None

    def _get_data(self, country, year, nuts_prefixes):
        best = _select_primary_collections(
            country,
            year,
            self.waste_categories,
            nuts_prefixes,
        )

        collection_ids = [row["collection_id"] for row in best.values()]
        cpv_qs = (
            CollectionPropertyValue.objects.filter(
                collection_id__in=collection_ids,
                property__name=COLLECTION_POINT_COUNT_PROPERTY_NAME,
                unit__name="No unit",
                year=year,
            )
            .order_by("collection_id", "-id")
            .distinct("collection_id")
            .values_list("collection_id", "average")
        )
        value_lookup = dict(cpv_qs)

        return [
            {
                "catchment_id": cid,
                "collection_point_count": value_lookup.get(row["collection_id"]),
                "is_door_to_door": row["collection_system"] == "Door to door",
            }
            for cid, row in best.items()
        ]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = self._get_data(country, year, nuts_prefixes)
        serializer = CatchmentCollectionPointCountSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteCollectionPointCountViewSet(CollectionPointCountViewSet):
    waste_categories = ["Biowaste", "Food waste"]


class ResidualCollectionPointCountViewSet(CollectionPointCountViewSet):
    waste_categories = ["Residual waste"]


class CollectionPointCountRatioViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        bio = {
            r["catchment_id"]: r
            for r in BiowasteCollectionPointCountViewSet()._get_data(
                country, year, nuts_prefixes
            )
        }
        res = {
            r["catchment_id"]: r
            for r in ResidualCollectionPointCountViewSet()._get_data(
                country, year, nuts_prefixes
            )
        }
        all_ids = set(bio) | set(res)
        data = []
        for cid in all_ids:
            bio_row = bio.get(cid, {})
            res_row = res.get(cid, {})
            bio_count = bio_row.get("collection_point_count")
            residual_count = res_row.get("collection_point_count")
            ratio = None
            if (
                bio_count is not None
                and residual_count is not None
                and residual_count != 0
            ):
                ratio = bio_count / residual_count
            data.append(
                {
                    "catchment_id": cid,
                    "bio_count": bio_count,
                    "residual_count": residual_count,
                    "ratio": ratio,
                    "bio_is_door_to_door": bio_row.get("is_door_to_door"),
                    "residual_is_door_to_door": res_row.get("is_door_to_door"),
                }
            )
        serializer = CatchmentCollectionPointCountRatioSerializer(data, many=True)
        return Response(serializer.data)


def _get_fee_system(country, year, waste_categories, nuts_prefixes=()):
    """Return per-catchment fee system for the given waste categories.

    For biowaste, non-door-to-door catchments return the collection
    system name instead of the fee system.
    """
    best = _select_primary_collections(
        country,
        year,
        waste_categories,
        nuts_prefixes,
        extra_fields=("fee_system__name",),
    )

    data = []
    for cid, row in best.items():
        system = row["collection_system"]
        fee = row["fee_system__name"]
        if system == "No separate collection":
            val = "No separate collection"
        elif fee:
            val = fee
        else:
            val = "no_data"
        data.append({"catchment_id": cid, "fee_system": val})
    return data


class ResidualFeeSystemViewSet(WasteAtlasViewSet):
    """Return fee system for residual waste per catchment (Karte 14).

    Example::

        GET /waste_collection/api/waste-atlas/residual-fee-system/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, fee_system}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_fee_system(country, year, ["Residual waste"], nuts_prefixes)
        serializer = CatchmentFeeSystemSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteFeeSystemViewSet(WasteAtlasViewSet):
    """Return fee system for biowaste per catchment (Karte 15).

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-fee-system/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, fee_system}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_fee_system(country, year, ["Biowaste", "Food waste"], nuts_prefixes)
        serializer = CatchmentFeeSystemSerializer(data, many=True)
        return Response(serializer.data)


class CombinedFeeSystemViewSet(WasteAtlasViewSet):
    """Return combined bio + residual fee system per catchment (Karte 16).

    Example::

        GET /waste_collection/api/waste-atlas/combined-fee-system/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, bio_fee, residual_fee}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        bio = {
            r["catchment_id"]: r["fee_system"]
            for r in _get_fee_system(
                country, year, ["Biowaste", "Food waste"], nuts_prefixes
            )
        }
        res = {
            r["catchment_id"]: r["fee_system"]
            for r in _get_fee_system(country, year, ["Residual waste"], nuts_prefixes)
        }
        all_ids = set(bio) | set(res)
        data = [
            {
                "catchment_id": cid,
                "bio_fee": bio.get(cid, "no_data"),
                "residual_fee": res.get(cid, "no_data"),
            }
            for cid in all_ids
        ]
        serializer = CatchmentCombinedFeeSystemSerializer(data, many=True)
        return Response(serializer.data)


def _get_collection_amount(
    country,
    year,
    waste_categories,
    nuts_prefixes=(),
    include_value_source=False,
    include_acpv_group_key=False,
):
    """Return per-catchment collection amount in kg/person/year.

    Uses ``specific waste collected`` for the requested year directly.
    Derived CPV records (computed from total waste / population) are
    included automatically via the ``is_derived`` mechanism.

    Data is looked up across **all** collections for a catchment (any
    year) so that values attached to an earlier collection version are
    still found.
    """
    # ------------------------------------------------------------------
    # Step 1: pick primary collection system per catchment
    # ------------------------------------------------------------------
    best = _select_primary_collections(
        country,
        year,
        waste_categories,
        nuts_prefixes,
    )

    catchment_ids = list(best.keys())

    # ------------------------------------------------------------------
    # Step 2: map catchments → all collection IDs (any year)
    # ------------------------------------------------------------------
    all_col_rows = _filter_by_waste_categories(
        Collection.objects.filter(
            catchment_id__in=catchment_ids,
        ),
        waste_categories,
    ).values_list("id", "catchment_id")

    cid_to_cols: dict[int, set[int]] = {}
    all_collection_ids: set[int] = set()
    for col_id, cid in all_col_rows:
        cid_to_cols.setdefault(cid, set()).add(col_id)
        all_collection_ids.add(col_id)

    col_to_cid: dict[int, int] = {}
    for cid, col_ids in cid_to_cols.items():
        for col_id in col_ids:
            col_to_cid[col_id] = cid

    # ------------------------------------------------------------------
    # Step 3: look up amounts (strategy depends on year)
    # ------------------------------------------------------------------
    amounts, value_sources, acpv_group_keys = _amounts_for_year(
        year,
        all_collection_ids,
        col_to_cid,
        catchment_ids,
        include_metadata=True,
    )

    # ------------------------------------------------------------------
    # Step 4: build result list
    # ------------------------------------------------------------------
    data = []
    for cid, row in best.items():
        system = row["collection_system"]
        no_collection = system == "No separate collection"
        amount = None if no_collection else amounts.get(cid)
        data.append(
            {
                "catchment_id": cid,
                "amount": amount,
                "no_collection": no_collection,
                **(
                    {"value_source": None if no_collection else value_sources.get(cid)}
                    if include_value_source
                    else {}
                ),
                **(
                    {
                        "acpv_group_key": None
                        if no_collection
                        else acpv_group_keys.get(cid)
                    }
                    if include_acpv_group_key
                    else {}
                ),
            }
        )
    return data


def _build_acpv_group_key(acpv_ids):
    if not acpv_ids:
        return None
    return "acpv-" + "-".join(str(acpv_id) for acpv_id in sorted(acpv_ids))


def _amounts_for_year(
    year,
    all_collection_ids,
    col_to_cid,
    catchment_ids,
    *,
    include_metadata=False,
):
    """Specific waste collected for *year*, with total/population fallback.

    Derived CPV records (computed from total waste / population) are
    stored in the database with ``is_derived=True`` and are picked up
    by this query automatically. For environments where backfill was not
    run yet, this function also computes a read-time fallback from
    ``total waste collected`` and population.
    """
    cfg = get_derived_property_config()
    cpv_qs = (
        CollectionPropertyValue.objects.filter(
            collection_id__in=all_collection_ids,
            property_id=cfg.specific_property_id,
            year=year,
        )
        .exclude(average=0)
        .values_list("collection_id", "average")
    )
    result: dict[int, float] = {}
    value_sources: dict[int, str] = {}
    for col_id, avg in cpv_qs:
        cid = col_to_cid.get(col_id)
        if cid is not None and cid not in result:
            result[cid] = avg
            value_sources[cid] = "cpv"

    missing_cids = [cid for cid in catchment_ids if cid not in result]
    acpv_group_keys: dict[int, str | None] = {}
    if missing_cids:
        missing_cid_set = set(missing_cids)
        missing_cols = {
            col_id for col_id, cid in col_to_cid.items() if cid in missing_cid_set
        }
        agg_qs = (
            AggregatedCollectionPropertyValue.objects.filter(
                collections__id__in=missing_cols,
                property_id=cfg.specific_property_id,
                year=year,
            )
            .exclude(average=0)
            .values_list("collections__id", "average", "id")
        )
        acpv_by_catchment: dict[int, list[float]] = {}
        acpv_ids_by_catchment: dict[int, set[int]] = {}
        for col_id, avg, acpv_id in agg_qs:
            cid = col_to_cid.get(col_id)
            if cid is not None and cid not in result:
                acpv_by_catchment.setdefault(cid, []).append(avg)
                acpv_ids_by_catchment.setdefault(cid, set()).add(acpv_id)
        for cid, values in acpv_by_catchment.items():
            if values:
                result[cid] = sum(values) / len(values)
                value_sources[cid] = "acpv"
                acpv_group_keys[cid] = _build_acpv_group_key(acpv_ids_by_catchment[cid])

    # Runtime fallback for missing catchments: total_Mg * 1000 / population.
    missing_cids = [cid for cid in catchment_ids if cid not in result]
    if not missing_cids:
        if include_metadata:
            return result, value_sources, acpv_group_keys
        return result

    missing_cid_set = set(missing_cids)
    missing_cols = {
        col_id for col_id, cid in col_to_cid.items() if cid in missing_cid_set
    }
    total_qs = (
        CollectionPropertyValue.objects.filter(
            collection_id__in=missing_cols,
            property_id=cfg.total_property_id,
            year=year,
        )
        .exclude(average=0)
        .values_list("collection_id", "average")
    )
    total_by_catchment: dict[int, float] = {}
    for col_id, avg in total_qs:
        cid = col_to_cid.get(col_id)
        if cid is not None:
            total_by_catchment[cid] = avg

    if not total_by_catchment:
        if include_metadata:
            return result, value_sources, acpv_group_keys
        return result

    pop_qs = (
        RegionAttributeValue.objects.filter(
            region__catchment__id__in=list(total_by_catchment.keys()),
            property_id=_resolved_population_attribute_id(),
        )
        .order_by("region_id", "-date")
        .distinct("region_id")
        .values_list("region_id", "value")
    )
    region_pop: dict[int, float] = dict(pop_qs)

    catchment_regions = dict(
        CollectionCatchment.objects.filter(
            id__in=list(total_by_catchment.keys()),
        ).values_list("id", "region_id")
    )
    for cid, total_mg in total_by_catchment.items():
        region_id = catchment_regions.get(cid)
        if region_id is None:
            continue
        pop = region_pop.get(region_id)
        if pop and pop > 0:
            result[cid] = convert_total_to_specific(total_mg, pop, ndigits=1)
            value_sources[cid] = "cpv"
    if include_metadata:
        return result, value_sources, acpv_group_keys
    return result


def _amounts_for_2024(year, all_collection_ids, col_to_cid, catchment_ids):
    return _amounts_for_year(year, all_collection_ids, col_to_cid, catchment_ids)


def _get_biowaste_acpv_outline_geojson(country, year, nuts_prefixes=()):
    amount_rows = _get_collection_amount(
        country,
        year,
        ["Biowaste", "Food waste"],
        nuts_prefixes,
        include_value_source=True,
        include_acpv_group_key=True,
    )
    catchment_ids_by_group: dict[str, list[int]] = {}
    for row in amount_rows:
        group_key = row.get("acpv_group_key")
        if group_key:
            catchment_ids_by_group.setdefault(group_key, []).append(row["catchment_id"])

    if not catchment_ids_by_group:
        return _build_feature_collection([])

    catchments = {
        catchment.id: catchment
        for catchment in CollectionCatchment.objects.filter(
            id__in=[cid for cids in catchment_ids_by_group.values() for cid in cids],
            region__borders__isnull=False,
        ).select_related("region", "region__borders")
    }

    features = []
    for group_key in sorted(catchment_ids_by_group):
        group_catchment_ids = sorted(catchment_ids_by_group[group_key])
        geoms = [
            catchments[catchment_id].region.borders.geom
            for catchment_id in group_catchment_ids
            if catchment_id in catchments
            and catchments[catchment_id].region
            and catchments[catchment_id].region.borders
            and catchments[catchment_id].region.borders.geom
        ]
        if not geoms:
            continue

        dissolved_geom = geoms[0].clone()
        for geom in geoms[1:]:
            dissolved_geom = dissolved_geom.union(geom)
        dissolved_geom.normalize()
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "acpv_group_key": group_key,
                    "catchment_ids": group_catchment_ids,
                },
                "geometry": json.loads(dissolved_geom.geojson),
            }
        )

    return _build_feature_collection(features)


def _get_green_waste_collection_amount(country, year, nuts_prefixes=()):
    """Return per-catchment green-waste amount in kg/person/year.

    Priority for amount resolution:

    1) aggregated specific amount (ACPV)
    2) specific amount (CPV)
    3) total amount (CPV/ACPV) converted via population
    """
    best = _select_primary_collections(
        country,
        year,
        _GREEN_WASTE_CATEGORY_NAMES,
        nuts_prefixes,
    )

    scoped_catchment_ids = list(
        _apply_nuts_prefix_filter(
            CollectionCatchment.objects.filter(
                _country_filter_q("", country),
                collections__valid_from__year=year,
            ).distinct(),
            nuts_prefixes,
        ).values_list("id", flat=True)
    )
    for catchment_id in scoped_catchment_ids:
        if catchment_id not in best:
            best[catchment_id] = {
                "collection_id": None,
                "catchment_id": catchment_id,
                "collection_system": "No separate collection",
                "priority": 99,
            }

    catchment_ids = list(best.keys())
    if not catchment_ids:
        return []

    all_col_rows = _filter_by_waste_categories(
        Collection.objects.filter(
            catchment_id__in=catchment_ids,
        ),
        _GREEN_WASTE_CATEGORY_NAMES,
    ).values_list("id", "catchment_id")

    col_to_cid: dict[int, int] = {}
    all_collection_ids: set[int] = set()
    for col_id, cid in all_col_rows:
        col_to_cid[col_id] = cid
        all_collection_ids.add(col_id)

    cfg = get_derived_property_config()

    # 1) Aggregated specific waste amount per catchment.
    agg_specific_by_catchment: dict[int, list[float]] = {}
    agg_specific_qs = (
        AggregatedCollectionPropertyValue.objects.filter(
            collections__id__in=all_collection_ids,
            property_id=cfg.specific_property_id,
            year=year,
        )
        .exclude(average=0)
        .values_list("collections__id", "average")
    )
    for col_id, avg in agg_specific_qs:
        cid = col_to_cid.get(col_id)
        if cid is not None:
            agg_specific_by_catchment.setdefault(cid, []).append(avg)

    amounts = {
        cid: sum(values) / len(values)
        for cid, values in agg_specific_by_catchment.items()
        if values
    }

    missing_cids = [cid for cid in catchment_ids if cid not in amounts]

    # 2) Fallback to non-aggregated specific amount.
    if missing_cids:
        missing_cid_set = set(missing_cids)
        missing_cols = {
            col_id for col_id, cid in col_to_cid.items() if cid in missing_cid_set
        }
        cpv_specific_by_catchment: dict[int, list[float]] = {}
        cpv_specific_qs = (
            CollectionPropertyValue.objects.filter(
                collection_id__in=missing_cols,
                property_id=cfg.specific_property_id,
                year=year,
            )
            .exclude(average=0)
            .values_list("collection_id", "average")
        )
        for col_id, avg in cpv_specific_qs:
            cid = col_to_cid.get(col_id)
            if cid is not None:
                cpv_specific_by_catchment.setdefault(cid, []).append(avg)

        for cid, values in cpv_specific_by_catchment.items():
            if cid not in amounts and values:
                amounts[cid] = sum(values) / len(values)

    missing_cids = [cid for cid in catchment_ids if cid not in amounts]

    # 3) Fallback to total amount converted via population.
    if missing_cids:
        missing_cid_set = set(missing_cids)
        missing_cols = {
            col_id for col_id, cid in col_to_cid.items() if cid in missing_cid_set
        }

        total_by_catchment: dict[int, float] = {}
        total_qs = (
            CollectionPropertyValue.objects.filter(
                collection_id__in=missing_cols,
                property_id=cfg.total_property_id,
                year=year,
            )
            .exclude(average=0)
            .values_list("collection_id", "average")
        )
        for col_id, avg in total_qs:
            cid = col_to_cid.get(col_id)
            if cid is not None:
                total_by_catchment[cid] = total_by_catchment.get(cid, 0) + avg

        still_missing_cids = [
            cid for cid in missing_cids if cid not in total_by_catchment
        ]
        if still_missing_cids:
            still_missing_cid_set = set(still_missing_cids)
            still_missing_cols = {
                col_id
                for col_id, cid in col_to_cid.items()
                if cid in still_missing_cid_set
            }
            agg_total_by_catchment: dict[int, list[float]] = {}
            agg_total_qs = (
                AggregatedCollectionPropertyValue.objects.filter(
                    collections__id__in=still_missing_cols,
                    property_id=cfg.total_property_id,
                    year=year,
                )
                .exclude(average=0)
                .values_list("collections__id", "average")
            )
            for col_id, avg in agg_total_qs:
                cid = col_to_cid.get(col_id)
                if cid is not None:
                    agg_total_by_catchment.setdefault(cid, []).append(avg)
            for cid, values in agg_total_by_catchment.items():
                if cid not in total_by_catchment and values:
                    total_by_catchment[cid] = sum(values) / len(values)

        if total_by_catchment:
            pop_qs = (
                RegionAttributeValue.objects.filter(
                    region__catchment__id__in=list(total_by_catchment.keys()),
                    property_id=_resolved_population_attribute_id(),
                )
                .order_by("region_id", "-date")
                .distinct("region_id")
                .values_list("region_id", "value")
            )
            region_pop: dict[int, float] = dict(pop_qs)

            catchment_regions = dict(
                CollectionCatchment.objects.filter(
                    id__in=list(total_by_catchment.keys()),
                ).values_list("id", "region_id")
            )
            for cid, total_mg in total_by_catchment.items():
                region_id = catchment_regions.get(cid)
                if region_id is None:
                    continue
                pop = region_pop.get(region_id)
                if pop and pop > 0:
                    amounts[cid] = convert_total_to_specific(total_mg, pop, ndigits=1)

    data = []
    for cid, row in best.items():
        system = row["collection_system"]
        no_collection = system == "No separate collection"
        amount = None if no_collection else amounts.get(cid)
        data.append(
            {
                "catchment_id": cid,
                "amount": amount,
                "no_collection": no_collection,
            }
        )
    return data


class ResidualCollectionAmountViewSet(WasteAtlasViewSet):
    """Return specific waste collected for residual waste (Karte 17).

    Example::

        GET /waste_collection/api/waste-atlas/residual-collection-amount/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, amount}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_collection_amount(country, year, ["Residual waste"], nuts_prefixes)
        serializer = CatchmentCollectionAmountSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteCollectionAmountViewSet(WasteAtlasViewSet):
    """Return specific waste collected for biowaste (Karte 18).

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-collection-amount/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, amount}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_collection_amount(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
            include_value_source=True,
            include_acpv_group_key=True,
        )
        serializer = CatchmentCollectionAmountSerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="acpv-outline-geojson")
    def acpv_outline_geojson(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        return Response(
            _get_biowaste_acpv_outline_geojson(country, year, nuts_prefixes)
        )


class GreenWasteCollectionAmountViewSet(WasteAtlasViewSet):
    """Return specific waste collected for green waste (Karte 22).

    Example::

        GET /waste_collection/api/waste-atlas/green-waste-collection-amount/?country=DE&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, amount, no_collection}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_green_waste_collection_amount(country, year, nuts_prefixes)
        serializer = CatchmentCollectionAmountSerializer(data, many=True)
        return Response(serializer.data)


def _get_min_bin_size(
    country, year, waste_categories, nuts_prefixes=(), include_missing_primary=False
):
    """Return per-catchment minimum bin size (L) for door-to-door collections.

    Picks the primary door-to-door collection per catchment using
    ``_COLLECTION_SYSTEM_PRIORITY`` and returns its ``min_bin_size`` value.
    Only door-to-door collections carry meaningful bin size data.
    """
    qs = _filter_by_waste_categories(
        Collection.objects.filter(
            _country_filter_q("catchment__", country),
            valid_from__year=year,
            collection_system__name="Door to door",
        ),
        waste_categories,
    )
    qs = _apply_nuts_prefix_filter(qs, nuts_prefixes, catchment_path="catchment__")
    rows = qs.values_list("catchment_id", "min_bin_size")

    best: dict[int, tuple[float | None, bool]] = {}
    for cid, size in rows:
        if cid not in best:
            best[cid] = (float(size) if size is not None else None, True)

    if include_missing_primary:
        best_system = _select_primary_collections(
            country,
            year,
            waste_categories,
            nuts_prefixes,
        )
        for cid, row in best_system.items():
            if cid not in best:
                best[cid] = (None, row["collection_system"] == "Door to door")

    return [
        {
            "catchment_id": cid,
            "min_bin_size": size,
            "is_door_to_door": is_door_to_door,
        }
        for cid, (size, is_door_to_door) in best.items()
    ]


def _get_required_bin_capacity(
    country, year, waste_categories, nuts_prefixes=(), include_missing_primary=False
):
    """Return per-catchment required specific bin capacity for door-to-door collections.

    Returns ``required_bin_capacity`` (L/reference) and
    ``required_bin_capacity_reference`` (person / household / property /
    not_specified) for the primary door-to-door collection per catchment.
    """
    qs = _filter_by_waste_categories(
        Collection.objects.filter(
            _country_filter_q("catchment__", country),
            valid_from__year=year,
            collection_system__name="Door to door",
        ),
        waste_categories,
    )
    qs = _apply_nuts_prefix_filter(qs, nuts_prefixes, catchment_path="catchment__")
    rows = qs.values_list(
        "catchment_id", "required_bin_capacity", "required_bin_capacity_reference"
    )

    best: dict[int, tuple[float | None, str | None, bool]] = {}
    for cid, cap, ref in rows:
        if cid not in best:
            best[cid] = (float(cap) if cap is not None else None, ref or None, True)

    if include_missing_primary:
        best_system = _select_primary_collections(
            country,
            year,
            waste_categories,
            nuts_prefixes,
        )
        for cid, row in best_system.items():
            if cid not in best:
                best[cid] = (None, None, row["collection_system"] == "Door to door")

    return [
        {
            "catchment_id": cid,
            "required_bin_capacity": cap,
            "required_bin_capacity_reference": ref,
            "is_door_to_door": is_door_to_door,
        }
        for cid, (cap, ref, is_door_to_door) in best.items()
    ]


class BiowasteMinBinSizeViewSet(WasteAtlasViewSet):
    """Return minimum bin size for biowaste door-to-door collections (Karte 23).

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-min-bin-size/?country=DE&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, min_bin_size}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_min_bin_size(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
            include_missing_primary=True,
        )
        serializer = CatchmentMinBinSizeSerializer(data, many=True)
        return Response(serializer.data)


class ResidualMinBinSizeViewSet(WasteAtlasViewSet):
    """Return minimum bin size for residual waste door-to-door collections (Karte 24).

    Example::

        GET /waste_collection/api/waste-atlas/residual-min-bin-size/?country=DE&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, min_bin_size}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_min_bin_size(country, year, ["Residual waste"], nuts_prefixes)
        serializer = CatchmentMinBinSizeSerializer(data, many=True)
        return Response(serializer.data)


class MinBinSizeRatioViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        bio = {
            r["catchment_id"]: r
            for r in _get_min_bin_size(
                country,
                year,
                ["Biowaste", "Food waste"],
                nuts_prefixes,
                include_missing_primary=True,
            )
        }
        res = {
            r["catchment_id"]: r
            for r in _get_min_bin_size(country, year, ["Residual waste"], nuts_prefixes)
        }
        all_ids = set(bio) | set(res)
        data = []
        for cid in all_ids:
            bio_size = bio.get(cid, {}).get("min_bin_size")
            residual_size = res.get(cid, {}).get("min_bin_size")
            ratio = None
            if (
                bio_size is not None
                and residual_size is not None
                and residual_size != 0
            ):
                ratio = bio_size / residual_size
            data.append(
                {
                    "catchment_id": cid,
                    "bio_min_bin_size": bio_size,
                    "residual_min_bin_size": residual_size,
                    "ratio": ratio,
                    "bio_is_door_to_door": bio.get(cid, {}).get("is_door_to_door"),
                    "residual_is_door_to_door": res.get(cid, {}).get("is_door_to_door"),
                }
            )
        serializer = CatchmentMinBinSizeRatioSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteRequiredBinCapacityViewSet(WasteAtlasViewSet):
    """Return required specific bin capacity for biowaste collections (Karte 25).

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-required-bin-capacity/?country=DE&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, required_bin_capacity, required_bin_capacity_reference}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_required_bin_capacity(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
            include_missing_primary=True,
        )
        serializer = CatchmentRequiredBinCapacitySerializer(data, many=True)
        return Response(serializer.data)


class ResidualRequiredBinCapacityViewSet(WasteAtlasViewSet):
    """Return required specific bin capacity for residual waste collections (Karte 26).

    Example::

        GET /waste_collection/api/waste-atlas/residual-required-bin-capacity/?country=DE&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, required_bin_capacity, required_bin_capacity_reference}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_required_bin_capacity(
            country, year, ["Residual waste"], nuts_prefixes
        )
        serializer = CatchmentRequiredBinCapacitySerializer(data, many=True)
        return Response(serializer.data)


_ORGANIC_CATEGORY_NAMES = ["Biowaste", "Food waste"] + _GREEN_WASTE_CATEGORY_NAMES


def _get_organic_amounts(country, year, nuts_prefixes=()):
    """Return per-catchment summed organic waste amount (kg/person/year).

    Sums bio/food waste from ``_get_collection_amount`` with green waste from
    ``_get_green_waste_collection_amount``.  Catchments present in either
    source are included; amounts are summed where both are available.
    """
    bio_rows = _get_collection_amount(
        country, year, ["Biowaste", "Food waste"], nuts_prefixes
    )
    green_rows = _get_green_waste_collection_amount(country, year, nuts_prefixes)

    bio_map = {
        r["catchment_id"]: r["amount"] for r in bio_rows if not r.get("no_collection")
    }
    green_map = {
        r["catchment_id"]: r["amount"] for r in green_rows if not r.get("no_collection")
    }

    all_ids = set(bio_map) | set(green_map)
    result = {}
    for cid in all_ids:
        b = bio_map.get(cid)
        g = green_map.get(cid)
        if b is not None and g is not None:
            result[cid] = b + g
        elif b is not None:
            result[cid] = b
        elif g is not None:
            result[cid] = g
        else:
            result[cid] = None
    return result


class OrganicCollectionAmountViewSet(WasteAtlasViewSet):
    """Return aggregated organic waste amount per catchment (Karte 27).

    Sums biowaste/food waste and green waste specific collection amounts
    into a single organic total (kg/person/year).

    Example::

        GET /waste_collection/api/waste-atlas/organic-collection-amount/?country=DE&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, amount}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        organic = _get_organic_amounts(country, year, nuts_prefixes)
        data = [{"catchment_id": cid, "amount": amt} for cid, amt in organic.items()]
        serializer = CatchmentCollectionAmountSerializer(data, many=True)
        return Response(serializer.data)


class OrganicWasteRatioViewSet(WasteAtlasViewSet):
    """Return organic / (organic + residual) ratio per catchment (Karte 28).

    Example::

        GET /waste_collection/api/waste-atlas/organic-waste-ratio/?country=DE&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, organic_amount, residual_amount, ratio}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        organic = _get_organic_amounts(country, year, nuts_prefixes)
        res_map = {
            r["catchment_id"]: r["amount"]
            for r in _get_collection_amount(
                country, year, ["Residual waste"], nuts_prefixes
            )
        }
        all_ids = set(organic) | set(res_map)
        data = []
        for cid in all_ids:
            o = organic.get(cid)
            r = res_map.get(cid)
            if o is not None and r is not None and (o + r) > 0:
                ratio = o / (o + r)
            else:
                ratio = None
            data.append(
                {
                    "catchment_id": cid,
                    "organic_amount": o,
                    "residual_amount": r,
                    "ratio": ratio,
                }
            )
        serializer = CatchmentOrganicRatioSerializer(data, many=True)
        return Response(serializer.data)


class WasteRatioViewSet(WasteAtlasViewSet):
    """Return biowaste / (biowaste + residual) ratio per catchment (Karte 19).

    Example::

        GET /waste_collection/api/waste-atlas/waste-ratio/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, bio_amount, residual_amount, ratio}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        bio = {
            r["catchment_id"]: r["amount"]
            for r in _get_collection_amount(
                country, year, ["Biowaste", "Food waste"], nuts_prefixes
            )
        }
        res = {
            r["catchment_id"]: r["amount"]
            for r in _get_collection_amount(
                country, year, ["Residual waste"], nuts_prefixes
            )
        }
        all_ids = set(bio) | set(res)
        data = []
        for cid in all_ids:
            b = bio.get(cid)
            r = res.get(cid)
            if b is not None and r is not None and (b + r) > 0:
                ratio = b / (b + r)
            else:
                ratio = None
            data.append(
                {
                    "catchment_id": cid,
                    "bio_amount": b,
                    "residual_amount": r,
                    "ratio": ratio,
                }
            )
        serializer = CatchmentWasteRatioSerializer(data, many=True)
        return Response(serializer.data)


class CollectionSupportViewSet(WasteAtlasViewSet):
    """Return combined paper + plastic bags status per catchment (Karte 7).

    Returns both statuses so the front-end can classify into the 2D
    combination matrix (paper × plastic).

    Example::

        GET /waste_collection/api/waste-atlas/collection-support/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, paper_bags, plastic_bags}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        best = _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
        )

        collection_ids = [
            row["collection_id"]
            for row in best.values()
            if row["collection_id"] is not None
        ]

        # Step 2: batch-fetch allowed/forbidden for both materials
        def _lookup(material_id):
            allowed = set(
                Collection.objects.filter(
                    id__in=collection_ids,
                    allowed_materials__id=material_id,
                ).values_list("id", flat=True)
            )
            forbidden = set(
                Collection.objects.filter(
                    id__in=collection_ids,
                    forbidden_materials__id=material_id,
                ).values_list("id", flat=True)
            )
            return allowed, forbidden

        paper_allowed, paper_forbidden = _lookup(_PAPER_BAGS_MATERIAL_ID)
        plastic_allowed, plastic_forbidden = _lookup(_PLASTIC_BAGS_MATERIAL_ID)

        def _status(collection_id, allowed_set, forbidden_set):
            if collection_id in allowed_set:
                return "allowed"
            if collection_id in forbidden_set:
                return "forbidden"
            return "no_data"

        # Step 3: build response
        data = []
        for cid, row in best.items():
            collection_id = row["collection_id"]
            system = row["collection_system"]
            if system == "No separate collection":
                paper = "no_collection"
                plastic = "no_collection"
            else:
                paper = _status(collection_id, paper_allowed, paper_forbidden)
                plastic = _status(collection_id, plastic_allowed, plastic_forbidden)
            data.append(
                {
                    "catchment_id": cid,
                    "paper_bags": paper,
                    "plastic_bags": plastic,
                }
            )

        serializer = CatchmentCollectionSupportSerializer(data, many=True)
        return Response(serializer.data)


class RegularPlasticCollectionSupportViewSet(WasteAtlasViewSet):
    """Return combined paper + regular-plastic bags status per catchment.

    Like CollectionSupportViewSet but uses material 18 (regular plastic bags)
    instead of material 17 (biodegradable) for the plastic bags slot.
    Used for Denmark-specific collection-support maps.

    Example::

        GET /waste_collection/api/waste-atlas/regular-plastic-collection-support/?country=DK&year=2023
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, paper_bags, plastic_bags}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        best = _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
        )

        collection_ids = [
            row["collection_id"]
            for row in best.values()
            if row["collection_id"] is not None
        ]

        def _lookup(material_id):
            allowed = set(
                Collection.objects.filter(
                    id__in=collection_ids,
                    allowed_materials__id=material_id,
                ).values_list("id", flat=True)
            )
            forbidden = set(
                Collection.objects.filter(
                    id__in=collection_ids,
                    forbidden_materials__id=material_id,
                ).values_list("id", flat=True)
            )
            return allowed, forbidden

        paper_allowed, paper_forbidden = _lookup(_PAPER_BAGS_MATERIAL_ID)
        plastic_allowed, plastic_forbidden = _lookup(_REGULAR_PLASTIC_BAGS_MATERIAL_ID)

        def _status(collection_id, allowed_set, forbidden_set):
            if collection_id in allowed_set:
                return "allowed"
            if collection_id in forbidden_set:
                return "forbidden"
            return "no_data"

        data = []
        for cid, row in best.items():
            collection_id = row["collection_id"]
            system = row["collection_system"]
            if system == "No separate collection":
                paper = "no_collection"
                plastic = "no_collection"
            else:
                paper = _status(collection_id, paper_allowed, paper_forbidden)
                plastic = _status(collection_id, plastic_allowed, plastic_forbidden)
            data.append(
                {
                    "catchment_id": cid,
                    "paper_bags": paper,
                    "plastic_bags": plastic,
                }
            )

        serializer = CatchmentCollectionSupportSerializer(data, many=True)
        return Response(serializer.data)


class PaperBagsStatusViewSet(WasteAtlasViewSet):
    """Return paper-bags allowed/forbidden status per catchment (Karte 5).

    Checks whether 'Collection Support Item: Paper bags' (material 19) appears
    in the collection's ``allowed_materials`` or ``forbidden_materials``.

    Example::

        GET /waste_collection/api/waste-atlas/paper-bags/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, status}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_material_status(
            country, year, _PAPER_BAGS_MATERIAL_ID, nuts_prefixes
        )
        serializer = CatchmentMaterialStatusSerializer(data, many=True)
        return Response(serializer.data)


class PlasticBagsStatusViewSet(WasteAtlasViewSet):
    """Return biodegradable plastic bags allowed/forbidden status (Karte 6).

    Checks whether 'Collection Support Item: Biodegradable plastic bags'
    (material 17) appears in ``allowed_materials`` or ``forbidden_materials``.

    Example::

        GET /waste_collection/api/waste-atlas/plastic-bags/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, status}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_material_status(
            country, year, _PLASTIC_BAGS_MATERIAL_ID, nuts_prefixes
        )
        serializer = CatchmentMaterialStatusSerializer(data, many=True)
        return Response(serializer.data)


class RegularPlasticBagsStatusViewSet(WasteAtlasViewSet):
    """Return regular (non-biodegradable) plastic bags allowed/forbidden status.

    Checks whether 'Collection Support Item: Plastic bags' (material 18) appears
    in the collection's ``allowed_materials`` or ``forbidden_materials``.

    Used for Denmark-specific maps where collections record regular plastic bags
    (material 18) rather than the biodegradable subtype (material 17).

    Example::

        GET /waste_collection/api/waste-atlas/regular-plastic-bags/?country=DK&year=2023
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, status}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        data = _get_material_status(
            country, year, _REGULAR_PLASTIC_BAGS_MATERIAL_ID, nuts_prefixes
        )
        serializer = CatchmentMaterialStatusSerializer(data, many=True)
        return Response(serializer.data)


class FoodWasteCategoryViewSet(WasteAtlasViewSet):
    """Return the allowed food waste category per catchment (Karte 4).

    Classifies each catchment's biowaste collection by which food waste
    materials are allowed in the collection (animal/plant, raw/processed).

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year of ``valid_from`` on the collection (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/food-waste-category/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, food_waste_category}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        best = _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
        )

        # Step 2: batch-fetch allowed material IDs (11-14) for selected collections
        collection_ids = [
            row["collection_id"]
            for row in best.values()
            if row["collection_id"] is not None
        ]
        collection_materials = Collection.objects.filter(
            id__in=collection_ids,
            allowed_materials__id__in=_FOOD_WASTE_MATERIAL_IDS,
        ).values_list("id", "allowed_materials__id")

        collection_material_map = {}  # collection_id -> set of material_ids
        for col_id, mat_id in collection_materials:
            collection_material_map.setdefault(col_id, set()).add(mat_id)

        # Step 3: classify and build response
        data = []
        for cid, row in best.items():
            col_id = row["collection_id"]
            system = row["collection_system"]
            if system == "No separate collection":
                category = "No separate collection"
            elif col_id and col_id in collection_material_map:
                category = _classify_food_waste(collection_material_map[col_id])
            else:
                category = system  # fallback to collection system name
            data.append({"catchment_id": cid, "food_waste_category": category})

        serializer = CatchmentFoodWasteCategorySerializer(data, many=True)
        return Response(serializer.data)


class ConnectionRateViewSet(WasteAtlasViewSet):
    """Return the connection rate for biowaste door-to-door collections (Karte 3).

    For each catchment, selects the primary biowaste/food-waste collection
    (door-to-door preferred) and returns the latest connection rate from the
    collection's version chain.

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year of ``valid_from`` on the collection (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/connection-rate/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array with connection rate and reporting year."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        best = _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
        )

        collection_ids = [row["collection_id"] for row in best.values()]
        rate_lookup = _latest_connection_rate_values(collection_ids)

        data = []
        for cid, row in best.items():
            col_id = row["collection_id"]
            system = row["collection_system"]
            is_d2d = system == "Door to door"
            rate = rate_lookup.get(col_id)
            avg = rate["average"] if rate is not None else None
            data.append(
                {
                    "catchment_id": cid,
                    "connection_rate": avg / 100.0 if avg is not None else None,
                    "is_door_to_door": is_d2d,
                    "reporting_year": rate["year"] if rate is not None else None,
                }
            )

        serializer = CatchmentConnectionRateSerializer(data, many=True)
        return Response(serializer.data)


class ConnectionTypeViewSet(WasteAtlasViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        data = []
        for cid, row in _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
            extra_fields=("connection_type",),
        ).items():
            value = (
                "no_bio_collection"
                if row["collection_system"] == "No separate collection"
                else row["connection_type"]
            )
            data.append({"catchment_id": cid, "connection_type": value})
        serializer = CatchmentConnectionTypeSerializer(data, many=True)
        return Response(serializer.data)


class CatchmentPopulationViewSet(WasteAtlasViewSet):
    """Return population and population density for catchments with waste collections.

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year filter applied to both ``valid_from`` on the collection
      and the ``date`` on the attribute value (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/population/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, population, population_density}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)
        population_attribute_id = _resolved_population_attribute_id()

        qs = (
            CollectionCatchment.objects.filter(
                _country_filter_q("", country),
                collections__valid_from__year=year,
            )
            .distinct()
            .values_list("id", flat=False)
        )

        # Subqueries for population and population density
        pop_sq = RegionAttributeValue.objects.filter(
            region_id=OuterRef("region_id"),
            property_id=population_attribute_id,
            date__year=year,
        ).values("value")[:1]

        density_sq = RegionAttributeValue.objects.filter(
            region_id=OuterRef("region_id"),
            property_id=_resolved_population_density_attribute_id(),
            date__year=year,
        ).values("value")[:1]

        qs = (
            CollectionCatchment.objects.filter(
                _country_filter_q("", country),
                collections__valid_from__year=year,
            )
            .distinct()
            .annotate(
                population=Subquery(pop_sq, output_field=FloatField()),
                population_density=Subquery(density_sq, output_field=FloatField()),
            )
            .values("id", "population", "population_density")
        )
        qs = _apply_nuts_prefix_filter(qs, nuts_prefixes)

        data = [
            {
                "catchment_id": row["id"],
                "population": row["population"],
                "population_density": row["population_density"],
            }
            for row in qs
        ]
        serializer = CatchmentPopulationSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteImpurityViewSet(WasteAtlasViewSet):
    """Return the biowaste impurity rate per catchment (Catalonia KPI).

    For each catchment, selects the primary biowaste collection and returns
    its impurity rate from ``CollectionPropertyValue`` (property:
    'biowaste impurity rate').

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year of ``valid_from`` on the collection (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-impurity/?country=ES&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, impurity_rate, no_collection}."""
        country, year = _parse_country_year(request)
        collection_year = int(request.query_params.get("collection_year", year))
        nuts_prefixes = _parse_nuts_prefixes(request)

        best = _select_primary_collections(
            country,
            collection_year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
        )

        collection_ids = [row["collection_id"] for row in best.values()]
        cpv_qs = (
            CollectionPropertyValue.objects.filter(
                collection_id__in=collection_ids,
                property__name=BIOWASTE_IMPURITY_RATE_PROPERTY_NAME,
                year=year,
            )
            .order_by("collection_id", "-year")
            .distinct("collection_id")
            .values_list("collection_id", "average")
        )
        rate_lookup = dict(cpv_qs)

        data = []
        for cid, row in best.items():
            col_id = row["collection_id"]
            system = row["collection_system"]
            no_collection = system == "No separate collection"
            avg = None if no_collection else rate_lookup.get(col_id)
            data.append(
                {
                    "catchment_id": cid,
                    "impurity_rate": avg,
                    "no_collection": no_collection,
                }
            )

        serializer = CatchmentBiowasteImpuritySerializer(data, many=True)
        return Response(serializer.data)


class WeeklyBpAccessDaysViewSet(WasteAtlasViewSet):
    """Return weekly bring-point access days per catchment (Catalonia KPI).

    For each catchment, selects the primary biowaste collection and returns
    the weekly bring-point access days from ``CollectionPropertyValue``
    (property: 'weekly bring-point access days').

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year of ``valid_from`` on the collection (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/weekly-bp-access-days/?country=ES&year=2024
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, weekly_access_days, has_bring_point}."""
        country, year = _parse_country_year(request)
        nuts_prefixes = _parse_nuts_prefixes(request)

        best = _select_primary_collections(
            country,
            year,
            ["Biowaste", "Food waste"],
            nuts_prefixes,
        )

        collection_ids = [row["collection_id"] for row in best.values()]
        cpv_qs = (
            CollectionPropertyValue.objects.filter(
                collection_id__in=collection_ids,
                property__name=WEEKLY_BP_ACCESS_DAYS_PROPERTY_NAME,
                year=year,
            )
            .order_by("collection_id", "-year")
            .distinct("collection_id")
            .values_list("collection_id", "average")
        )
        days_lookup = dict(cpv_qs)

        _BP_SYSTEMS = {"Bring point", "Mixed door-to-door and bring point"}

        data = []
        for cid, row in best.items():
            col_id = row["collection_id"]
            system = row["collection_system"]
            has_bp = system in _BP_SYSTEMS
            avg = days_lookup.get(col_id) if has_bp else None
            data.append(
                {
                    "catchment_id": cid,
                    "weekly_access_days": avg,
                    "has_bring_point": has_bp,
                }
            )

        serializer = CatchmentWeeklyBpAccessDaysSerializer(data, many=True)
        return Response(serializer.data)
