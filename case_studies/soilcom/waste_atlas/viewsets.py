from django.db.models import (
    Case,
    CharField,
    Exists,
    F,
    FloatField,
    OuterRef,
    Subquery,
    Value,
    When,
)
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from case_studies.soilcom.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
)
from maps.db_functions import SimplifyPreserveTopology
from maps.models import LauRegion, NutsRegion, RegionAttributeValue

from .serializers import (
    GEOMETRY_SIMPLIFY_TOLERANCE,
    CatchmentCollectionAmountSerializer,
    CatchmentCollectionCountSerializer,
    CatchmentCollectionSupportSerializer,
    CatchmentCollectionSystemSerializer,
    CatchmentCombinedCollectionCountSerializer,
    CatchmentCombinedFeeSystemSerializer,
    CatchmentCombinedFrequencySerializer,
    CatchmentConnectionRateSerializer,
    CatchmentFeeSystemSerializer,
    CatchmentFoodWasteCategorySerializer,
    CatchmentFrequencyTypeSerializer,
    CatchmentGeometrySerializer,
    CatchmentMaterialStatusSerializer,
    CatchmentOrgaLevelSerializer,
    CatchmentPopulationSerializer,
    CatchmentWasteRatioSerializer,
)

# Material IDs for food waste classification (Karte 4)
_FOOD_WASTE_MATERIAL_IDS = {11, 12, 13, 14}

# Material IDs for collection support items (Karte 5, 6)
_PAPER_BAGS_MATERIAL_ID = 19
_PLASTIC_BAGS_MATERIAL_ID = 17

# Property ID for "Connection rate" (properties_property table)
CONNECTION_RATE_PROPERTY_ID = 4

# Priority for picking the primary collection system per catchment.
# Lower number = higher priority.
_COLLECTION_SYSTEM_PRIORITY = {
    "Door to door": 1,
    "Bring point": 2,
    "Recycling centre": 3,
    "On demand kerbside collection": 4,
    "Home-composting": 5,
    "No separate collection": 6,
}

# Attribute IDs for population data (maps_attribute table)
POPULATION_ATTRIBUTE_ID = 3
POPULATION_DENSITY_ATTRIBUTE_ID = 2


def _parse_country_year(request):
    """Extract and validate country/year query params with defaults."""
    country = request.query_params.get("country", "DE")
    year = request.query_params.get("year", "2022")
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = 2022
    return country, year


