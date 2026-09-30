from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from maps.models import (
    GeoDataset,
    GeoDatasetColumnPolicy,
    GeoDatasetRuntimeConfiguration,
    Region,
)
from maps.runtime_adapters import get_dataset_runtime_adapter


class LocalRelationTypedFilterTestCase(TestCase):
    relation_name = "maps_test_typed_filter_features"
    filter_columns = (
        "name",
        "category",
        "crop_code",
        "height_m",
        "surveyed_on",
        "surveyed_at",
        "is_active",
    )

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(
            name="Typed filter region",
            country="DE",
            publication_status="published",
        )
        cls.dataset = GeoDataset.objects.create(
            name="Typed filter dataset",
            publication_status="published",
            region=cls.region,
        )
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=cls.dataset,
            backend_type="local_relation",
            schema_name="public",
            relation_name=cls.relation_name,
            geometry_column="geom",
            primary_key_column="feature_id",
            label_field="name",
        )
        for column_name in cls.filter_columns:
            GeoDatasetColumnPolicy.objects.create(
                dataset=cls.dataset,
                column_name=column_name,
                is_visible=True,
                is_filterable=True,
            )
        GeoDatasetColumnPolicy.objects.create(
            dataset=cls.dataset,
            column_name="hidden_code",
            is_visible=True,
            is_filterable=False,
        )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")
            cursor.execute(
                f"""
                CREATE TABLE public.{self.relation_name} (
                    feature_id integer PRIMARY KEY,
                    name varchar(100),
                    category varchar(20),
                    crop_code integer,
                    height_m numeric(6, 2),
                    surveyed_on date,
                    surveyed_at timestamp with time zone,
                    is_active boolean,
                    hidden_code varchar(20),
                    height_m_max integer,
                    geom geometry(Point, 3857)
                )
                """
            )
            cursor.execute(
                f"""
                INSERT INTO public.{self.relation_name} VALUES
                    (1, 'Oak A', 'tree', 10, 4.50, '2024-01-15',
                     '2024-01-15T08:00:00+00:00', true, 'a', 7,
                     ST_Transform(ST_SetSRID(ST_Point(10, 53), 4326), 3857)),
                    (2, 'Beech B', 'tree', 20, 12.00, '2024-06-01',
                     '2024-06-01T23:30:00+00:00', false, 'b', 7,
                     ST_Transform(ST_SetSRID(ST_Point(11, 54), 4326), 3857)),
                    (3, 'Hedge C', 'shrub', 20, 1.25, '2025-03-10',
                     '2025-03-10T12:00:00+00:00', true, 'c', 99,
                     ST_Transform(ST_SetSRID(ST_Point(12, 55), 4326), 3857))
                """
            )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")

    def adapter(self):
        return get_dataset_runtime_adapter(self.dataset)

    def count(self, query_string):
        return self.adapter().get_record_count(query_params=QueryDict(query_string))

    def test_filter_specs_follow_column_data_types(self):
        specs = self.adapter().get_filter_specs()

        self.assertEqual(
            {column: spec.kind for column, spec in specs.items()},
            {
                "category": "choice",
                "crop_code": "choice",
                "height_m": "range",
                "is_active": "boolean",
                "name": "choice",
                "surveyed_at": "date_range",
                "surveyed_on": "date_range",
            },
        )
        self.assertEqual(specs["category"].options, ("shrub", "tree"))
        self.assertEqual(specs["crop_code"].options, (10, 20))
        self.assertEqual(str(specs["height_m"].minimum), "1.25")
        self.assertEqual(str(specs["height_m"].maximum), "12.00")
        self.assertEqual(str(specs["surveyed_on"].minimum), "2024-01-15")
        self.assertEqual(str(specs["surveyed_at"].maximum), "2025-03-10")

    def test_columns_with_many_values_use_autocomplete_or_range(self):
        with patch("maps.runtime_adapters.MAX_LOCAL_RELATION_FILTER_OPTIONS", 2):
            specs = self.adapter().get_filter_specs()

        self.assertEqual(specs["name"].kind, "autocomplete")
        self.assertEqual(specs["name"].options, ())
        self.assertEqual(specs["category"].kind, "choice")
        self.assertEqual(specs["crop_code"].kind, "choice")
        with patch("maps.runtime_adapters.MAX_LOCAL_RELATION_FILTER_OPTIONS", 1):
            self.assertEqual(
                self.adapter().get_filter_specs()["crop_code"].kind, "range"
            )

    def test_choice_filters_accept_multiple_values(self):
        self.assertEqual(self.count("category=tree"), 2)
        self.assertEqual(self.count("category=tree&category=shrub"), 3)
        self.assertEqual(self.count("crop_code=20"), 2)
        self.assertEqual(self.count("crop_code=10&crop_code=20"), 3)

    def test_range_filters_bound_numeric_and_date_columns(self):
        self.assertEqual(self.count("height_m_min=4.5"), 2)
        self.assertEqual(self.count("height_m_min=2&height_m_max=5"), 1)
        self.assertEqual(self.count("crop_code_min=15"), 2)
        self.assertEqual(self.count("surveyed_on_max=2024-12-31"), 2)
        self.assertEqual(
            self.count("surveyed_at_min=2024-06-01&surveyed_at_max=2024-06-01"), 1
        )

    def test_boolean_filter(self):
        self.assertEqual(self.count("is_active=true"), 2)
        self.assertEqual(self.count("is_active=false"), 1)

    def test_exact_timestamp_filter_accepts_full_timestamp(self):
        self.assertEqual(self.count("surveyed_at=2024-06-01T23:30:00%2B00:00"), 1)

    def test_range_suffix_colliding_with_column_filters_that_column(self):
        GeoDatasetColumnPolicy.objects.create(
            dataset=self.dataset,
            column_name="height_m_max",
            is_visible=True,
            is_filterable=True,
        )

        specs = self.adapter().get_filter_specs()
        response = self.client.get(
            reverse("geodataset-table", kwargs={"pk": self.dataset.pk})
        )

        self.assertEqual(self.count("height_m_max=7"), 2)
        self.assertEqual(specs["height_m"].kind, "choice")
        self.assertNotIn("height_m_min", self.adapter().get_filter_query_param_names())
        self.assertContains(response, 'name="height_m_max"', count=1)

    def test_range_params_ignored_for_text_and_unfilterable_columns(self):
        self.assertEqual(self.count("name_min=Z&hidden_code=a"), 3)

    def test_invalid_typed_filter_value_is_bad_request(self):
        for query in (
            {"height_m_min": "tall"},
            {"crop_code": "maize"},
            {"surveyed_on_max": "yesterday"},
            {"is_active": "maybe"},
        ):
            with self.subTest(query=query):
                response = self.client.get(
                    reverse("geodataset-table", kwargs={"pk": self.dataset.pk}),
                    query,
                )
                self.assertEqual(response.status_code, 400)

    def test_geojson_range_filter_counts_as_bounded(self):
        url = reverse("geodataset-features-geojson", kwargs={"pk": self.dataset.pk})
        with patch("maps.mixins.MAX_UNBOUNDED_GEOJSON_FEATURES", 0):
            unbounded = self.client.get(url)
            bounded = self.client.get(url, {"height_m_min": "2"})

        self.assertEqual(unbounded.status_code, 400)
        self.assertEqual(bounded.status_code, 200)
        self.assertEqual(bounded["X-Total-Count"], "2")

    def test_map_route_renders_widgets_suited_to_column_types(self):
        with patch("maps.runtime_adapters.MAX_LOCAL_RELATION_FILTER_OPTIONS", 2):
            response = self.client.get(
                reverse("geodataset-map", kwargs={"pk": self.dataset.pk}),
                {"name": "Oak A", "category": "tree", "height_m_min": "2"},
            )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertInHTML('<option value="tree" selected>tree</option>', content)
        self.assertIn('data-geodataset-filter="choice"', content)
        self.assertIn('name="category"', content)
        self.assertIn('data-geodataset-filter="autocomplete"', content)
        self.assertIn(
            'data-autocomplete-url="'
            + reverse(
                "geodataset-filter-options",
                kwargs={"pk": self.dataset.pk, "column": "name"},
            )
            + '"',
            content,
        )
        self.assertInHTML('<option value="Oak A" selected>Oak A</option>', content)
        self.assertIn('name="height_m_min"', content)
        self.assertIn('name="height_m_max"', content)
        self.assertIn('type="number"', content)
        self.assertIn('value="2"', content)
        self.assertIn('name="surveyed_on_min"', content)
        self.assertIn('type="date"', content)
        self.assertInHTML('<option value="true">Yes</option>', content)
        self.assertNotIn("<datalist", content)
        self.assertIn("geodataset_filters.min.js", content)

    def test_table_route_renders_typed_filters(self):
        response = self.client.get(
            reverse("geodataset-table", kwargs={"pk": self.dataset.pk}),
            {"crop_code": ["10", "20"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertInHTML(
            '<option value="10" selected>10</option>', response.content.decode()
        )
        self.assertIn("geodataset_filters.min.js", response.content.decode())
        self.assertEqual(len(response.context["table_rows"]), 3)

    def url(self, column):
        return reverse(
            "geodataset-filter-options",
            kwargs={"pk": self.dataset.pk, "column": column},
        )

    def test_returns_matching_distinct_values(self):
        response = self.client.get(self.url("name"), {"q": "e"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "results": [
                    {"value": "Beech B", "text": "Beech B"},
                    {"value": "Hedge C", "text": "Hedge C"},
                ]
            },
        )

    def test_search_treats_wildcards_literally(self):
        response = self.client.get(self.url("name"), {"q": "%"})

        self.assertEqual(response.json(), {"results": []})

    def test_long_search_terms_are_truncated(self):
        response = self.client.get(self.url("name"), {"q": "Oak" + "x" * 500})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": []})
        with patch.object(
            type(self.adapter()), "search_filter_values", return_value=[]
        ) as search:
            self.client.get(self.url("name"), {"q": "y" * 500})
        self.assertEqual(len(search.call_args.args[1]), 100)

    def test_rejects_unfilterable_column(self):
        response = self.client.get(self.url("hidden_code"), {"q": "a"})

        self.assertEqual(response.status_code, 404)

    def test_private_dataset_options_require_access(self):
        owner = User.objects.create_user(username="typed-filter-owner")
        GeoDataset.objects.filter(pk=self.dataset.pk).update(
            publication_status="private", owner=owner
        )

        anonymous = self.client.get(self.url("name"), {"q": "a"})
        self.client.force_login(owner)
        owned = self.client.get(self.url("name"), {"q": "a"})

        self.assertIn(anonymous.status_code, (302, 403))
        self.assertEqual(owned.status_code, 200)
