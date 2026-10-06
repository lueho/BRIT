import hashlib
import json
import logging
from types import SimpleNamespace
from uuid import uuid4

from django.conf import settings
from django.core.cache import caches
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import Http404, StreamingHttpResponse
from django.urls import reverse
from django.utils.http import parse_etags
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Region
from .serializers import RegionGeoFeatureModelSerializer
from .throttling import GeoJSONAnonThrottle
from .utils import (
    GEOJSON_MAX_RENDERED_CACHE_BYTES,
    iter_geojson_features,
    iter_rendered_geojson,
    render_geojson_payload,
)

logger = logging.getLogger(__name__)

REGION_GEOJSON_ASSET_SCHEMA_VERSION = 1
REGION_GEOJSON_ASSET_LOCK_TIMEOUT_SECONDS = 600
STATIC_REGION_GEOJSON_CACHE_CONTROL = "public, max-age=31536000, immutable"
EXPOSE_HEADERS = "X-Total-Count, X-Cache-Status, X-Data-Version, ETag"


def _geojson_cache():
    return caches[getattr(settings, "GEOJSON_CACHE", "default")]


def is_static_region_geojson_eligible(region):
    if region is None:
        return False
    return (
        region.publication_status == "published"
        and region.borders_id is not None
        and region.name in getattr(settings, "GEOJSON_STATIC_REGION_NAMES", ())
    )


