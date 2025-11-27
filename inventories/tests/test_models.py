from django.test import TestCase

from maps.models import Region

from ..models import GeoDataset, InventoryAlgorithm, Material, Scenario


class ScenarioTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        feedstock1 = Material.objects.create(name="Feedstock 1")
        Material.objects.create(name="Feedstock 2")
        region = Region.objects.create(name="Test Region")
        Scenario.objects.create(name="Test Scenario", region=region)

        geodataset = GeoDataset.objects.create(name="Test Dataset", region=region)
        algorithm = InventoryAlgorithm.objects.create(
            name="Test Algorithm", geodataset=geodataset
        )
        algorithm.feedstocks.add(feedstock1)

    def setUp(self):
        self.scenario = Scenario.objects.get(name="Test Scenario")

    def test_available_geodatasets_with_single_feedstock(self):
        feedstock = Material.objects.get(name="Feedstock 1")
        geodatasets = self.scenario.available_geodatasets(feedstock=feedstock)
        self.assertQuerySetEqual(
            geodatasets, GeoDataset.objects.filter(name="Test Dataset")
        )

    def test_available_geodatasets_with_feedstock_queryset(self):
        feedstocks = Material.objects.all()
        geodatasets = self.scenario.available_geodatasets(feedstocks=feedstocks)
        self.assertQuerySetEqual(
            geodatasets, GeoDataset.objects.filter(name="Test Dataset")
        )

    def test_available_geodatasets_with_missing_input(self):
        geodatasets = self.scenario.available_geodatasets()
        self.assertQuerySetEqual(
            geodatasets, GeoDataset.objects.filter(name="Test Dataset")
        )

    def test_available_inventory_algorithms_with_single_feedstock(self):
        feedstock = Material.objects.get(name="Feedstock 1")
        algorithms = self.scenario.available_inventory_algorithms(feedstock=feedstock)
        self.assertQuerySetEqual(
            algorithms, InventoryAlgorithm.objects.filter(name="Test Algorithm")
        )

    def test_available_inventory_algorithms_with_feedstock_queryset(self):
        feedstocks = Material.objects.all()
        algorithms = self.scenario.available_inventory_algorithms(feedstocks=feedstocks)
        self.assertQuerySetEqual(
            algorithms, InventoryAlgorithm.objects.filter(name="Test Algorithm")
        )

    def test_available_inventory_algorithms_with_missing_input(self):
        algorithms = self.scenario.available_inventory_algorithms()
        self.assertQuerySetEqual(
            algorithms, InventoryAlgorithm.objects.filter(name="Test Algorithm")
        )
