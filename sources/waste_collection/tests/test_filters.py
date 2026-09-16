from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Q, signals
from django.test import RequestFactory, TestCase
from django.utils import timezone
from factory.django import mute_signals

from distributions.models import TemporalDistribution, Timestep
from maps.models import Region
from materials.models import MaterialCategory
from utils.properties.models import Property

from ..filters import (
    CollectionFilterSet,
    CollectionsPerYearFilter,
    CollectorFilter,
    ConnectionRateFilter,
    SpecWasteCollectedFilter,
    WasteFlyerFilter,
)
from ..models import (
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    Collector,
    WasteComponent,
    WasteFlyer,
)


class WasteFlyerFilterTestCase(TestCase):
    catchment = None

    @classmethod
    def setUpTestData(cls):
        with mute_signals(signals.post_save):
            for i in range(1, 5):
                WasteFlyer.objects.create(
                    title=f"Waste flyer {i}",
                    citation_key=f"WF{i}",
                    url=f"https://www.flyer{i}.com",
                    url_valid=i % 2 == 0,
                )
        cls.catchment = CollectionCatchment.objects.create(name="Parent")
        child_catchment = CollectionCatchment.objects.create(
            name="Child", parent=cls.catchment
        )
        for flyer in WasteFlyer.objects.filter(citation_key__in=("WF1", "WF2")):
            collection = Collection.objects.create(
                catchment=child_catchment,
            )
            collection.flyers.add(flyer)
        collection = Collection.objects.create(catchment=cls.catchment)
        collection.flyers.add(WasteFlyer.objects.get(citation_key="WF3"))

    def setUp(self):
        pass

    def test_filter_form_has_no_formtags(self):
        filter_ = WasteFlyerFilter(queryset=WasteFlyer.objects.all())
        self.assertFalse(filter_.form.helper.form_tag)

    def test_url_valid(self):
        data = {"url_valid": "False"}
        filter_ = WasteFlyerFilter(data, WasteFlyer.objects.all())
        self.assertTrue(filter_.is_valid())
        self.assertEqual(4, WasteFlyer.objects.count())
        self.assertEqual(2, filter_.qs.count())

    def test_get_catchment_returns_flyers_from_downstream_collections(self):
        data = {"catchment": self.catchment.id}
        filter_ = WasteFlyerFilter(data=data, queryset=WasteFlyer.objects.all())
        self.assertTrue(filter_.is_valid())
        self.assertQuerySetEqual(
            filter_.qs.order_by("id"),
            WasteFlyer.objects.filter(citation_key__in=("WF1", "WF2", "WF3")).order_by(
                "id"
            ),
        )


class CollectionsPerYearFilterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        distribution = TemporalDistribution.objects.get(name="Months of the year")
        whole_year = CollectionSeason.objects.get(
            distribution=distribution,
            first_timestep=Timestep.objects.get(name="January"),
            last_timestep=Timestep.objects.get(name="December"),
        )
        first_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=Timestep.objects.get(name="January"),
            last_timestep=Timestep.objects.get(name="June"),
        )
        second_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=Timestep.objects.get(name="July"),
            last_timestep=Timestep.objects.get(name="December"),
        )

        continuous_frequency = CollectionFrequency.objects.create(
            name="Continuous Frequency"
        )
        seasonal_frequency = CollectionFrequency.objects.create(
            name="Seasonal Frequency"
        )
        uncountable_frequency = CollectionFrequency.objects.create(
            name="Frequency Without Count Options"
        )

        CollectionCountOptions.objects.create(
            frequency=continuous_frequency, season=whole_year, standard=35, option_1=70
        )
        CollectionCountOptions.objects.create(
            frequency=seasonal_frequency, season=first_half_year, standard=35
        )
        CollectionCountOptions.objects.create(
            frequency=seasonal_frequency, season=second_half_year, standard=35
        )

        cls.collection1 = Collection.objects.create(
            name="Collection 1", frequency=continuous_frequency
        )
        cls.collection2 = Collection.objects.create(
            name="Collection 2", frequency=continuous_frequency
        )
        cls.collection3 = Collection.objects.create(
            name="Collection 3", frequency=seasonal_frequency
        )
        cls.collection4 = Collection.objects.create(name="Collection 4")
        cls.collection5 = Collection.objects.create(
            name="Collection 5", frequency=uncountable_frequency
        )

    def test_filter_by_collections_per_year(self):
        filter_ = CollectionsPerYearFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(26, 52), False))
        expected = Collection.objects.filter(
            pk__in=[self.collection1.pk, self.collection2.pk]
        )
        self.assertQuerySetEqual(qs, expected, ordered=False)

    def test_filter_with_without_value_returns_full_queryset(self):
        filter_ = CollectionsPerYearFilter()
        qs = filter_.filter(Collection.objects.all(), None)
        self.assertQuerySetEqual(qs, Collection.objects.all(), ordered=False)

    def test_filter_by_collections_per_year_with_no_value(self):
        filter_ = CollectionsPerYearFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(52, 100), True))
        expected = Collection.objects.filter(
            pk__in=[self.collection3.pk, self.collection4.pk, self.collection5.pk]
        )
        self.assertQuerySetEqual(qs, expected, ordered=False)

    def test_frequency_without_count_options_is_treated_as_null(self):
        filter_ = CollectionsPerYearFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(0, 100), True))
        self.assertIn(self.collection5, qs)

    def test_frequency_without_count_options_is_excluded_without_nulls(self):
        filter_ = CollectionsPerYearFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(0, 100), False))
        self.assertNotIn(self.collection5, qs)


class ConnectionRateFilterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.collection1 = Collection.objects.create(name="Collection 1")
        cls.collection2 = Collection.objects.create(name="Collection 2")
        cls.collection3 = Collection.objects.create(name="Collection 3")
        cls.collection4 = Collection.objects.create(name="Collection 4")
        cls.collection5 = Collection.objects.create(name="Collection 5")

        # Add connection rate properties to collections
        prop = Property.objects.create(name="Connection rate")
        CollectionPropertyValue.objects.create(
            collection=cls.collection1, property=prop, year=2022, average=50
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection2, property=prop, year=2022, average=75
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection3, property=prop, year=2022, average=25
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection4, property=prop, year=2022, average=0
        )

    def test_filter_by_connection_rate(self):
        filter_ = ConnectionRateFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(50, 75), False))
        expected = Collection.objects.filter(
            pk__in=[self.collection1.pk, self.collection2.pk]
        )
        self.assertQuerySetEqual(qs, expected, ordered=False)

    def test_filter_treats_zero_as_a_value(self):
        filter_ = ConnectionRateFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(0, 0), False))
        expected = Collection.objects.filter(pk=self.collection4.pk)
        self.assertQuerySetEqual(qs, expected, ordered=False)

    def test_filter_with_without_value(self):
        filter_ = ConnectionRateFilter()
        qs = filter_.filter(Collection.objects.all(), None)
        expected = Collection.objects.all()
        self.assertQuerySetEqual(qs, expected, ordered=False)

    def test_filter_including_null_values(self):
        filter_ = ConnectionRateFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(50, 75), True))
        expected = Collection.objects.filter(
            pk__in=[self.collection1.pk, self.collection2.pk, self.collection5.pk]
        )
        self.assertQuerySetEqual(qs, expected, ordered=False)


class SpecWasteCollectedFilterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.collection1 = Collection.objects.create(name="Collection 1")
        cls.collection2 = Collection.objects.create(name="Collection 2")
        cls.collection3 = Collection.objects.create(name="Collection 3")
        cls.collection4 = Collection.objects.create(name="Collection 4")

        # Add spec waste collected properties to collections
        prop = Property.objects.create(name="specific waste collected")
        CollectionPropertyValue.objects.create(
            collection=cls.collection1, property=prop, year=2022, average=100
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection2, property=prop, year=2021, average=200
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection3, property=prop, year=2019, average=300
        )

    def test_filter_by_spec_waste_collected(self):
        filter_ = SpecWasteCollectedFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(100, 200), False))
        expected = Collection.objects.filter(
            pk__in=[self.collection1.pk, self.collection2.pk]
        )
        self.assertQuerySetEqual(qs, expected, ordered=False)

    def test_filter_with_without_value(self):
        filter_ = SpecWasteCollectedFilter()
        qs = filter_.filter(Collection.objects.all(), None)
        expected = Collection.objects.all()
        self.assertQuerySetEqual(qs, expected, ordered=False)

    def test_filter_including_null_values(self):
        filter_ = SpecWasteCollectedFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(100, 200), True))
        expected = Collection.objects.filter(
            pk__in=[self.collection1.pk, self.collection2.pk, self.collection4.pk]
        )
        self.assertQuerySetEqual(qs, expected, ordered=False)


class CollectionFilterMetadataTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="filter-metadata-owner")
        cls.collection = Collection.objects.create(
            owner=cls.owner,
            required_bin_capacity=Decimal("120.5"),
            min_bin_size=Decimal("240.5"),
        )
        cls.connection_property, _ = Property.objects.get_or_create(
            name="Connection rate"
        )
        cls.specific_property, _ = Property.objects.get_or_create(
            name="specific waste collected"
        )
        CollectionPropertyValue.objects.bulk_create(
            [
                CollectionPropertyValue(
                    owner=cls.owner,
                    collection=cls.collection,
                    property=property_,
                    average=average,
                    year=2024,
                )
                for property_, average in (
                    (cls.connection_property, 100.1),
                    (cls.specific_property, 1600.1),
                )
            ]
        )
        whole_year = CollectionSeason.objects.get(
            distribution__name="Months of the year",
            first_timestep__name="January",
            last_timestep__name="December",
        )
        first_half = CollectionSeason.objects.create(
            distribution=whole_year.distribution,
            first_timestep=whole_year.first_timestep,
            last_timestep=Timestep.objects.get(name="June"),
        )
        cls.frequency = CollectionFrequency.objects.create(owner=cls.owner)
        other_frequency = CollectionFrequency.objects.create(owner=cls.owner)
        CollectionCountOptions.objects.bulk_create(
            [
                CollectionCountOptions(
                    owner=cls.owner,
                    frequency=frequency,
                    season=season,
                    standard=standard,
                    option_1=999,
                )
                for frequency, season, standard in (
                    (cls.frequency, whole_year, 300),
                    (cls.frequency, first_half, 300),
                    (other_frequency, whole_year, 400),
                )
            ]
        )
        MaterialCategory.objects.get_or_create(name="Biowaste component")
        cls.material = WasteComponent.objects.create(
            name="Choice alpha", owner=cls.owner
        )

    def get_filters(self, data=None, **kwargs):
        request = RequestFactory().get("/collections/", data or {})
        request.user = self.owner
        return CollectionFilterSet(
            data=request.GET,
            queryset=Collection.objects.all(),
            request=request,
            **kwargs,
        )

    def assert_maxima(self, filters, expected):
        for name, maximum in expected.items():
            with self.subTest(field=name):
                widget = filters.form.fields[name].widget
                self.assertEqual(widget.attrs["data-range_max"], maximum)

    def test_slider_initialization_uses_three_aggregate_queries(self):
        with self.assertNumQueries(3):
            filters = self.get_filters({"scope": "published"})
            self.assert_maxima(
                filters,
                {
                    "connection_rate": 101,
                    "spec_waste_collected": 1601,
                    "collections_per_year": 600,
                    "required_bin_capacity": Decimal("120.5"),
                    "min_bin_size": Decimal("240.5"),
                },
            )

    def test_slider_metadata_reaches_forms_with_and_without_scope(self):
        for data in ({}, {"valid_on": "2024-01-01"}, {"scope": "private"}):
            with self.subTest(data=data):
                self.assert_maxima(
                    self.get_filters(data),
                    {"connection_rate": 101, "collections_per_year": 600},
                )

    def test_zero_maxima_are_not_replaced_by_defaults(self):
        Collection.objects.update(required_bin_capacity=0, min_bin_size=0)
        CollectionPropertyValue.objects.update(average=0)
        CollectionCountOptions.objects.update(standard=0)

        self.assert_maxima(
            self.get_filters({"scope": "published"}),
            dict.fromkeys(
                (
                    "connection_rate",
                    "spec_waste_collected",
                    "collections_per_year",
                    "required_bin_capacity",
                    "min_bin_size",
                ),
                0,
            ),
        )

    def test_all_null_frequency_and_bin_values_use_defaults(self):
        Collection.objects.update(required_bin_capacity=None, min_bin_size=None)
        CollectionCountOptions.objects.update(standard=None)

        self.assert_maxima(
            self.get_filters({"scope": "published"}),
            {
                "collections_per_year": 1000,
                "required_bin_capacity": 1000,
                "min_bin_size": 2000,
            },
        )

    def test_new_filtersets_see_bulk_updates_without_cache_invalidation(self):
        first = self.get_filters({"scope": "published"})
        Collection.objects.filter(pk=self.collection.pk).update(min_bin_size=360)
        CollectionPropertyValue.objects.filter(
            property=self.connection_property
        ).update(average=150.2)

        self.assert_maxima(
            first, {"connection_rate": 101, "min_bin_size": Decimal("240.5")}
        )
        self.assert_maxima(
            self.get_filters({"scope": "published"}),
            {"connection_rate": 151, "min_bin_size": 360},
        )

    def test_explicit_property_range_configuration_is_preserved(self):
        class FixedConnectionRateFilter(ConnectionRateFilter):
            range_min = 5
            range_max = 80
            range_step = 0.5

        class FixedRangeFilterSet(CollectionFilterSet):
            connection_rate = FixedConnectionRateFilter()

        filters = FixedRangeFilterSet(data={"scope": "published"})
        widget = filters.form.fields["connection_rate"].widget
        self.assertEqual(widget.attrs["data-range_min"], 5)
        self.assertEqual(widget.attrs["data-range_max"], 80)
        self.assertEqual(widget.attrs["data-step"], 0.5)

    def test_api_mode_does_not_query_slider_metadata_or_choices(self):
        with self.assertNumQueries(0):
            filters = self.get_filters({"scope": "published"}, skip_min_max=True)
            self.assertIn("allowed_materials", filters.form.fields)

    def test_material_checkboxes_share_one_query_per_filterset(self):
        filters = self.get_filters({"scope": "published"}, skip_min_max=True)

        with self.assertNumQueries(1):
            allowed = filters.form["allowed_materials"].as_widget()
            forbidden = filters.form["forbidden_materials"].as_widget()

        self.assertIn("Choice alpha", allowed)
        self.assertIn("Choice alpha", forbidden)
        with self.assertNumQueries(0):
            self.assertEqual(filters.form["allowed_materials"].as_widget(), allowed)
            self.assertEqual(filters.form["forbidden_materials"].as_widget(), forbidden)

    def test_material_choices_are_request_local_and_do_not_change_validation(self):
        first = self.get_filters({"scope": "published"}, skip_min_max=True)
        first.form["allowed_materials"].as_widget()
        material = WasteComponent.objects.create(name="Choice beta", owner=self.owner)

        self.assertNotIn("Choice beta", first.form["forbidden_materials"].as_widget())
        second = self.get_filters({"scope": "published"}, skip_min_max=True)
        self.assertIn("Choice beta", second.form["forbidden_materials"].as_widget())
        self.assertQuerySetEqual(
            first.form.fields["allowed_materials"].clean([material.pk]), [material]
        )
        invalid = self.get_filters(
            {"scope": "published", "allowed_materials": "not-an-id"},
            skip_min_max=True,
        )
        self.assertFalse(invalid.is_valid())


