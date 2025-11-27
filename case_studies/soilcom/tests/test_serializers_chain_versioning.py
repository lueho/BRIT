from datetime import date

from django.test import TestCase

from case_studies.soilcom.models import (
    Collection,
    CollectionCatchment,
    CollectionFrequency,
    CollectionSystem,
    Collector,
    WasteCategory,
    WasteStream,
)
from case_studies.soilcom.serializers import CollectionFlatSerializer
from maps.models import NutsRegion


class CollectionFlatSerializerChainAwareStatsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Minimal collection setup
        waste_stream = WasteStream.objects.create(
            name="WS",
            category=WasteCategory.objects.create(name="Cat"),
        )
        frequency = CollectionFrequency.objects.create(name="F")
        nuts = NutsRegion.objects.create(name="Hamburg", country="DE", nuts_id="DE600")
        cls.collection_root = Collection.objects.create(
            name="C0",
            catchment=CollectionCatchment.objects.create(
                name="Catch", region=nuts.region_ptr
            ),
            collector=Collector.objects.create(name="Col"),
            collection_system=CollectionSystem.objects.create(name="Sys"),
            waste_stream=waste_stream,
            frequency=frequency,
            valid_from=date(2020, 1, 1),
            publication_status="published",
        )
        cls.collection_succ = Collection.objects.create(
            name="C1",
            catchment=cls.collection_root.catchment,
            collector=Collector.objects.create(name="Col2"),
            collection_system=CollectionSystem.objects.create(name="Sys2"),
            waste_stream=waste_stream,
            frequency=frequency,
            valid_from=date(2021, 1, 1),
            publication_status="published",
        )
        cls.collection_succ.predecessors.add(cls.collection_root)

        # Properties used by serializer dynamic columns
        from utils.properties.models import Property, Unit

        cls.prop_specific = Property.objects.create(
            name="specific waste collected", publication_status="published"
        )
        cls.prop_conn = Property.objects.create(
            name="Connection rate", publication_status="published"
        )
        cls.unit = Unit.objects.create(name="u", publication_status="published")
        cls.prop_specific.allowed_units.add(cls.unit)
        cls.prop_conn.allowed_units.add(cls.unit)

        # Create a CPV on successor for 'specific waste collected'
        from case_studies.soilcom.models import (
            AggregatedCollectionPropertyValue,
            CollectionPropertyValue,
        )

        CollectionPropertyValue.objects.create(
            collection=cls.collection_succ,
            property=cls.prop_specific,
            unit=cls.unit,
            year=2022,
            average=12.5,
            publication_status="published",
        )

        # No CPV for 'Connection rate', but create an aggregated one
        agg = AggregatedCollectionPropertyValue.objects.create(
            property=cls.prop_conn,
            unit=cls.unit,
            year=2021,
            average=88.1,
            publication_status="published",
        )
        agg.collections.add(cls.collection_root)

    def test_dynamic_columns_include_chain_aware_values(self):
        # No request context -> anonymous scope -> only published
        s = CollectionFlatSerializer(self.collection_succ)
        data = s.data
        # From CPV
        self.assertIn("specific_waste_collected_2022", data)
        self.assertEqual(data["specific_waste_collected_2022"], 12.5)
        # From aggregated fallback
        self.assertIn("connection_rate_2021", data)
        self.assertEqual(data["connection_rate_2021"], 88.1)
        # Aggregated flag is set when aggregated values are present
        self.assertTrue(data.get("aggregated", False))
