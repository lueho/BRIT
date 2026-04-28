from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from bibliography.models import Source
from maps.models import (
    GeoDataset,
    GeoDatasetColumnPolicy,
    GeoDatasetRuntimeConfiguration,
    NutsRegion,
    Region,
)
from maps.runtime_adapters import (
    LocalRelationDatasetRuntimeAdapter,
    get_dataset_runtime_adapter,
)


class GeoDataSetRuntimeRouteTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(
            name="Runtime region",
            country="DE",
            publication_status="published",
        )
        cls.source = Source.objects.create(
            title="Runtime source",
            publication_status="published",
        )
        cls.dataset = GeoDataset.objects.create(
            name="Runtime dataset",
            publication_status="published",
            region=cls.region,
        )
        cls.dataset.sources.add(cls.source)
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=cls.dataset,
            backend_type="django_model",
            runtime_model_name="NutsRegion",
        )
        GeoDatasetColumnPolicy.objects.create(
            dataset=cls.dataset,
            column_name="nuts_id",
            display_label="NUTS ID",
            is_visible=True,
        )
        GeoDatasetColumnPolicy.objects.create(
            dataset=cls.dataset,
            column_name="cntr_code",
            display_label="Country code",
            is_visible=False,
        )
        cls.feature = NutsRegion.objects.create(
            name="Hamburg",
            country="DE",
            publication_status="published",
            nuts_id="DE6",
            name_latn="Hamburg",
            nuts_name="Hamburg",
            cntr_code="DE",
            levl_code=1,
        )

    def test_dataset_detail_links_to_table_route(self):
        response = self.client.get(
            reverse("geodataset-detail", kwargs={"pk": self.dataset.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("geodataset-table", kwargs={"pk": self.dataset.pk}),
        )

    def test_dataset_table_route_renders_visible_columns(self):
        response = self.client.get(
            reverse("geodataset-table", kwargs={"pk": self.dataset.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Runtime dataset features")
        self.assertContains(response, "NUTS ID")
        self.assertContains(response, "DE6")
        self.assertNotContains(response, "Country code")
        self.assertContains(
            response,
            reverse(
                "geodataset-feature-detail",
                kwargs={"pk": self.dataset.pk, "feature_pk": self.feature.pk},
            ),
        )

    def test_runtime_adapter_resolves_compatibility_runtime(self):
        adapter = get_dataset_runtime_adapter(self.dataset)

        self.assertEqual(adapter.runtime_model_name, "NutsRegion")
        self.assertIs(adapter.model, NutsRegion)
        self.assertEqual(adapter.features_api_basename, "api-nuts-region")
        self.assertEqual(
            [policy.column_name for policy in adapter.get_visible_column_policies()],
            ["nuts_id"],
        )

    def test_dataset_feature_detail_route_renders_visible_columns(self):
        response = self.client.get(
            reverse(
                "geodataset-feature-detail",
                kwargs={"pk": self.dataset.pk, "feature_pk": self.feature.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feature from Runtime dataset")
        self.assertContains(response, "NUTS ID")
        self.assertContains(response, "DE6")
        self.assertNotContains(response, "Country code")
        self.assertContains(
            response,
            reverse("geodataset-table", kwargs={"pk": self.dataset.pk}),
        )


class GeoDataSetLocalRelationRuntimeRouteTestCase(TestCase):
    relation_name = "dataset_runtime_test_features"

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(
            name="Local relation runtime region",
            country="DE",
            publication_status="published",
        )
        cls.dataset = GeoDataset.objects.create(
            name="Local relation dataset",
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
        GeoDatasetColumnPolicy.objects.create(
            dataset=cls.dataset,
            column_name="nuts_id",
            display_label="NUTS ID",
            is_visible=True,
            is_filterable=True,
        )
        GeoDatasetColumnPolicy.objects.create(
            dataset=cls.dataset,
            column_name="hidden_code",
            display_label="Hidden code",
            is_visible=False,
        )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")
            cursor.execute(
                f"""
                CREATE TABLE public.{self.relation_name} (
                    feature_id integer PRIMARY KEY,
                    name varchar(100),
                    nuts_id varchar(20),
                    hidden_code varchar(20),
                    geom geometry(Point, 4326)
                )
                """
            )
            cursor.execute(
                f"""
                INSERT INTO public.{self.relation_name}
                    (feature_id, name, nuts_id, hidden_code, geom)
                VALUES
                    (1, 'Local feature A', 'DE-A', 'hidden-a', ST_SetSRID(ST_Point(10, 53), 4326)),
                    (2, 'Local feature B', 'DE-B', 'hidden-b', ST_SetSRID(ST_Point(11, 54), 4326))
                """
            )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS public.{self.relation_name}")

    def test_runtime_adapter_resolves_local_relation_runtime(self):
        adapter = get_dataset_runtime_adapter(self.dataset)

        self.assertIsInstance(adapter, LocalRelationDatasetRuntimeAdapter)
        self.assertTrue(adapter.uses_local_relation)
        self.assertEqual(
            adapter.relation_identifier,
            '"public"."dataset_runtime_test_features"',
        )

    def test_local_relation_adapter_introspects_columns_without_exposing_them(self):
        adapter = get_dataset_runtime_adapter(self.dataset)

        columns = {column["name"]: column for column in adapter.get_relation_columns()}

        self.assertTrue(columns["feature_id"]["is_primary_key"])
        self.assertTrue(columns["name"]["is_label"])
        self.assertTrue(columns["geom"]["is_geometry"])
        self.assertTrue(columns["nuts_id"]["is_configured"])
        self.assertTrue(columns["nuts_id"]["is_visible"])
        self.assertTrue(columns["nuts_id"]["is_filterable"])
        self.assertTrue(columns["hidden_code"]["is_configured"])
        self.assertFalse(columns["hidden_code"]["is_visible"])
        self.assertFalse(columns["name"]["is_configured"])

    def test_local_relation_adapter_reports_missing_configured_columns(self):
        GeoDatasetColumnPolicy.objects.create(
            dataset=self.dataset,
            column_name="missing_column",
            display_label="Missing column",
            is_visible=True,
        )
        adapter = get_dataset_runtime_adapter(self.dataset)

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "Local relation dataset references missing columns: missing_column.",
        ):
            adapter.get_records()

    def test_local_relation_adapter_rejects_invalid_policy_identifier(self):
        GeoDatasetColumnPolicy.objects.create(
            dataset=self.dataset,
            column_name="unsafe;column",
            display_label="Unsafe column",
            is_visible=True,
        )
        adapter = get_dataset_runtime_adapter(self.dataset)

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "Invalid local relation identifier: unsafe;column.",
        ):
            adapter.get_records()

    def test_local_relation_adapter_reports_non_geometry_column(self):
        runtime_configuration = self.dataset.runtime_configuration
        runtime_configuration.geometry_column = "nuts_id"
        runtime_configuration.save(update_fields=["geometry_column"])
        adapter = get_dataset_runtime_adapter(self.dataset)

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "Local relation dataset geometry column is not a geometry column: nuts_id.",
        ):
            adapter.get_records()

    def test_local_relation_table_route_renders_visible_columns(self):
        response = self.client.get(
            reverse("geodataset-table", kwargs={"pk": self.dataset.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Local relation dataset features")
        self.assertContains(response, "NUTS ID")
        self.assertContains(response, "DE-A")
        self.assertContains(response, "DE-B")
        self.assertNotContains(response, "Hidden code")
        self.assertNotContains(response, "hidden-a")

    def test_local_relation_table_route_applies_filterable_column(self):
        response = self.client.get(
            reverse("geodataset-table", kwargs={"pk": self.dataset.pk}),
            {"nuts_id": "DE-B"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DE-B")
        self.assertNotContains(response, "DE-A")

    def test_local_relation_feature_detail_route_renders_visible_columns(self):
        response = self.client.get(
            reverse(
                "geodataset-feature-detail",
                kwargs={"pk": self.dataset.pk, "feature_pk": 1},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Local feature A")
        self.assertContains(response, "NUTS ID")
        self.assertContains(response, "DE-A")
        self.assertNotContains(response, "Hidden code")

    def test_local_relation_geojson_route_returns_feature_collection(self):
        response = self.client.get(
            reverse("geodataset-features-geojson", kwargs={"pk": self.dataset.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["type"], "FeatureCollection")
        self.assertEqual(len(response.json()["features"]), 2)
        self.assertEqual(response.json()["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            response.json()["features"][0]["properties"]["nuts_id"], "DE-A"
        )
        self.assertNotIn("hidden_code", response.json()["features"][0]["properties"])

    def test_local_relation_map_route_uses_dataset_scoped_geojson_url(self):
        response = self.client.get(
            reverse("geodataset-map", kwargs={"pk": self.dataset.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["map_config"]["featuresLayerGeometriesUrl"],
            reverse("geodataset-features-geojson", kwargs={"pk": self.dataset.pk}),
        )
        self.assertEqual(
            response.context["map_config"]["featuresLayerDetailsUrlTemplate"],
            reverse(
                "geodataset-feature-detail",
                kwargs={"pk": self.dataset.pk, "feature_pk": 0},
            ).replace("/0/", "/"),
        )

    def test_local_relation_adapter_rejects_invalid_identifier(self):
        runtime_configuration = self.dataset.runtime_configuration
        runtime_configuration.relation_name = "unsafe;table"

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "Invalid local relation identifier: unsafe;table.",
        ):
            LocalRelationDatasetRuntimeAdapter(
                dataset=self.dataset,
                runtime_configuration=runtime_configuration,
            )