def get_static_region_geojson_version(region):
    lastmodified_at = region.lastmodified_at
    payload = {
        "schema_version": REGION_GEOJSON_ASSET_SCHEMA_VERSION,
        "pk": region.pk,
        "borders_id": region.borders_id,
        "name": region.name,
        "country": region.country,
        "description": region.description,
        "publication_status": region.publication_status,
        "lastmodified_at": (lastmodified_at.isoformat() if lastmodified_at else None),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def get_static_region_geojson_asset_name(pk, version):
    return f"maps/geojson-assets/regions/{pk}/{version}.json.zlib"


def get_static_region_geojson_url(region):
    if not is_static_region_geojson_eligible(region):
        return None
    return reverse(
        "region-geojson-asset",
        kwargs={
            "pk": region.pk,
            "version": get_static_region_geojson_version(region),
        },
    )


def _region_geojson_queryset(pk):
    return Region.objects.filter(pk=pk).defer("borders__geom")


def _region_version_row(pk):
    row = (
        Region.objects.filter(pk=pk)
        .values(
            "pk",
            "name",
            "country",
            "description",
            "publication_status",
            "borders_id",
            "lastmodified_at",
        )
        .first()
    )
    return SimpleNamespace(**row) if row else None


def _asset_lock_key(name):
    return f"region_geojson_asset:lock:{name}"


def ensure_static_region_geojson_asset(region):
    """Persist the compressed GeoJSON asset for ``region`` if missing.

    Returns the storage name when the asset is available, ``None`` when it
    could not be produced or stored (storage errors, oversized payload, or a
    concurrent generation holding the lock).
    """
    version = get_static_region_geojson_version(region)
    name = get_static_region_geojson_asset_name(region.pk, version)
    try:
        if default_storage.exists(name):
            return name
    except Exception:
        logger.warning(
            "Static region GeoJSON asset check failed for %s",
            name,
            exc_info=True,
        )
        return None

    lock_key = _asset_lock_key(name)
    try:
        cache = _geojson_cache()
    except Exception:
        logger.warning(
            "GeoJSON asset lock cache unavailable for region %s",
            region.pk,
            exc_info=True,
        )
        return None
    lock_handle = None
    token = None
    try:
        if hasattr(cache, "lock"):
            lock_handle = cache.lock(
                lock_key,
                timeout=REGION_GEOJSON_ASSET_LOCK_TIMEOUT_SECONDS,
                blocking=False,
            )
            acquired = lock_handle.acquire()
        else:
            token = uuid4().hex
            acquired = cache.add(
                lock_key, token, timeout=REGION_GEOJSON_ASSET_LOCK_TIMEOUT_SECONDS
            )
    except Exception:
        logger.warning(
            "GeoJSON asset lock unavailable for region %s",
            region.pk,
            exc_info=True,
        )
        return None
    if not acquired:
        return None
    try:
        try:
            if default_storage.exists(name):
                return name
        except Exception:
            logger.warning(
                "Static region GeoJSON asset check failed for %s",
                name,
                exc_info=True,
            )
            return None
        payload = render_geojson_payload(
            _region_geojson_queryset(region.pk),
            RegionGeoFeatureModelSerializer,
            "borders__geom",
        )
        if payload is None:
            return None
        current = _region_version_row(region.pk)
        if (
            not is_static_region_geojson_eligible(current)
            or get_static_region_geojson_version(current) != version
        ):
            return None
        try:
            saved_name = default_storage.save(name, ContentFile(payload))
        except Exception:
            logger.warning(
                "Failed to store static region GeoJSON asset %s",
                name,
                exc_info=True,
            )
            return None
        if saved_name != name:
            try:
                if default_storage.exists(name):
                    return name
            except Exception:
                logger.warning(
                    "Static region GeoJSON asset check failed for %s",
                    name,
                    exc_info=True,
                )
                return None
            return saved_name
        return name
    finally:
        try:
            if lock_handle is not None:
                lock_handle.release()
            elif token is not None and cache.get(lock_key) == token:
                cache.delete(lock_key)
        except Exception:
            logger.warning(
                "Failed to release static region GeoJSON lock %s",
                lock_key,
                exc_info=True,
            )


class RegionGeoJSONAssetView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (GeoJSONAnonThrottle,)

    def _validated_region(self, pk, version):
        region = (
            Region.objects.filter(pk=pk)
            .only(
                "id",
                "name",
                "country",
                "description",
                "publication_status",
                "lastmodified_at",
                "borders",
            )
            .first()
        )
        if not is_static_region_geojson_eligible(region):
            raise Http404
        if version != get_static_region_geojson_version(region):
            raise Http404
        return region

    @staticmethod
    def _etag_matches(request, version):
        inm = request.META.get("HTTP_IF_NONE_MATCH", "")
        tag = f'"{version}"'
        return any(
            etag == "*" or etag.removeprefix("W/") == tag for etag in parse_etags(inm)
        )

    @staticmethod
    def _set_headers(response, version, persisted):
        response["ETag"] = f'"{version}"'
        response["X-Data-Version"] = version
        response["X-Total-Count"] = "1"
        response["Cache-Control"] = (
            STATIC_REGION_GEOJSON_CACHE_CONTROL if persisted else "no-store"
        )
        response["Access-Control-Expose-Headers"] = EXPOSE_HEADERS
        return response

    def _not_modified(self, version):
        response = Response(status=status.HTTP_304_NOT_MODIFIED)
        response["ETag"] = f'"{version}"'
        response["Cache-Control"] = STATIC_REGION_GEOJSON_CACHE_CONTROL
        return response

    def _fallback_stream(self, request, region, version):
        response = StreamingHttpResponse(
            iter_geojson_features(
                _region_geojson_queryset(region.pk),
                RegionGeoFeatureModelSerializer,
                "borders__geom",
                context={"request": request},
            ),
            content_type="application/geo+json",
        )
        response["X-Cache-Status"] = "STREAM"
        return self._set_headers(response, version, persisted=False)

    def get(self, request, pk, version):
        region = self._validated_region(pk, version)
        if self._etag_matches(request, version):
            return self._not_modified(version)
        name = ensure_static_region_geojson_asset(region)
        if name is not None:
            try:
                with default_storage.open(name, "rb") as stored:
                    payload = stored.read(GEOJSON_MAX_RENDERED_CACHE_BYTES + 1)
            except Exception:
                logger.warning(
                    "Failed to read static region GeoJSON asset %s",
                    name,
                    exc_info=True,
                )
                payload = None
            if payload is not None and len(payload) <= GEOJSON_MAX_RENDERED_CACHE_BYTES:
                response = StreamingHttpResponse(
                    iter_rendered_geojson(payload),
                    content_type="application/geo+json",
                )
                response["X-Cache-Status"] = "ASSET"
                return self._set_headers(response, version, persisted=True)
        region = self._validated_region(pk, version)
        return self._fallback_stream(request, region, version)

    def head(self, request, pk, version):
        region = self._validated_region(pk, version)
        if self._etag_matches(request, version):
            return self._not_modified(version)
        name = get_static_region_geojson_asset_name(region.pk, version)
        try:
            persisted = default_storage.exists(name)
        except Exception:
            logger.warning(
                "Static region GeoJSON asset check failed for %s",
                name,
                exc_info=True,
            )
            persisted = False
        response = StreamingHttpResponse((), content_type="application/geo+json")
        response["X-Cache-Status"] = "ASSET" if persisted else "STREAM"
        return self._set_headers(response, version, persisted)
