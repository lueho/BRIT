from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db.models import signals
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from distributions.models import Period, TemporalDistribution, Timestep
from materials.models import Material
from utils.object_management.models import get_default_owner
from utils.properties.models import Property, Unit

from ..models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    CollectionSystem,
    SortingMethod,
    WasteCategory,
    WasteFlyer,
)
from ..utils import ensure_initial_data
from .test_views import (  # noqa: F401
    CollectionEstablishedFieldTestCase,
    CollectionSortingMethodFieldTestCase,
    SortingMethodModelTestCase,
)


class InitialDataTestCase(TestCase):
    def test_simple_initial_collection_frequency_exists(self):
        ensure_initial_data()
        season = CollectionSeason.objects.get(
            distribution=TemporalDistribution.objects.get(name="Months of the year"),
            first_timestep=Timestep.objects.get(name="January"),
            last_timestep=Timestep.objects.get(name="December"),
        )
        CollectionCountOptions.objects.get(
            frequency__type="Fixed", season=season, standard=52
        )

    def test_default_sorting_methods_exist(self):
        ensure_initial_data()
        expected_names = {
            "Separate bins",
            "Optical bag sorting",
            "Four compartments bin",
            "Two compartments bin",
        }
        existing_names = set(
            SortingMethod.objects.filter(name__in=expected_names).values_list(
                "name", flat=True
            )
        )
        self.assertTrue(expected_names.issubset(existing_names))


class CollectionCatchmentTestCase(TestCase):
    catchment = None

    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(name="Test Catchment")
        cls.child_catchment = CollectionCatchment.objects.create(parent=cls.catchment)
        cls.grandchild_catchment = CollectionCatchment.objects.create(
            parent=cls.child_catchment
        )
        cls.great_grandchild_catchment = CollectionCatchment.objects.create(
            parent=cls.grandchild_catchment
        )
        cls.collection = Collection.objects.create(catchment=cls.catchment)
        cls.child_collection = Collection.objects.create(catchment=cls.child_catchment)
        cls.grandchild_collection = Collection.objects.create(
            catchment=cls.grandchild_catchment
        )
        cls.unrelated_collection = Collection.objects.create(
            catchment=CollectionCatchment.objects.create()
        )

    def test_downstream_collections_contains_collections_of_self(self):
        collections = self.catchment.downstream_collections
        self.assertIn(self.collection, collections)

    def test_downstream_collections_contains_collections_of_child_catchment(self):
        collections = self.catchment.downstream_collections
        self.assertIn(self.child_collection, collections)

    def test_downstream_collections_contains_collections_of_grandchild_catchment(self):
        collections = self.catchment.downstream_collections
        self.assertIn(self.grandchild_collection, collections)

    def test_downstream_collections_excludes_unrelated_collection(self):
        collections = self.catchment.downstream_collections
        self.assertNotIn(self.unrelated_collection, collections)

    def test_upstream_collections_includes_collections_from_all_ancestor_catchments(
        self,
    ):
        collections = self.great_grandchild_catchment.upstream_collections
        self.assertIn(self.collection, collections)
        self.assertIn(self.child_collection, collections)
        self.assertIn(self.grandchild_collection, collections)

    def test_get_absolute_url(self):
        self.assertEqual(
            reverse("collectioncatchment-detail", kwargs={"pk": self.catchment.pk}),
            self.collection.catchment.get_absolute_url(),
        )


class WasteFlyerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with mute_signals(signals.post_save):
            WasteFlyer.objects.create(
                citation_key="WasteFlyer007", url="https://www.super-test-flyer.org"
            )

    def setUp(self):
        pass

    def test_new_instance_is_saved_with_type_waste_flyer(self):
        with mute_signals(signals.post_save):
            flyer = WasteFlyer.objects.create(citation_key="WasteFlyer002")
        self.assertEqual(flyer.type, "waste_flyer")

    def test_str_returns_url(self):
        with mute_signals(signals.post_save):
            flyer = WasteFlyer.objects.get(citation_key="WasteFlyer007")
        self.assertEqual(flyer.__str__(), "https://www.super-test-flyer.org")