class CatchmentViewSet(viewsets.ReadOnlyModelViewSet):
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
        return (
            CollectionCatchment.objects.filter(
                collections__valid_from__year=year,
                region__country=country,
                region__borders__isnull=False,
            )
            .distinct()
            .select_related("region", "region__borders")
        )

    @action(detail=False, methods=["get"])
    def geojson(self, request, *args, **kwargs):
        """Return a GeoJSON FeatureCollection of matching catchments."""
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.annotate(
            simplified_geom=SimplifyPreserveTopology(
                F("region__borders__geom"),
                GEOMETRY_SIMPLIFY_TOLERANCE,
            )
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class OrgaLevelViewSet(viewsets.ViewSet):
    """Return the organizational level for catchments with waste collections (Karte 1).

    Determines whether each catchment's region is a NUTS region
    (Landkreise & kreisfreie Städte), a LAU region (Kommunalebene),
    or an individual catchment.

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year of ``valid_from`` on the collection (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/orga-level/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, orga_level}."""
        country, year = _parse_country_year(request)

        nuts_exists = Exists(
            NutsRegion.objects.filter(region_ptr_id=OuterRef("region_id"))
        )
        lau_exists = Exists(
            LauRegion.objects.filter(region_ptr_id=OuterRef("region_id"))
        )

        qs = (
            CollectionCatchment.objects.filter(
                collections__valid_from__year=year,
                region__country=country,
            )
            .distinct()
            .annotate(
                orga_level=Case(
                    When(nuts_exists, then=Value("nuts")),
                    When(lau_exists, then=Value("lau")),
                    default=Value("individual"),
                    output_field=CharField(),
                )
            )
            .values("id", "orga_level")
        )

        data = [
            {"catchment_id": row["id"], "orga_level": row["orga_level"]} for row in qs
        ]
        serializer = CatchmentOrgaLevelSerializer(data, many=True)
        return Response(serializer.data)


class CollectionSystemViewSet(viewsets.ViewSet):
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

        rows = (
            Collection.objects.filter(
                valid_from__year=year,
                catchment__region__country=country,
                waste_stream__category__name__in=["Biowaste", "Food waste"],
            )
            .select_related("collection_system")
            .values_list("catchment_id", "collection_system__name")
        )

        best = {}
        for cid, system in rows:
            p = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
            if cid not in best or p < best[cid][1]:
                best[cid] = (system, p)

        data = [
            {"catchment_id": cid, "collection_system": val[0]}
            for cid, val in best.items()
        ]
        serializer = CatchmentCollectionSystemSerializer(data, many=True)
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


def _get_material_status(country, year, material_id):
    """Return per-catchment allowed/forbidden status for a given material.

    Returns a list of dicts: ``[{catchment_id, status}]`` where *status* is
    one of ``'allowed'``, ``'forbidden'``, ``'No separate collection'``,
    or ``'no_data'``.
    """
    from case_studies.soilcom.models import WasteStream

    # Step 1: pick primary bio/food waste collection per catchment
    rows = (
        Collection.objects.filter(
            valid_from__year=year,
            catchment__region__country=country,
            waste_stream__category__name__in=["Biowaste", "Food waste"],
        )
        .select_related("collection_system")
        .values_list("catchment_id", "waste_stream_id", "collection_system__name")
    )

    best = {}  # catchment_id -> (waste_stream_id, system, priority)
    for cid, ws_id, system in rows:
        p = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
        if cid not in best or p < best[cid][2]:
            best[cid] = (ws_id, system, p)

    ws_ids = [v[0] for v in best.values() if v[0] is not None]

    # Step 2: batch-fetch allowed / forbidden sets for the target material
    allowed_ws = set(
        WasteStream.objects.filter(
            id__in=ws_ids, allowed_materials__id=material_id
        ).values_list("id", flat=True)
    )
    forbidden_ws = set(
        WasteStream.objects.filter(
            id__in=ws_ids, forbidden_materials__id=material_id
        ).values_list("id", flat=True)
    )

    # Step 3: classify
    data = []
    for cid, (ws_id, system, _) in best.items():
        if system == "No separate collection":
            status = "No separate collection"
        elif ws_id in allowed_ws:
            status = "allowed"
        elif ws_id in forbidden_ws:
            status = "forbidden"
        else:
            status = "no_data"
        data.append({"catchment_id": cid, "status": status})
    return data


def _get_collection_count(country, year, waste_categories):
    """Return per-catchment annual collection count for the given waste categories.

    For door-to-door collections, sums ``CollectionCountOptions.standard``
    across all seasons.  Also flags whether the counts vary by season.
    Non-door-to-door catchments are excluded (they have no frequency data).
    """
    rows = Collection.objects.filter(
        valid_from__year=year,
        catchment__region__country=country,
        waste_stream__category__name__in=waste_categories,
        collection_system__name="Door to door",
        frequency__isnull=False,
    ).values_list(
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
            }
        )
    return data


def _get_frequency_type(country, year, waste_categories):
    """Return per-catchment frequency type for the given waste categories.

    For door-to-door collections, returns the ``CollectionFrequency.type``;
    for other systems, returns the collection system name.
    """
    rows = (
        Collection.objects.filter(
            valid_from__year=year,
            catchment__region__country=country,
            waste_stream__category__name__in=waste_categories,
        )
        .select_related("collection_system", "frequency")
        .values_list(
            "catchment_id",
            "collection_system__name",
            "frequency__type",
        )
    )

    best = {}  # catchment_id -> (system, freq_type, priority)
    for cid, system, freq_type in rows:
        p = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
        if cid not in best or p < best[cid][2]:
            best[cid] = (system, freq_type, p)

    data = []
    for cid, (system, freq_type, _) in best.items():
        if system == "Door to door" and freq_type:
            val = freq_type
        else:
            val = system
        data.append({"catchment_id": cid, "frequency_type": val})
    return data


class ResidualFrequencyTypeViewSet(viewsets.ViewSet):
    """Return collection frequency type for residual waste (Karte 8).

    Example::

        GET /waste_collection/api/waste-atlas/residual-frequency-type/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, frequency_type}."""
        country, year = _parse_country_year(request)
        data = _get_frequency_type(country, year, ["Residual waste"])
        serializer = CatchmentFrequencyTypeSerializer(data, many=True)
        return Response(serializer.data)


