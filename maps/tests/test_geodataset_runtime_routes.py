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
from maps.runtime_adapters import get_dataset_runtime_adapter


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
