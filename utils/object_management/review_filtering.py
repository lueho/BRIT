"""Pure Python filtering for heterogeneous review item collections.

Since the review dashboard combines multiple model types into a single list,
database-level filtering isn't possible. This module provides Python-based
filtering for these heterogeneous collections.

The ReviewDashboardFilterSet in filters.py generates the filter form UI,
but actual filtering is delegated to this module.
"""
import logging
from datetime import datetime
from typing import Any, List

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReviewItemFilter:
    """Pure Python filtering for heterogeneous review item lists.
    
    Applies search, model type, owner, date, and ordering filters
    to a list of mixed model instances.
    
    Usage:
        filter_obj = ReviewItemFilter(items, request.GET)
        filtered_items = filter_obj.filter()
    """

    def __init__(self, items: List[Any], params: dict):
        """Initialize filter with items and filter parameters.
        
        Args:
            items: List of model instances to filter
            params: Dictionary of filter parameters (typically request.GET)
        """
        self.items = items
        self.params = params

    def filter(self) -> List[Any]:
        """Apply all filters and return filtered, sorted list."""
        items = self.items

        # If no filters, just sort by default and return
        if not self.params:
            return self._apply_default_sort(items)

        # Apply each filter in sequence
        search = self.params.get("search", "").strip()
        if search:
            items = self._apply_search(items, search)

        model_types = self.params.getlist("model_type")
        if model_types:
            items = self._apply_model_type_filter(items, model_types)

        owner_id = self.params.get("owner")
        if owner_id:
            items = self._apply_owner_filter(items, owner_id)

        submitted_after = self.params.get("submitted_after")
        if submitted_after:
            items = self._apply_date_filter(items, submitted_after, is_after=True)

        submitted_before = self.params.get("submitted_before")
        if submitted_before:
            items = self._apply_date_filter(items, submitted_before, is_after=False)

        # Apply ordering last
        ordering = self.params.get("ordering", "-submitted_at")
        items = self._apply_ordering(items, ordering)

        return items

    def _apply_search(self, items: List[Any], search: str) -> List[Any]:
        """Filter items by case-insensitive name search."""
        search_lower = search.lower()
        return [
            item
            for item in items
            if search_lower in str(getattr(item, "name", "")).lower()
        ]

    def _apply_model_type_filter(
        self, items: List[Any], model_type_ids: List[str]
    ) -> List[Any]:
        """Filter items by ContentType IDs."""
        try:
            # Convert to integers, skipping non-numeric values
            valid_ids = [int(mt) for mt in model_type_ids if mt.isdigit()]
            if not valid_ids:
                return items

            return [
                item
                for item in items
                if ContentType.objects.get_for_model(item.__class__).id in valid_ids
            ]
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid model_type filter values: {e}")
            return items

    def _apply_owner_filter(self, items: List[Any], owner_id: str) -> List[Any]:
        """Filter items by owner ID."""
        if not owner_id.isdigit():
            logger.warning(f"Invalid owner_id filter value: {owner_id}")
            return items

        owner_id_int = int(owner_id)
        return [
            item
            for item in items
            if getattr(item, "owner_id", None) == owner_id_int
        ]

    def _apply_date_filter(
        self, items: List[Any], date_str: str, is_after: bool
    ) -> List[Any]:
        """Filter items by submission date (before or after)."""
        try:
            filter_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            if is_after:
                return [
                    item
                    for item in items
                    if getattr(item, "submitted_at", None)
                    and item.submitted_at.date() >= filter_date
                ]
            else:
                return [
                    item
                    for item in items
                    if getattr(item, "submitted_at", None)
                    and item.submitted_at.date() <= filter_date
                ]
        except ValueError as e:
            logger.warning(f"Invalid date filter value '{date_str}': {e}")
            return items

    def _apply_ordering(self, items: List[Any], ordering: str) -> List[Any]:
        """Sort items by the specified field and direction."""
        reverse = ordering.startswith("-")
        field = ordering.lstrip("-")

        if field == "submitted_at":
            items.sort(
                key=lambda x: getattr(x, "submitted_at", None) or timezone.now(),
                reverse=reverse,
            )
        elif field == "name":
            items.sort(
                key=lambda x: str(getattr(x, "name", "")).lower(),
                reverse=reverse,
            )
        else:
            # Unknown field, apply default sort
            logger.warning(f"Unknown ordering field: {field}. Using default.")
            items = self._apply_default_sort(items)

        return items

    def _apply_default_sort(self, items: List[Any]) -> List[Any]:
        """Apply default sorting (newest first by submitted_at)."""
        items_copy = list(items)  # Don't modify original
        items_copy.sort(
            key=lambda x: getattr(x, "submitted_at", None) or timezone.now(),
            reverse=True,
        )
        return items_copy
