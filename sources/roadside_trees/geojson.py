"""GeoJSON adapter module for roadside_trees sources."""

from sources.roadside_trees.models import HamburgRoadsideTrees
from sources.roadside_trees.serializers import HamburgRoadsideTreeGeometrySerializer

__all__ = [
    "HamburgRoadsideTrees",
    "HamburgRoadsideTreeGeometrySerializer",
]