class CombinedFrequencyTypeViewSet(viewsets.ViewSet):
    """Return combined bio + residual frequency type per catchment (Karte 10).

    Example::

        GET /waste_collection/api/waste-atlas/combined-frequency-type/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, bio_frequency, residual_frequency}."""
        country, year = _parse_country_year(request)
        bio = {
            r["catchment_id"]: r["frequency_type"]
            for r in _get_frequency_type(country, year, ["Biowaste", "Food waste"])
        }
        res = {
            r["catchment_id"]: r["frequency_type"]
            for r in _get_frequency_type(country, year, ["Residual waste"])
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


class BiowasteFrequencyTypeViewSet(viewsets.ViewSet):
    """Return collection frequency type for biowaste (Karte 9).

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-frequency-type/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, frequency_type}."""
        country, year = _parse_country_year(request)
        data = _get_frequency_type(country, year, ["Biowaste", "Food waste"])
        serializer = CatchmentFrequencyTypeSerializer(data, many=True)
        return Response(serializer.data)


class ResidualCollectionCountViewSet(viewsets.ViewSet):
    """Return annual collection count for residual waste (Karte 11).

    Example::

        GET /waste_collection/api/waste-atlas/residual-collection-count/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, collection_count, has_seasonal_variation}."""
        country, year = _parse_country_year(request)
        data = _get_collection_count(country, year, ["Residual waste"])
        serializer = CatchmentCollectionCountSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteCollectionCountViewSet(viewsets.ViewSet):
    """Return annual collection count for biowaste (Karte 12).

    Includes non-door-to-door catchments with ``collection_count=null``.

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-collection-count/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, collection_count, has_seasonal_variation}."""
        country, year = _parse_country_year(request)
        door_to_door = _get_collection_count(country, year, ["Biowaste", "Food waste"])
        d2d_ids = {r["catchment_id"] for r in door_to_door}

        # Include non-door-to-door biowaste catchments.
        all_bio = Collection.objects.filter(
            valid_from__year=year,
            catchment__region__country=country,
            waste_stream__category__name__in=["Biowaste", "Food waste"],
        ).values_list("catchment_id", "collection_system__name")
        best_system: dict[int, tuple[str, int]] = {}
        for cid, system in all_bio:
            p = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
            if cid not in best_system or p < best_system[cid][1]:
                best_system[cid] = (system, p)

        for cid, (_system, _) in best_system.items():
            if cid not in d2d_ids:
                door_to_door.append(
                    {
                        "catchment_id": cid,
                        "collection_count": None,
                        "has_seasonal_variation": False,
                    }
                )

        serializer = CatchmentCollectionCountSerializer(door_to_door, many=True)
        return Response(serializer.data)


class CombinedCollectionCountViewSet(viewsets.ViewSet):
    """Return combined bio + residual collection count per catchment (Karte 13).

    Example::

        GET /waste_collection/api/waste-atlas/combined-collection-count/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, bio_count, residual_count}."""
        country, year = _parse_country_year(request)
        bio = {
            r["catchment_id"]: r["collection_count"]
            for r in _get_collection_count(country, year, ["Biowaste", "Food waste"])
        }
        res = {
            r["catchment_id"]: r["collection_count"]
            for r in _get_collection_count(country, year, ["Residual waste"])
        }
        all_ids = set(bio) | set(res)
        data = [
            {
                "catchment_id": cid,
                "bio_count": bio.get(cid),
                "residual_count": res.get(cid),
            }
            for cid in all_ids
        ]
        serializer = CatchmentCombinedCollectionCountSerializer(data, many=True)
        return Response(serializer.data)


def _get_fee_system(country, year, waste_categories):
    """Return per-catchment fee system for the given waste categories.

    For biowaste, non-door-to-door catchments return the collection
    system name instead of the fee system.
    """
    rows = (
        Collection.objects.filter(
            valid_from__year=year,
            catchment__region__country=country,
            waste_stream__category__name__in=waste_categories,
        )
        .select_related("collection_system", "fee_system")
        .values_list(
            "catchment_id",
            "collection_system__name",
            "fee_system__name",
        )
    )

    best: dict[int, tuple[str, str | None, int]] = {}
    for cid, system, fee in rows:
        p = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
        if cid not in best or p < best[cid][2]:
            best[cid] = (system, fee, p)

    data = []
    for cid, (system, fee, _) in best.items():
        if system == "No separate collection":
            val = "No separate collection"
        elif fee:
            val = fee
        else:
            val = "no_data"
        data.append({"catchment_id": cid, "fee_system": val})
    return data


class ResidualFeeSystemViewSet(viewsets.ViewSet):
    """Return fee system for residual waste per catchment (Karte 14).

    Example::

        GET /waste_collection/api/waste-atlas/residual-fee-system/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, fee_system}."""
        country, year = _parse_country_year(request)
        data = _get_fee_system(country, year, ["Residual waste"])
        serializer = CatchmentFeeSystemSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteFeeSystemViewSet(viewsets.ViewSet):
    """Return fee system for biowaste per catchment (Karte 15).

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-fee-system/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, fee_system}."""
        country, year = _parse_country_year(request)
        data = _get_fee_system(country, year, ["Biowaste", "Food waste"])
        serializer = CatchmentFeeSystemSerializer(data, many=True)
        return Response(serializer.data)


class CombinedFeeSystemViewSet(viewsets.ViewSet):
    """Return combined bio + residual fee system per catchment (Karte 16).

    Example::

        GET /waste_collection/api/waste-atlas/combined-fee-system/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, bio_fee, residual_fee}."""
        country, year = _parse_country_year(request)
        bio = {
            r["catchment_id"]: r["fee_system"]
            for r in _get_fee_system(country, year, ["Biowaste", "Food waste"])
        }
        res = {
            r["catchment_id"]: r["fee_system"]
            for r in _get_fee_system(country, year, ["Residual waste"])
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


# Property IDs (properties_property table)
_SPECIFIC_WASTE_PROPERTY_ID = 1  # "specific waste collected" (kg/person/a)
_TOTAL_WASTE_PROPERTY_ID = 9  # "total waste collected" (Mg/a)
_MG_TO_KG = 1000  # conversion factor: 1 Mg = 1000 kg

# For the 2022 atlas version the actual 2022 amounts were not yet
# available, so the average of 2020 and 2021 is used instead.
_2022_AMOUNT_YEARS = (2020, 2021)


def _get_collection_amount(country, year, waste_categories):
    """Return per-catchment collection amount in kg/person/year.

    Strategy varies by atlas year:

    * **2022** – average of ``specific waste collected`` (property 1) over
      2020–2021, with ``AggregatedCollectionPropertyValue`` as fallback.
    * **2024** – ``specific waste collected`` for 2024 directly.  Where
      only ``total waste collected`` (property 9, in Mg/a) is available
      the specific amount is derived as ``total * 1000 / population``.

    Data is looked up across **all** collections for a catchment (any
    year) so that values attached to an earlier collection version are
    still found.
    """
    # ------------------------------------------------------------------
    # Step 1: pick primary collection system per catchment
    # ------------------------------------------------------------------
    rows = (
        Collection.objects.filter(
            valid_from__year=year,
            catchment__region__country=country,
            waste_stream__category__name__in=waste_categories,
        )
        .select_related("collection_system")
        .values_list("id", "catchment_id", "collection_system__name")
    )

    best: dict[int, tuple[int, str, int]] = {}
    for col_id, cid, system in rows:
        p = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
        if cid not in best or p < best[cid][2]:
            best[cid] = (col_id, system, p)

    catchment_ids = list(best.keys())

    # ------------------------------------------------------------------
    # Step 2: map catchments → all collection IDs (any year)
    # ------------------------------------------------------------------
    all_col_rows = Collection.objects.filter(
        catchment_id__in=catchment_ids,
        waste_stream__category__name__in=waste_categories,
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
    if year == 2022:
        amounts = _amounts_for_2022(all_collection_ids, col_to_cid)
    else:
        amounts = _amounts_for_2024(year, all_collection_ids, col_to_cid, catchment_ids)

    # ------------------------------------------------------------------
    # Step 4: build result list
    # ------------------------------------------------------------------
    data = []
    for cid, (_col_id, system, _) in best.items():
        if system == "No separate collection":
            amount = None
        else:
            amount = amounts.get(cid)
        data.append({"catchment_id": cid, "amount": amount})
    return data


def _amounts_for_2022(all_collection_ids, col_to_cid):
    """Average of *specific waste collected* over 2020–2021 per catchment."""
    cpv_qs = (
        CollectionPropertyValue.objects.filter(
            collection_id__in=all_collection_ids,
            property_id=_SPECIFIC_WASTE_PROPERTY_ID,
            year__in=_2022_AMOUNT_YEARS,
        )
        .exclude(average=0)
        .values_list("collection_id", "average")
    )
    cpv_by_catchment: dict[int, list[float]] = {}
    for col_id, avg in cpv_qs:
        cid = col_to_cid.get(col_id)
        if cid is not None:
            cpv_by_catchment.setdefault(cid, []).append(avg)

    # Aggregated fallback
    missing_cols = {
        col_id for col_id, cid in col_to_cid.items() if cid not in cpv_by_catchment
    }
    if missing_cols:
        agg_qs = (
            AggregatedCollectionPropertyValue.objects.filter(
                collections__id__in=missing_cols,
                property_id=_SPECIFIC_WASTE_PROPERTY_ID,
                year__in=_2022_AMOUNT_YEARS,
            )
            .exclude(average=0)
            .values_list("collections__id", "average")
        )
        for col_id, avg in agg_qs:
            cid = col_to_cid.get(col_id)
            if cid is not None and cid not in cpv_by_catchment:
                cpv_by_catchment.setdefault(cid, []).append(avg)

    return {cid: sum(vals) / len(vals) for cid, vals in cpv_by_catchment.items()}


def _amounts_for_2024(year, all_collection_ids, col_to_cid, catchment_ids):
    """Specific waste collected for *year* directly, with total/population fallback."""
    # --- direct specific values (property 1, exact year) ---------------
    cpv_qs = (
        CollectionPropertyValue.objects.filter(
            collection_id__in=all_collection_ids,
            property_id=_SPECIFIC_WASTE_PROPERTY_ID,
            year=year,
        )
        .exclude(average=0)
        .values_list("collection_id", "average")
    )
    result: dict[int, float] = {}
    for col_id, avg in cpv_qs:
        cid = col_to_cid.get(col_id)
        if cid is not None and cid not in result:
            result[cid] = avg

    # --- fallback: total waste (property 9) / population ---------------
    missing_cids = [cid for cid in catchment_ids if cid not in result]
    if not missing_cids:
        return result

    # Collect total waste values keyed by catchment
    missing_cols = {
        col_id for col_id, cid in col_to_cid.items() if cid in set(missing_cids)
    }
    total_qs = (
        CollectionPropertyValue.objects.filter(
            collection_id__in=missing_cols,
            property_id=_TOTAL_WASTE_PROPERTY_ID,
            year=year,
        )
        .exclude(average=0)
        .values_list("collection_id", "average")
    )
    total_by_catchment: dict[int, float] = {}
    for col_id, avg in total_qs:
        cid = col_to_cid.get(col_id)
        if cid is not None and cid not in total_by_catchment:
            total_by_catchment[cid] = avg

    if not total_by_catchment:
        return result

    # Load population for those catchments
    pop_qs = (
        RegionAttributeValue.objects.filter(
            region__catchment__id__in=list(total_by_catchment.keys()),
            attribute_id=POPULATION_ATTRIBUTE_ID,
        )
        .order_by("region_id", "-date")
        .distinct("region_id")
        .values_list("region_id", "value")
    )
    # Map region_id → population
    region_pop: dict[int, float] = dict(pop_qs)

    # Map catchment_id → region_id
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
            result[cid] = round(total_mg * _MG_TO_KG / pop, 1)

    return result


class ResidualCollectionAmountViewSet(viewsets.ViewSet):
    """Return specific waste collected for residual waste (Karte 17).

    Example::

        GET /waste_collection/api/waste-atlas/residual-collection-amount/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, amount}."""
        country, year = _parse_country_year(request)
        data = _get_collection_amount(country, year, ["Residual waste"])
        serializer = CatchmentCollectionAmountSerializer(data, many=True)
        return Response(serializer.data)


class BiowasteCollectionAmountViewSet(viewsets.ViewSet):
    """Return specific waste collected for biowaste (Karte 18).

    Example::

        GET /waste_collection/api/waste-atlas/biowaste-collection-amount/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, amount}."""
        country, year = _parse_country_year(request)
        data = _get_collection_amount(country, year, ["Biowaste", "Food waste"])
        serializer = CatchmentCollectionAmountSerializer(data, many=True)
        return Response(serializer.data)


class WasteRatioViewSet(viewsets.ViewSet):
    """Return biowaste / (biowaste + residual) ratio per catchment (Karte 19).

    Example::

        GET /waste_collection/api/waste-atlas/waste-ratio/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, bio_amount, residual_amount, ratio}."""
        country, year = _parse_country_year(request)
        bio = {
            r["catchment_id"]: r["amount"]
            for r in _get_collection_amount(country, year, ["Biowaste", "Food waste"])
        }
        res = {
            r["catchment_id"]: r["amount"]
            for r in _get_collection_amount(country, year, ["Residual waste"])
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


class CollectionSupportViewSet(viewsets.ViewSet):
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

        from case_studies.soilcom.models import WasteStream

        # Step 1: pick primary bio/food waste collection per catchment
        rows = (
            Collection.objects.filter(
                valid_from__year=year,
                catchment__region__country=country,
                waste_stream__category__name__in=["Biowaste", "Food waste"],
            )
            .select_related("collection_system")
            .values_list("catchment_id", "waste_stream_id", "collection_system__name")
        )

        best = {}  # catchment_id -> (waste_stream_id, system, priority)
        for cid, ws_id, system in rows:
            p = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
            if cid not in best or p < best[cid][2]:
                best[cid] = (ws_id, system, p)

        ws_ids = [v[0] for v in best.values() if v[0] is not None]

        # Step 2: batch-fetch allowed/forbidden for both materials
        def _lookup(material_id):
            allowed = set(
                WasteStream.objects.filter(
                    id__in=ws_ids, allowed_materials__id=material_id
                ).values_list("id", flat=True)
            )
            forbidden = set(
                WasteStream.objects.filter(
                    id__in=ws_ids, forbidden_materials__id=material_id
                ).values_list("id", flat=True)
            )
            return allowed, forbidden

        paper_allowed, paper_forbidden = _lookup(_PAPER_BAGS_MATERIAL_ID)
        plastic_allowed, plastic_forbidden = _lookup(_PLASTIC_BAGS_MATERIAL_ID)

        def _status(ws_id, allowed_set, forbidden_set):
            if ws_id in allowed_set:
                return "allowed"
            if ws_id in forbidden_set:
                return "forbidden"
            return "no_data"

        # Step 3: build response
        data = []
        for cid, (ws_id, system, _) in best.items():
            if system == "No separate collection":
                paper = "no_collection"
                plastic = "no_collection"
            else:
                paper = _status(ws_id, paper_allowed, paper_forbidden)
                plastic = _status(ws_id, plastic_allowed, plastic_forbidden)
            data.append(
                {
                    "catchment_id": cid,
                    "paper_bags": paper,
                    "plastic_bags": plastic,
                }
            )

        serializer = CatchmentCollectionSupportSerializer(data, many=True)
        return Response(serializer.data)


class PaperBagsStatusViewSet(viewsets.ViewSet):
    """Return paper-bags allowed/forbidden status per catchment (Karte 5).

    Checks whether 'Collection Support Item: Paper bags' (material 19) appears
    in the waste stream's ``allowed_materials`` or ``forbidden_materials``.

    Example::

        GET /waste_collection/api/waste-atlas/paper-bags/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, status}."""
        country, year = _parse_country_year(request)
        data = _get_material_status(country, year, _PAPER_BAGS_MATERIAL_ID)
        serializer = CatchmentMaterialStatusSerializer(data, many=True)
        return Response(serializer.data)


class PlasticBagsStatusViewSet(viewsets.ViewSet):
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
        data = _get_material_status(country, year, _PLASTIC_BAGS_MATERIAL_ID)
        serializer = CatchmentMaterialStatusSerializer(data, many=True)
        return Response(serializer.data)


class FoodWasteCategoryViewSet(viewsets.ViewSet):
    """Return the allowed food waste category per catchment (Karte 4).

    Classifies each catchment's biowaste collection by which food waste
    materials are allowed in the waste stream (animal/plant, raw/processed).

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

        # Step 1: pick primary bio/food waste collection per catchment
        rows = (
            Collection.objects.filter(
                valid_from__year=year,
                catchment__region__country=country,
                waste_stream__category__name__in=["Biowaste", "Food waste"],
            )
            .select_related("collection_system")
            .values_list(
                "id", "catchment_id", "waste_stream_id", "collection_system__name"
            )
        )

        best = {}  # catchment_id -> (collection_id, waste_stream_id, system, priority)
        for col_id, cid, ws_id, system in rows:
            p = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
            if cid not in best or p < best[cid][3]:
                best[cid] = (col_id, ws_id, system, p)

        # Step 2: batch-fetch allowed material IDs (11-14) for selected waste streams
        from case_studies.soilcom.models import WasteStream

        ws_ids = [v[1] for v in best.values() if v[1] is not None]
        ws_materials = WasteStream.objects.filter(
            id__in=ws_ids,
            allowed_materials__id__in=_FOOD_WASTE_MATERIAL_IDS,
        ).values_list("id", "allowed_materials__id")

        ws_mat_map = {}  # waste_stream_id -> set of material_ids
        for ws_id, mat_id in ws_materials:
            ws_mat_map.setdefault(ws_id, set()).add(mat_id)

        # Step 3: classify and build response
        data = []
        for cid, (_col_id, ws_id, system, _) in best.items():
            if system == "No separate collection":
                category = "No separate collection"
            elif ws_id and ws_id in ws_mat_map:
                category = _classify_food_waste(ws_mat_map[ws_id])
            else:
                category = system  # fallback to collection system name
            data.append({"catchment_id": cid, "food_waste_category": category})

        serializer = CatchmentFoodWasteCategorySerializer(data, many=True)
        return Response(serializer.data)


class ConnectionRateViewSet(viewsets.ViewSet):
    """Return the connection rate for biowaste door-to-door collections (Karte 3).

    For each catchment, selects the primary biowaste/food-waste collection
    (door-to-door preferred) and returns its connection rate from
    ``CollectionPropertyValue`` (property: 'Connection rate').

    Supports query parameters:

    - ``country``: ISO country code filter (default: ``DE``)
    - ``year``: Year of ``valid_from`` on the collection (default: ``2022``)

    Example::

        GET /waste_collection/api/waste-atlas/connection-rate/?country=DE&year=2022
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """Return a JSON array of {catchment_id, connection_rate, is_door_to_door}."""
        country, year = _parse_country_year(request)

        # Step 1: pick primary bio/food waste collection per catchment
        rows = (
            Collection.objects.filter(
                valid_from__year=year,
                catchment__region__country=country,
                waste_stream__category__name__in=["Biowaste", "Food waste"],
            )
            .select_related("collection_system")
            .values_list("id", "catchment_id", "collection_system__name")
        )

        best = {}  # catchment_id -> (collection_id, system_name, priority)
        for col_id, cid, system in rows:
            p = _COLLECTION_SYSTEM_PRIORITY.get(system, 99)
            if cid not in best or p < best[cid][2]:
                best[cid] = (col_id, system, p)

        # Step 2: batch-fetch connection rate values for the selected collections
        collection_ids = [v[0] for v in best.values()]
        cpv_qs = (
            CollectionPropertyValue.objects.filter(
                collection_id__in=collection_ids,
                property_id=CONNECTION_RATE_PROPERTY_ID,
            )
            .order_by("collection_id", "-year")
            .distinct("collection_id")
            .values_list("collection_id", "average")
        )
        rate_lookup = dict(cpv_qs)

        # Step 3: build response
        data = []
        for cid, (col_id, system, _) in best.items():
            is_d2d = system == "Door to door"
            avg = rate_lookup.get(col_id)
            data.append(
                {
                    "catchment_id": cid,
                    "connection_rate": avg / 100.0 if avg is not None else None,
                    "is_door_to_door": is_d2d,
                }
            )

        serializer = CatchmentConnectionRateSerializer(data, many=True)
        return Response(serializer.data)


class CatchmentPopulationViewSet(viewsets.ViewSet):
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

        qs = (
            CollectionCatchment.objects.filter(
                collections__valid_from__year=year,
                region__country=country,
            )
            .distinct()
            .values_list("id", flat=False)
        )

        # Subqueries for population and population density
        pop_sq = RegionAttributeValue.objects.filter(
            region_id=OuterRef("region_id"),
            attribute_id=POPULATION_ATTRIBUTE_ID,
            date__year=year,
        ).values("value")[:1]

        density_sq = RegionAttributeValue.objects.filter(
            region_id=OuterRef("region_id"),
            attribute_id=POPULATION_DENSITY_ATTRIBUTE_ID,
            date__year=year,
        ).values("value")[:1]

        qs = (
            CollectionCatchment.objects.filter(
                collections__valid_from__year=year,
                region__country=country,
            )
            .distinct()
            .annotate(
                population=Subquery(pop_sq, output_field=FloatField()),
                population_density=Subquery(density_sq, output_field=FloatField()),
            )
            .values("id", "population", "population_density")
        )

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
