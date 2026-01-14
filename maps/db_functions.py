"""
Custom PostGIS database functions for geometry operations.

Provides Django ORM wrappers for PostGIS functions not included in
Django's built-in GIS functions.
"""

from django.contrib.gis.db.models import GeometryField
from django.db.models import Func, Value


class SimplifyPreserveTopology(Func):
    """
    PostGIS ST_SimplifyPreserveTopology function wrapper.

    Simplifies a geometry while preserving topology (no invalid geometries).
    Uses the Douglas-Peucker algorithm.

    Args:
        expression: The geometry field/expression to simplify
        tolerance: Simplification tolerance in units of the geometry's SRID

    Example:
        qs.annotate(
            simplified_geom=SimplifyPreserveTopology(
                F('geom'),
                0.001  # ~100m at equator for SRID 4326
            )
        )
    """

    function = "ST_SimplifyPreserveTopology"
    output_field = GeometryField()

    def __init__(self, expression, tolerance, **extra):
        if not hasattr(tolerance, "resolve_expression"):
            tolerance = Value(tolerance)
        super().__init__(expression, tolerance, **extra)
