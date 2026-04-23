"""Tests for sources.waste_collection.renderers."""

from django.test import TestCase

from sources.waste_collection.renderers import _sort_dynamic_columns

from .test_views import (  # noqa: F401
    CollectionCSVRendererTestCase,
    CollectionXLSXRendererTestCase,
)


class SortDynamicColumnsTestCase(TestCase):
    """Regression tests for year-based column sorting in exports."""

    def test_year_columns_sorted_chronologically(self):
        """Year-based columns should be sorted by year, not by discovery order."""
        columns = [
            "specific_waste_collected_2022",
            "specific_waste_collected_2020",
            "specific_waste_collected_2021",
        ]
        sorted_cols = _sort_dynamic_columns(columns)
        expected = [
            "specific_waste_collected_2020",
            "specific_waste_collected_2021",
            "specific_waste_collected_2022",
        ]
        assert sorted_cols == expected

    def test_year_columns_with_units_kept_adjacent(self):
        """Unit columns should follow their corresponding value columns."""
        columns = [
            "population_2021",
            "population_2020_unit",
            "population_2020",
            "population_2021_unit",
        ]
        sorted_cols = _sort_dynamic_columns(columns)
        expected = [
            "population_2020",
            "population_2020_unit",
            "population_2021",
            "population_2021_unit",
        ]
        assert sorted_cols == expected

    def test_different_properties_grouped_separately(self):
        """Different property prefixes should be grouped and sorted separately."""
        columns = [
            "connection_rate_2021",
            "specific_waste_collected_2020",
            "connection_rate_2020",
            "specific_waste_collected_2021",
        ]
        sorted_cols = _sort_dynamic_columns(columns)
        # Alphabetically: connection_rate_ before specific_waste_collected_
        expected = [
            "connection_rate_2020",
            "connection_rate_2021",
            "specific_waste_collected_2020",
            "specific_waste_collected_2021",
        ]
        assert sorted_cols == expected

    def test_non_year_columns_preserved_first(self):
        """Non-year columns should appear before year-based columns."""
        columns = [
            "some_metric",
            "population_2021",
            "another_field",
            "population_2020",
        ]
        sorted_cols = _sort_dynamic_columns(columns)
        expected = [
            "some_metric",
            "another_field",
            "population_2020",
            "population_2021",
        ]
        assert sorted_cols == expected

    def test_empty_list_returns_empty(self):
        """Empty input should return empty output."""
        assert _sort_dynamic_columns([]) == []

    def test_no_year_columns_returns_unchanged(self):
        """Columns without year suffix should be returned in original order."""
        columns = ["field_a", "field_b", "field_c"]
        assert _sort_dynamic_columns(columns) == columns
