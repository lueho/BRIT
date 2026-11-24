"""Helpers shared by the operator import APIs (NUTS, LAU).

Lives outside either import package so a second importer does not copy the
geometry handling, the dry-run rollback, the truthy query-param check, or the
large-body JSON parser.
"""

import json

from django.conf import settings
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.contrib.gis.geos.error import GEOSException
from rest_framework import serializers
from rest_framework.exceptions import APIException, ParseError
from rest_framework.parsers import BaseParser, get_encoding

from maps.models import GeoPolygon, Region


class ImportBodyTooLarge(APIException):
    """An import request body exceeded ``IMPORT_API_MAX_BODY_SIZE``."""

    status_code = 413
    default_detail = "Request body exceeded the import size limit."
    default_code = "request_too_large"


class ImportJSONParser(BaseParser):
    """JSON parser for the bulk import endpoints.

    Deliberately NOT a ``JSONParser`` subclass: DRF wraps ``self.body`` in a
    ``BytesIO`` for ``JSONParser`` instances, and reading ``request.body``
    enforces the site-wide ``DATA_UPLOAD_MAX_MEMORY_SIZE``. Import payloads
    legitimately exceed it (a single Norway NUTS-0 geometry is ~3.2 MB), so
    this parser reads the stream itself and enforces the import-only limit
    ``IMPORT_API_MAX_BODY_SIZE`` instead.
    """

    media_type = "application/json"

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        limit = settings.IMPORT_API_MAX_BODY_SIZE
        request = parser_context.get("request")
        if request is not None:
            try:
                content_length = int(request.META.get("CONTENT_LENGTH") or 0)
            except (TypeError, ValueError):
                content_length = 0
            if content_length > limit:
                raise ImportBodyTooLarge

        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ImportBodyTooLarge

        encoding = get_encoding(parser_context)
        try:
            return json.loads(raw.decode(encoding))
        except (UnicodeDecodeError, ValueError) as error:
            raise ParseError(f"JSON parse error - {error}") from error


class GeometryField(serializers.JSONField):
    """A GeoJSON polygon, stored as the MultiPolygon BRIT keeps borders in."""

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        raw = data if isinstance(data, str) else json.dumps(data)
        try:
            geometry = GEOSGeometry(raw, srid=4326)
        except (GDALException, GEOSException, ValueError, TypeError) as error:
            raise serializers.ValidationError(f"Invalid geometry: {error}") from error
        if geometry.geom_type == "Polygon":
            geometry = MultiPolygon(geometry, srid=4326)
        if geometry.geom_type != "MultiPolygon":
            raise serializers.ValidationError(
                f"Expected a Polygon or MultiPolygon, got {geometry.geom_type}."
            )
        if geometry.empty:
            raise serializers.ValidationError("A geometry without any parts.")
        return geometry


def _truthy(value):
    return str(value).lower() in ("1", "true", "yes", "on")


class _Rollback(Exception):
    """Raised to undo a dry run or a failed import inside its transaction."""


def _upsert_geometry(region, geometry):
    """Store the borders, returning whether they changed.

    A GeoPolygon shared with another Region is never edited in place: writing
    the new geometry into the shared row would silently move every other
    region's borders. A fresh GeoPolygon is created instead; the old one stays
    with the region that still references it.
    """
    if geometry is None:
        return False
    if region.borders is None:
        region.borders = GeoPolygon.objects.create(geom=geometry)
        return True
    if region.borders.geom is not None and region.borders.geom.equals_exact(geometry):
        return False
    shared = (
        Region.objects.filter(borders_id=region.borders_id)
        .exclude(pk=region.pk)
        .exists()
    )
    if shared:
        region.borders = GeoPolygon.objects.create(geom=geometry)
        return True
    region.borders.geom = geometry
    region.borders.save(update_fields=["geom"])
    return True