class WasteFlyerUrlCheckSignalTestCase(TestCase):
    def setUp(self):
        self.owner = get_default_owner()
        self.catchment = CollectionCatchment.objects.create(name="Signal Catchment")
        self.collection_system = CollectionSystem.objects.create(name="Signal System")
        self.category = WasteCategory.objects.create(name="Signal Category")
        self.collection = Collection.objects.create(
            owner=self.owner,
            catchment=self.catchment,
            collection_system=self.collection_system,
            waste_category=self.category,
            valid_from=date(2024, 1, 1),
        )
        self.property = Property.objects.create(
            owner=self.owner,
            name="Signal Property",
            unit="kg",
        )
        self.unit = Unit.objects.create(owner=self.owner, name="kg", symbol="kg")
        self.property.allowed_units.add(self.unit)

    @patch("sources.waste_collection.models.celery.current_app.send_task")
    def test_collection_flyer_add_schedules_wasteflyer_url_check(self, mock_send_task):
        with mute_signals(signals.post_save):
            flyer = WasteFlyer.objects.create(
                owner=self.owner,
                title="Signal Flyer",
                abbreviation="SignalFlyer",
                url="https://example.com/flyer-signal.pdf",
            )

        with self.captureOnCommitCallbacks(execute=True):
            self.collection.flyers.add(flyer)

        mock_send_task.assert_called_once_with("check_wasteflyer_url", (flyer.pk,))

    @patch("sources.waste_collection.models.celery.current_app.send_task")
    def test_cpv_source_add_schedules_wasteflyer_url_check(self, mock_send_task):
        cpv = CollectionPropertyValue.objects.create(
            owner=self.owner,
            collection=self.collection,
            property=self.property,
            unit=self.unit,
            average=12.5,
        )
        with mute_signals(signals.post_save):
            flyer = WasteFlyer.objects.create(
                owner=self.owner,
                title="Signal Flyer",
                abbreviation="SignalFlyer",
                url="https://example.com/flyer-cpv-signal.pdf",
            )

        with self.captureOnCommitCallbacks(execute=True):
            cpv.sources.add(flyer)

        mock_send_task.assert_called_once_with("check_wasteflyer_url", (flyer.pk,))

    @patch("sources.waste_collection.models.celery.current_app.send_task")
    def test_aggregated_cpv_source_add_schedules_wasteflyer_url_check(
        self, mock_send_task
    ):
        aggregated = AggregatedCollectionPropertyValue.objects.create(
            owner=self.owner,
            property=self.property,
            unit=self.unit,
            average=20.0,
        )
        with mute_signals(signals.post_save):
            flyer = WasteFlyer.objects.create(
                owner=self.owner,
                title="Signal Flyer",
                abbreviation="SignalFlyer",
                url="https://example.com/flyer-agg-signal.pdf",
            )

        with self.captureOnCommitCallbacks(execute=True):
            aggregated.sources.add(flyer)

        mock_send_task.assert_called_once_with("check_wasteflyer_url", (flyer.pk,))


class CollectionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        collection_system = CollectionSystem.objects.create(name="System")
        catchment = CollectionCatchment.objects.create(name="Catchment")
        category = WasteCategory.objects.create(name="Category")
        cls.predecessor_collection = Collection.objects.create(
            catchment=catchment,
            collection_system=collection_system,
            waste_category=category,
            valid_from=date(2023, 1, 1),
            valid_until=date(2023, 12, 31),
            description="Predecessor Collection",
        )
        cls.collection = Collection.objects.create(
            catchment=catchment,
            collection_system=collection_system,
            waste_category=category,
            valid_from=date(2024, 1, 1),
            description="Current Collection",
        )

    def test_collection_is_named_automatically_on_creation(self):
        self.assertEqual("Catchment Category System 2024", self.collection.name)

    def test_collection_name_is_updated_on_model_update(self):
        self.collection.collection_system = CollectionSystem.objects.create(
            name="New System"
        )
        self.collection.save()
        self.assertEqual("Catchment Category New System 2024", self.collection.name)

    def test_collection_name_is_updated_when_collection_system_model_is_changed(self):
        system = CollectionSystem.objects.get(name="System")
        system.name = "Updated System"
        system.save()
        self.collection.refresh_from_db()
        self.assertEqual("Catchment Category Updated System 2024", self.collection.name)

    def test_collection_name_is_updated_when_collection_waste_category_is_changed(self):
        category = WasteCategory.objects.create(name="New Category")
        self.collection.waste_category = category
        self.collection.save()
        self.collection.refresh_from_db()
        self.assertEqual("Catchment New Category System 2024", self.collection.name)

    def test_collection_name_is_updated_when_waste_category_model_is_changed(self):
        category = WasteCategory.objects.get(name="Category")
        category.name = "Updated Category"
        category.save()
        self.collection.refresh_from_db()
        self.assertEqual("Catchment Updated Category System 2024", self.collection.name)

    def test_collection_name_is_updated_when_catchment_model_is_changed(self):
        catchment = CollectionCatchment.objects.get(name="Catchment")
        catchment.name = "Updated Catchment"
        catchment.save()
        self.collection.refresh_from_db()
        self.assertEqual("Updated Catchment Category System 2024", self.collection.name)

    def test_collection_name_is_updated_when_year_is_changed(self):
        self.collection.valid_from = date(2025, 1, 1)
        self.collection.save()
        self.assertEqual("Catchment Category System 2025", self.collection.name)

    def test_currently_valid_returns_collection_with_past_valid_from_date(self):
        self.collection.valid_from = date.today() - timedelta(days=1)
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.currently_valid(), [self.collection]
        )

    def test_currently_valid_does_not_return_collection_with_future_valid_from_date(
        self,
    ):
        self.collection.valid_from = date.today() + timedelta(days=1)
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerySetEqual(Collection.objects.currently_valid(), [])

    def test_currently_valid_returns_collection_with_valid_from_date_today(self):
        self.collection.valid_from = date.today()
        self.collection.valid_until = None
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.currently_valid(), [self.collection]
        )

    def test_currently_valid_returns_collection_with_future_valid_until_date(self):
        self.collection.valid_from = date.today() - timedelta(days=1)
        self.collection.valid_until = date.today() + timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.currently_valid(), [self.collection]
        )

    def test_currently_valid_does_not_return_collection_with_past_valid_until_date(
        self,
    ):
        self.collection.valid_from = date.today() - timedelta(days=2)
        self.collection.valid_until = date.today() - timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(Collection.objects.currently_valid(), [])

    def test_archived_returns_collection_with_past_valid_until_date(self):
        self.collection.valid_from = date.today()
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.archived(), [self.predecessor_collection]
        )

    def test_archived_does_not_return_collection_with_future_valid_until_date(self):
        self.collection.valid_from = date.today() + timedelta(days=2)
        self.collection.save()
        self.predecessor_collection.valid_until = date.today() + timedelta(days=1)
        self.predecessor_collection.save()
        self.assertQuerySetEqual(Collection.objects.archived(), [])

    def test_archived_returns_collection_with_valid_until_date_today(self):
        self.collection.valid_from = date.today() + timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(
            Collection.objects.archived(), [self.predecessor_collection]
        )

    def test_valid_on_returns_collection_with_past_valid_from_date(self):
        day = date(2024, 6, 30)
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [self.collection])

    def test_valid_on_does_not_return_collection_with_future_valid_from_date(self):
        day = date(2022, 6, 30)
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [])

    def test_valid_on_returns_collection_with_given_valid_from_date(self):
        day = date(2024, 1, 1)
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [self.collection])

    def test_valid_on_returns_collection_with_future_valid_until_date(self):
        day = date(2024, 6, 30)
        self.collection.valid_until = day + timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [self.collection])

    def test_valid_on_does_not_return_collection_with_past_valid_until_date(self):
        day = date(2024, 6, 30)
        self.collection.valid_until = day - timedelta(days=1)
        self.collection.save()
        self.assertQuerySetEqual(Collection.objects.valid_on(day), [])

    def test_predecessor_returns_predecessor_collection(self):
        self.collection.predecessors.add(self.predecessor_collection)
        self.assertEqual(
            self.predecessor_collection, self.collection.predecessors.first()
        )

    def test_successor_returns_successor_collection(self):
        self.collection.predecessors.add(self.predecessor_collection)
        self.assertEqual(
            self.collection, self.predecessor_collection.successors.first()
        )

    def test_valid_until_cannot_be_before_valid_from(self):
        self.collection.valid_until = date(2023, 12, 31)
        with self.assertRaises(ValidationError):
            self.collection.full_clean()
            self.collection.save()


class CollectionMaterialMatchingQuerySetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        catchment = CollectionCatchment.objects.create(name="Material Match Catchment")
        collection_system = CollectionSystem.objects.create(
            name="Material Match System"
        )
        waste_category = WasteCategory.objects.create(name="Material Match Category")

        cls.allowed_1 = Material.objects.create(name="Allowed 1")
        cls.allowed_2 = Material.objects.create(name="Allowed 2")
        cls.allowed_3 = Material.objects.create(name="Allowed 3")
        cls.forbidden_1 = Material.objects.create(name="Forbidden 1")
        cls.forbidden_2 = Material.objects.create(name="Forbidden 2")

        cls.collection_exact = Collection.objects.create(
            catchment=catchment,
            collection_system=collection_system,
            waste_category=waste_category,
            valid_from=date(2022, 1, 1),
        )
        cls.collection_allowed_subset = Collection.objects.create(
            catchment=catchment,
            collection_system=collection_system,
            waste_category=waste_category,
            valid_from=date(2022, 2, 1),
        )
        cls.collection_allowed_superset = Collection.objects.create(
            catchment=catchment,
            collection_system=collection_system,
            waste_category=waste_category,
            valid_from=date(2022, 3, 1),
        )
        cls.collection_empty_sets = Collection.objects.create(
            catchment=catchment,
            collection_system=collection_system,
            waste_category=waste_category,
            valid_from=date(2022, 4, 1),
        )

        cls.collection_exact.allowed_materials.set([cls.allowed_1, cls.allowed_2])
        cls.collection_exact.forbidden_materials.set([cls.forbidden_1])

        cls.collection_allowed_subset.allowed_materials.set([cls.allowed_1])
        cls.collection_allowed_subset.forbidden_materials.set([cls.forbidden_1])

        cls.collection_allowed_superset.allowed_materials.set(
            [cls.allowed_1, cls.allowed_2, cls.allowed_3]
        )
        cls.collection_allowed_superset.forbidden_materials.set(
            [cls.forbidden_1, cls.forbidden_2]
        )

    def test_match_allowed_materials_requires_exact_set(self):
        qs = Collection.objects.match_allowed_materials(
            [self.allowed_2, self.allowed_1]
        )
        self.assertIn(self.collection_exact, qs)
        self.assertNotIn(self.collection_allowed_subset, qs)
        self.assertNotIn(self.collection_allowed_superset, qs)
        self.assertNotIn(self.collection_empty_sets, qs)

    def test_match_allowed_materials_can_match_empty_set(self):
        qs = Collection.objects.match_allowed_materials([])
        self.assertIn(self.collection_empty_sets, qs)
        self.assertNotIn(self.collection_exact, qs)

    def test_match_forbidden_materials_requires_exact_set(self):
        qs = Collection.objects.match_forbidden_materials([self.forbidden_1])
        self.assertIn(self.collection_exact, qs)
        self.assertIn(self.collection_allowed_subset, qs)
        self.assertNotIn(self.collection_allowed_superset, qs)
        self.assertNotIn(self.collection_empty_sets, qs)

    def test_match_materials_requires_exact_allowed_and_forbidden_sets(self):
        qs = Collection.objects.match_materials(
            allowed_materials=[self.allowed_1, self.allowed_2],
            forbidden_materials=[self.forbidden_1],
        )
        self.assertQuerySetEqual(qs, [self.collection_exact], ordered=False)


class CollectionVersioningHelpersTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(name="C")
        cls.system = CollectionSystem.objects.create(name="S")
        cls.category = WasteCategory.objects.create(name="Cat")

    def _mk(self, year):
        return Collection.objects.create(
            catchment=self.catchment,
            collection_system=self.system,
            waste_category=self.category,
            valid_from=date(year, 1, 1),
        )

    def test_all_versions_and_anchor_linear_chain(self):
        a = self._mk(2020)
        b = self._mk(2021)
        c = self._mk(2022)
        b.predecessors.add(a)
        c.predecessors.add(b)

        self.assertSetEqual(a.version_chain_ids, {a.pk, b.pk, c.pk})
        self.assertSetEqual(
            set(b.all_versions().values_list("pk", flat=True)), {a.pk, b.pk, c.pk}
        )
        self.assertEqual(c.version_anchor, a)

    def test_version_anchor_in_cycle_falls_back_to_earliest(self):
        a = self._mk(2020)
        b = self._mk(2019)
        # Create a cycle: a<->b
        a.predecessors.add(b)
        b.predecessors.add(a)

        # No node without predecessors; should pick earliest by valid_from then pk
        anchor = a.version_anchor
        self.assertIn(anchor.pk, {a.pk, b.pk})
        self.assertEqual(anchor.valid_from, min(a.valid_from, b.valid_from))


class CollectionStatisticsAccessorsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(name="C")
        cls.system = CollectionSystem.objects.create(name="S")
        cls.category = WasteCategory.objects.create(name="Cat")
        cls.root = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2020, 1, 1),
            publication_status="published",
        )
        cls.succ = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2021, 1, 1),
            publication_status="published",
        )
        cls.succ.predecessors.add(cls.root)

    def test_collectionpropertyvalues_for_display_dedup_and_scope(self):
        from sources.waste_collection.models import CollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="P", publication_status="published")
        unit = Unit.objects.create(name="U", publication_status="published")
        # Two values for same (prop, unit, year) across chain
        CollectionPropertyValue.objects.create(
            collection=self.root,
            property=prop,
            unit=unit,
            year=2020,
            average=10,
            publication_status="private",
        )
        v_succ = CollectionPropertyValue.objects.create(
            collection=self.succ,
            property=prop,
            unit=unit,
            year=2020,
            average=11,
            publication_status="published",
        )

        # Anonymous: only published, dedup keeps published one
        anon_list = self.succ.collectionpropertyvalues_for_display(user=None)
        self.assertEqual(len(anon_list), 1)
        self.assertEqual(anon_list[0].pk, v_succ.pk)

        # Owner-like visibility: simulate staff/owner by passing a dummy user with is_staff=True
        class U:
            is_staff = True
            is_authenticated = True

        full_list = self.succ.collectionpropertyvalues_for_display(user=U())
        self.assertEqual(len(full_list), 1)  # dedup keeps published due to ordering
        self.assertEqual(full_list[0].pk, v_succ.pk)

    def test_aggregatedcollectionpropertyvalues_for_display_chain_and_scope(self):
        from sources.waste_collection.models import AggregatedCollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="PA", publication_status="published")
        unit = Unit.objects.create(name="UA", publication_status="published")

        agg1 = AggregatedCollectionPropertyValue.objects.create(
            property=prop,
            unit=unit,
            year=2020,
            average=42,
            publication_status="private",
        )
        agg1.collections.add(self.root)

        agg2 = AggregatedCollectionPropertyValue.objects.create(
            property=prop,
            unit=unit,
            year=2021,
            average=43,
            publication_status="published",
        )
        agg2.collections.add(self.succ)

        # Anonymous sees only published
        anon = self.root.aggregatedcollectionpropertyvalues_for_display(user=None)
        self.assertEqual([a.year for a in anon], [2021])

        # Staff sees both, order by (property, unit, year, publication_order, -created_at, -pk)
        class U:
            is_staff = True
            is_authenticated = True

        both = self.succ.aggregatedcollectionpropertyvalues_for_display(user=U())
        self.assertEqual({a.year for a in both}, {2020, 2021})

    def test_collectionpropertyvalues_for_display_published_tie_prefers_latest_version(
        self,
    ):
        from sources.waste_collection.models import CollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="TP", publication_status="published")
        unit = Unit.objects.create(name="TU", publication_status="published")

        CollectionPropertyValue.objects.create(
            collection=self.root,
            property=prop,
            unit=unit,
            year=2022,
            average=1,
            publication_status="published",
        )
        v_succ = CollectionPropertyValue.objects.create(
            collection=self.succ,
            property=prop,
            unit=unit,
            year=2022,
            average=2,
            publication_status="published",
        )

        lst = self.root.collectionpropertyvalues_for_display(user=None)
        filtered = [
            v
            for v in lst
            if v.property_id == prop.pk and v.unit_id == unit.pk and v.year == 2022
        ]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].pk, v_succ.pk)

    def test_collectionpropertyvalues_for_display_prefetches_owner(self):
        from sources.waste_collection.models import CollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="QOwner", publication_status="published")
        unit = Unit.objects.create(name="QUnit", publication_status="published")
        CollectionPropertyValue.objects.create(
            collection=self.succ,
            property=prop,
            unit=unit,
            year=2023,
            average=3.14,
            publication_status="published",
        )

        cpvs = self.succ.collectionpropertyvalues_for_display(user=None)

        with self.assertNumQueries(0):
            _ = [value.owner.username for value in cpvs]

    def test_aggregatedcollectionpropertyvalues_for_display_prefetches_owner(self):
        from sources.waste_collection.models import AggregatedCollectionPropertyValue
        from utils.properties.models import Property, Unit

        prop = Property.objects.create(name="AQOwner", publication_status="published")
        unit = Unit.objects.create(name="AQUnit", publication_status="published")
        aggregated = AggregatedCollectionPropertyValue.objects.create(
            property=prop,
            unit=unit,
            year=2024,
            average=2.71,
            publication_status="published",
        )
        aggregated.collections.add(self.succ)

        values = self.succ.aggregatedcollectionpropertyvalues_for_display(user=None)

        with self.assertNumQueries(0):
            _ = [value.owner.username for value in values]


class CollectionSeasonTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.distribution = TemporalDistribution.objects.get(name="Months of the year")
        CollectionSeason.objects.get(
            distribution=cls.distribution,
            first_timestep=Timestep.objects.get(name="January"),
            last_timestep=Timestep.objects.get(name="December"),
        )

    def test_get_queryset_only_returns_from_months_of_the_year_distribution(self):
        self.assertQuerySetEqual(
            Period.objects.filter(distribution=self.distribution),
            CollectionSeason.objects.all(),
        )


class CollectionFrequencyTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        distribution = TemporalDistribution.objects.get(name="Months of the year")
        cls.january = Timestep.objects.get(name="January")
        cls.june = Timestep.objects.get(name="June")
        cls.july = Timestep.objects.get(name="July")
        cls.december = Timestep.objects.get(name="December")
        whole_year = CollectionSeason.objects.get(
            distribution=distribution,
            first_timestep=cls.january,
            last_timestep=cls.december,
        )
        first_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=cls.january,
            last_timestep=cls.june,
        )
        second_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=cls.july,
            last_timestep=cls.december,
        )
        cls.not_seasonal = CollectionFrequency.objects.create(
            name="Non-Seasonal Test Frequency"
        )
        CollectionCountOptions.objects.create(
            frequency=cls.not_seasonal, season=whole_year, standard=35, option_1=70
        )
        cls.seasonal = CollectionFrequency.objects.create(
            name="Seasonal Test Frequency"
        )
        CollectionCountOptions.objects.create(
            frequency=cls.seasonal, season=first_half_year, standard=35
        )
        CollectionCountOptions.objects.create(
            frequency=cls.seasonal, season=second_half_year, standard=35
        )

    def test_seasonal_returns_true_for_seasonal_frequency_object(self):
        self.assertTrue(self.seasonal.seasonal)

    def test_seasonal_returns_false_for_non_seasonal_frequency_object(self):
        self.assertFalse(self.not_seasonal.seasonal)

    def test_has_options_returns_true_for_frequency_with_optional_collection_count(
        self,
    ):
        self.assertTrue(self.not_seasonal.has_options)

    def test_has_options_returns_false_for_frequency_without_optional_collection_count(
        self,
    ):
        self.assertFalse(self.seasonal.has_options)

    def test_collections_per_year_returns_correct_sum_of_standard_values_of_all_seasons(
        self,
    ):
        self.assertEqual(70, self.seasonal.collections_per_year)
        self.assertEqual(35, self.not_seasonal.collections_per_year)