class CollectionFilterMetadataEmptyTestCase(TestCase):
    def test_empty_property_and_bin_tables_use_defaults(self):
        with self.assertNumQueries(3):
            filters = CollectionFilterSet(
                data={"scope": "published"}, queryset=Collection.objects.none()
            )

        for name, maximum in (
            ("connection_rate", 100),
            ("spec_waste_collected", 1000),
            ("required_bin_capacity", 1000),
            ("min_bin_size", 2000),
        ):
            with self.subTest(field=name):
                self.assertEqual(
                    filters.form.fields[name].widget.attrs["data-range_max"], maximum
                )


class CollectionFilterTestCase(TestCase):
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
        cls.not_seasonal_frequency = CollectionFrequency.objects.create(
            name="Non-Seasonal Test Frequency"
        )
        CollectionCountOptions.objects.create(
            frequency=cls.not_seasonal_frequency,
            season=whole_year,
            standard=35,
            option_1=70,
        )
        cls.seasonal_frequency = CollectionFrequency.objects.create(
            name="Seasonal Test Frequency"
        )
        CollectionCountOptions.objects.create(
            frequency=cls.seasonal_frequency, season=first_half_year, standard=35
        )
        CollectionCountOptions.objects.create(
            frequency=cls.seasonal_frequency, season=second_half_year, standard=35
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="Test Catchment", type="administrative"
        )
        child_catchment = CollectionCatchment.objects.create(
            name="Child Catchment", parent=cls.catchment, type="administrative"
        )
        cls.grandchild_catchment = CollectionCatchment.objects.create(
            parent=child_catchment, type="administrative"
        )
        cls.unrelated_catchment = CollectionCatchment.objects.create(
            name="Unrelated Test Catchment", type="administrative"
        )
        fixed_once_per_week = CollectionFrequency.objects.create(type="Fixed")
        CollectionCountOptions.objects.create(
            frequency=fixed_once_per_week, season=whole_year, standard=52
        )

        cls.collection1 = Collection.objects.create(
            catchment=cls.catchment,
            frequency=cls.not_seasonal_frequency,
            valid_from=timezone.now().date(),
            valid_until=timezone.now().date() + timezone.timedelta(days=30),
            required_bin_capacity=120,
            publication_status="published",
        )
        cls.collection2 = Collection.objects.create(
            catchment=cls.unrelated_catchment,
            frequency=cls.seasonal_frequency,
            valid_from=timezone.now().date(),
            required_bin_capacity=240,
            publication_status="published",
        )
        cls.child_collection = Collection.objects.create(
            catchment=child_catchment,
            frequency=fixed_once_per_week,
            valid_from=timezone.now().date(),
            required_bin_capacity=360,
            publication_status="published",
        )
        cls.predecessor_collection = Collection.objects.create(
            catchment=cls.catchment,
            valid_from=timezone.now().date() - timezone.timedelta(days=90),
            valid_until=timezone.now().date() - timezone.timedelta(days=1),
            description="Predecessor collection",
            publication_status="published",
        )
        cls.collection1.add_predecessor(cls.predecessor_collection)

        MaterialCategory.objects.get_or_create(name="Biowaste component")

        cls.allowed_material_a = WasteComponent.objects.create(name="Filter Allowed A")
        cls.allowed_material_b = WasteComponent.objects.create(name="Filter Allowed B")
        cls.allowed_material_c = WasteComponent.objects.create(name="Filter Allowed C")
        cls.forbidden_material_x = WasteComponent.objects.create(
            name="Filter Forbidden X"
        )
        cls.forbidden_material_y = WasteComponent.objects.create(
            name="Filter Forbidden Y"
        )

        cls.collection1.allowed_materials.set(
            [cls.allowed_material_a, cls.allowed_material_b]
        )
        cls.collection1.forbidden_materials.set([cls.forbidden_material_x])

        cls.collection2.allowed_materials.set([cls.allowed_material_a])
        cls.collection2.forbidden_materials.set([cls.forbidden_material_x])

        cls.child_collection.allowed_materials.set(
            [cls.allowed_material_a, cls.allowed_material_b, cls.allowed_material_c]
        )
        cls.child_collection.forbidden_materials.set(
            [cls.forbidden_material_x, cls.forbidden_material_y]
        )

        # Add connection_rate properties
        prop_connection_rate = Property.objects.create(name="Connection rate")
        CollectionPropertyValue.objects.create(
            collection=cls.collection1,
            property=prop_connection_rate,
            year=2022,
            average=70,
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection2,
            property=prop_connection_rate,
            year=2021,
            average=30,
        )

        # Add specific waste collected properties
        prop_spec_waste_collected = Property.objects.create(
            name="specific waste collected", unit="kg/(cap.*a)"
        )
        CollectionPropertyValue.objects.create(
            property=prop_spec_waste_collected,
            collection=cls.collection1,
            year=2022,
            average=100,
        )
        CollectionPropertyValue.objects.create(
            property=prop_spec_waste_collected,
            collection=cls.collection1,
            year=2021,
            average=150,
        )
        CollectionPropertyValue.objects.create(
            property=prop_spec_waste_collected,
            collection=cls.collection2,
            year=2022,
            average=200,
        )

    def setUp(self):
        self.data = {
            field_name: field.initial
            for field_name, field in CollectionFilterSet().form.fields.items()
            if field.initial
        }
        self.data["valid_on"] = None

    def test_only_initial_values_returns_complete_queryset(self):
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerySetEqual(Collection.objects.order_by("id"), qs.order_by("id"))

    def test_catchment_filter(self):
        self.data.update({"catchment": self.catchment.pk})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertEqual(3, qs.count())

    def test_filter_includes_child_catchments(self):
        self.data.update({"catchment": self.catchment.pk})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.child_collection, qs)

    def test_filter_includes_collections_from_upstream_catchments_if_there_are_none_downstream(
        self,
    ):
        self.data.update({"catchment": self.grandchild_catchment.pk})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.child_collection, qs)
        self.assertIn(self.collection1, qs)

    def test_country_level_catchment_falls_back_to_country_collections(self):
        sweden_region = Region.objects.create(name="Sweden Region", country="SE")
        sweden_catchment = CollectionCatchment.objects.create(
            name="Sverige (SE)",
            type="nuts",
            region=sweden_region,
        )
        unrelated_parent = CollectionCatchment.objects.create(
            name="Wrong Parent",
            type="nuts",
        )
        municipality_catchment = CollectionCatchment.objects.create(
            name="Stockholm (0180)",
            type="administrative",
            parent=unrelated_parent,
            region=sweden_region,
        )
        sweden_collection = Collection.objects.create(
            catchment=municipality_catchment,
            publication_status="published",
        )

        self.data.update({"catchment": sweden_catchment.pk})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs

        self.assertIn(sweden_collection, qs)

    def test_non_numeric_collector_is_ignored(self):
        data = self.data.copy()
        data.update({"collector": "*"})

        filtr = CollectionFilterSet(data, queryset=Collection.objects.all())
        filtr.is_valid()
        self.assertNotIn("collector", filtr.form.errors)
        self.assertQuerySetEqual(
            Collection.objects.order_by("id"), filtr.qs.order_by("id")
        )

    def test_allowed_materials_filter_matches_selected_material(self):
        self.data.update({"allowed_materials": [self.allowed_material_b.pk]})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection1, qs)
        self.assertIn(self.child_collection, qs)
        self.assertNotIn(self.collection2, qs)

    def test_forbidden_materials_filter_matches_selected_material(self):
        self.data.update({"forbidden_materials": [self.forbidden_material_y.pk]})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertNotIn(self.collection1, qs)
        self.assertNotIn(self.collection2, qs)
        self.assertIn(self.child_collection, qs)

    def test_allowed_and_forbidden_filters_intersect_selected_materials(self):
        self.data.update(
            {
                "allowed_materials": [self.allowed_material_b.pk],
                "forbidden_materials": [self.forbidden_material_y.pk],
            }
        )
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerySetEqual(qs, [self.child_collection], ordered=False)

    def test_connection_rate_range_filter_fields_exists_in_filter_and_form(self):
        self.data.update({"connection_rate_min": 50, "connection_rate_max": 99})
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertIn("connection_rate", filtr.filters.keys())
        self.assertIn("connection_rate", filtr.form.fields.keys())

    def test_connection_rate_range_filter_renders_with_converted_percentage_values(
        self,
    ):
        self.data.update({"connection_rate_min": 50, "connection_rate_max": 99})
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertInHTML(
            '<span class="numeric-slider-range-text fst-italic" id="id_connection_rate_text">50% - 99%</span>',
            filtr.form.as_p(),
        )

    def test_connection_rate_returns_only_collections_in_given_range(self):
        self.data.update(
            {
                "connection_rate_min": 50,
                "connection_rate_max": 100,
                "connection_rate_is_null": False,
            }
        )
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        qs = filtr.qs
        expected_qs = Collection.objects.filter(pk__in=[self.collection1.pk])
        self.assertQuerySetEqual(expected_qs, qs, ordered=False)

    def test_participation_policy_filter_variants(self):
        from sources.waste_collection.models import Collection

        base_kwargs = {
            "catchment": self.collection1.catchment,
            "collector": self.collection1.collector,
            "collection_system": self.collection1.collection_system,
            "waste_category": self.collection1.waste_category,
        }
        values = [
            ("MANDATORY", "MANDATORY"),
            ("VOLUNTARY", "VOLUNTARY"),
            (
                "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
                "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
            ),
            ("not_specified", "not_specified"),
            (None, None),
            ("", None),
        ]
        for value, filter_value in values:
            collection = Collection.objects.create(
                **base_kwargs, participation_policy=value
            )
            data = {"participation_policy": filter_value} if filter_value else {}
            filtr = CollectionFilterSet(data, queryset=Collection.objects.all())
            if filter_value:
                self.assertIn(collection, filtr.qs)
            else:
                self.assertIn(
                    collection, filtr.qs
                )  # For None/blank, should be included if no filter
            collection.delete()

        self.data.update(
            {
                "connection_rate_min": 50,
                "connection_rate_max": 100,
                "connection_rate_is_null": False,
            }
        )
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        qs = filtr.qs
        expected_qs = Collection.objects.filter(pk__in=[self.collection1.pk])
        self.assertQuerySetEqual(expected_qs, qs, ordered=False)

    def test_seasonal_frequency_filter_field_exists_in_filter_and_form(self):
        self.data.update({"seasonal_frequency": True})
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertIn("seasonal_frequency", filtr.filters.keys())
        self.assertIn("seasonal_frequency", filtr.form.fields.keys())

    def test_seasonal_frequency_filter_returns_collections_with_non_seasonal_frequency_on_false(
        self,
    ):
        self.data.update({"seasonal_frequency": False})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection1, qs)
        self.assertNotIn(self.collection2, qs)

    def test_seasonal_frequency_filter_returns_collections_with_seasonal_frequency_on_true(
        self,
    ):
        self.data.update({"seasonal_frequency": True})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection2, qs)
        self.assertNotIn(self.collection1, qs)

    def test_seasonal_frequency_filter_returns_all_collections_when_unselected(self):
        self.data.update({"seasonal_frequency": None})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerySetEqual(Collection.objects.order_by("id"), qs.order_by("id"))

    def test_optional_frequency_filter_field_exists_in_filter_and_form(self):
        self.data.update({"optional_frequency": True})
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertIn("optional_frequency", filtr.filters.keys())
        self.assertIn("optional_frequency", filtr.form.fields.keys())

    def test_optional_frequency_filter_returns_collections_without_options_on_false(
        self,
    ):
        self.data.update({"optional_frequency": False})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        opts = CollectionCountOptions.objects.filter(
            Q(option_1__isnull=True)
            & Q(option_2__isnull=True)
            & Q(option_3__isnull=True)
            & Q(frequency=self.seasonal_frequency)
        )
        self.assertEqual(2, opts.count())
        for opt in opts:
            self.assertIsNone(opt.option_1)
        fr = opts.first().frequency
        self.assertEqual(
            Collection.objects.filter(frequency=fr).first(), self.collection2
        )
        self.assertIn(self.collection2, qs)
        self.assertNotIn(self.collection1, qs)

    def test_optional_frequency_filter_returns_collections_with_seasonal_frequency_on_true(
        self,
    ):
        self.data.update({"optional_frequency": True})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection1, qs)
        self.assertNotIn(self.collection2, qs)

    def test_optional_frequency_filter_returns_all_collections_when_unselected(self):
        self.data.update({"optional_frequency": None})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerySetEqual(Collection.objects.order_by("id"), qs.order_by("id"))

    def test_collections_per_year_field_exists_in_filter_form(self):
        filtr = CollectionFilterSet(queryset=Collection.objects.all())
        self.assertIn("collections_per_year", filtr.filters.keys())
        self.assertIn("collections_per_year", filtr.form.fields.keys())

    def test_collections_per_year_returns_only_matching_results(self):
        self.data.update(
            {
                "collections_per_year_min": 60,
                "collections_per_year_max": 100,
                "collections_per_year_is_null": False,
            }
        )
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        expected = Collection.objects.filter(pk__in=[self.collection2.pk])
        self.assertQuerySetEqual(qs, expected, ordered=False)

    def test_collections_per_year_range_filter_renders_with_calculated_boundaries(self):
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertInHTML(
            '<span class="numeric-slider-range-text fst-italic" id="id_collections_per_year_text">0 - 70</span>',
            filtr.form.as_p(),
        )

    def test_specific_waste_collected_field_exists_in_filter_form(self):
        filtr = CollectionFilterSet(queryset=Collection.objects.all())
        self.assertIn("spec_waste_collected", filtr.filters.keys())
        self.assertIn("spec_waste_collected", filtr.form.fields.keys())

    def test_get_spec_waste_collected_with_average_returns_correctly(self):
        data = {
            "spec_waste_collected_filter_method": "average",
            "spec_waste_collected_min": 150,
            "spec_waste_collected_max": 1000,
        }
        filtr = CollectionFilterSet(data=data, queryset=Collection.objects.all())
        filtr.is_valid()
        self.assertTrue(filtr.is_valid())
        qs = filtr.qs
        self.assertIn(self.collection2, qs)
        self.assertNotIn(self.collection1, qs)

    def test_spec_waste_collected_include_unknown_includes_null_values_if_checked(self):
        data = self.data.update(
            {
                "spec_waste_collected_filter_method": "average",
                "spec_waste_collected_min": 0,
                "spec_waste_collected_max": 1000,
            }
        )
        filtr = CollectionFilterSet(data, queryset=Collection.objects.all())
        self.assertQuerySetEqual(
            Collection.objects.all().order_by("id"), filtr.qs.order_by("id")
        )

    def test_filter_form_has_no_formtags(self):
        filtr = CollectionFilterSet(queryset=Collection.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)

    def test_filter_form_omits_obsolete_ordering_control(self):
        filtr = CollectionFilterSet(queryset=Collection.objects.all())

        self.assertNotIn("ordering", filtr.filters)
        self.assertNotIn("ordering", filtr.form.fields)

    def test_valid_on_filter(self):
        self.data["valid_on"] = timezone.now().date()
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs

        self.assertIn(self.collection1, qs)
        self.assertIn(self.collection2, qs)
        self.assertIn(self.child_collection, qs)
        self.assertNotIn(self.predecessor_collection, qs)

    def test_valid_on_finds_collections_from_past_dates(self):
        self.data["valid_on"] = timezone.now().date() - timezone.timedelta(days=1)
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs

        self.assertNotIn(self.collection1, qs)
        self.assertNotIn(self.collection2, qs)
        self.assertNotIn(self.child_collection, qs)
        self.assertIn(self.predecessor_collection, qs)

    def test_required_bin_capacity_filter(self):
        # Filter by required_bin_capacity in range 200-400 (inclusive)
        data = {"required_bin_capacity_min": 200, "required_bin_capacity_max": 400}
        qs = CollectionFilterSet(
            data,
            queryset=Collection.objects.filter(
                pk__in=[
                    self.collection1.pk,
                    self.collection2.pk,
                    self.child_collection.pk,
                ]
            ),
        ).qs
        qs_pks = set(qs.values_list("pk", flat=True))
        self.assertNotIn(self.collection1.pk, qs_pks)
        self.assertIn(self.collection2.pk, qs_pks)
        self.assertIn(self.child_collection.pk, qs_pks)
        # Filter with null included
        c4 = Collection.objects.create(
            name="RequiredBinCapacityC4",
            catchment=self.catchment,
            required_bin_capacity=None,
        )
        data = {
            "required_bin_capacity_min": 200,
            "required_bin_capacity_max": 400,
            "required_bin_capacity_is_null": True,
        }
        qs = CollectionFilterSet(
            data,
            queryset=Collection.objects.filter(
                pk__in=[
                    self.collection1.pk,
                    self.collection2.pk,
                    self.child_collection.pk,
                    c4.pk,
                ]
            ),
        ).qs
        qs_pks = set(qs.values_list("pk", flat=True))
        self.assertNotIn(self.collection1.pk, qs_pks)
        self.assertIn(self.collection2.pk, qs_pks)
        self.assertIn(self.child_collection.pk, qs_pks)
        self.assertIn(c4.pk, qs_pks)


class CollectorFilterTestCase(TestCase):
    def test_filter_form_has_no_formtags(self):
        filtr = CollectorFilter(queryset=Collector.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
