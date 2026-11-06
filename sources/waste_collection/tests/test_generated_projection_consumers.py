"""Independently asserted numerical selection contracts for projections."""

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.test import RequestFactory, TestCase

from sources.waste_collection.derived_values import create_or_update_derived_cpv
from sources.waste_collection.filters import (
    CollectionFilterSet,
    CollectionsPerYearFilter,
    NullableCollectionPropertyValueRangeFilter,
)
from sources.waste_collection.models import (
    Collection,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
)
from sources.waste_collection.serializers import (
    CollectionFlatSerializer,
    CollectionPropertyValueSerializer,
)
from sources.waste_collection.tests import (
    test_generated_pipeline_numeric as numeric_contracts,
)
from sources.waste_collection.waste_atlas.viewsets import (
    _amounts_for_year,
    _property_value_q,
)


class GeneratedConsumerNumericalTests(TestCase):
    setUpTestData = classmethod(
        numeric_contracts.GeneratedPipelineNumericalTests.setUpTestData.__func__
    )
    setUp = numeric_contracts.GeneratedPipelineNumericalTests.setUp
    _raw = numeric_contracts.GeneratedPipelineNumericalTests._raw
    _assert_output = numeric_contracts.GeneratedPipelineNumericalTests._assert_output

    def _specific_ids(self, values):
        return {value.pk for value in values if value.property_id == self.specific.pk}

    def _range(self, actor, minimum, maximum):
        filter_ = NullableCollectionPropertyValueRangeFilter()
        filter_.property_name = self.specific.name
        filter_.parent = SimpleNamespace(request=SimpleNamespace(user=actor))
        return set(
            filter_.apply_range(
                Collection.objects.filter(pk=self.collection.pk),
                slice(minimum, maximum),
                False,
            ).values_list("pk", flat=True)
        )

    def test_visible_manual_measurement_wins_without_averaging_generated_copy(self):
        source = self._raw(self.total, self.total_unit, "300", state="published")
        generated = self._assert_output(
            source, self.specific, self.specific_unit, "150"
        )
        self._raw(
            self.specific,
            self.specific_unit,
            "900",
            owner=self.stranger,
            state="private",
        )
        manual = self._raw(self.specific, self.specific_unit, "400", state="published")
        selected = set(
            CollectionPropertyValue.objects.filter(
                _property_value_q(AnonymousUser()),
                property=self.specific,
            ).values_list("pk", flat=True)
        )
        self.assertEqual(selected, {manual.pk})
        self.assertNotIn(generated.pk, selected)
        self.assertEqual(
            _amounts_for_year(
                2024,
                [self.collection.pk],
                {self.collection.pk: self.catchment.pk},
                [self.catchment.pk],
                user=AnonymousUser(),
            ),
            {self.catchment.pk: 400},
        )
        self.assertEqual(self._range(AnonymousUser(), 399, 401), {self.collection.pk})
        self.assertEqual(self._range(AnonymousUser(), 149, 151), set())
        displayed = self.collection.collectionpropertyvalues_for_display(
            AnonymousUser()
        )
        self.assertEqual(self._specific_ids(displayed), {manual.pk})

    def test_private_source_with_public_copied_status_cannot_match_numeric_filter(self):
        source = self._raw(self.total, self.total_unit, "300")
        generated, _action = create_or_update_derived_cpv(
            source, owner=self.stranger, publication_status="published"
        )
        self.assertEqual(generated.average, 150)
        self.assertEqual(self._range(AnonymousUser(), 149, 151), set())

    def test_public_source_with_private_copied_status_can_match_numeric_filter(self):
        source = self._raw(self.total, self.total_unit, "300", state="published")
        generated, _action = create_or_update_derived_cpv(
            source, owner=self.stranger, publication_status="private"
        )
        self.assertEqual(generated.average, 150)
        self.assertEqual(self._range(AnonymousUser(), 149, 151), {self.collection.pk})
        representation = CollectionPropertyValueSerializer(generated).data
        self.assertEqual(representation["publication_status"], "published")
        self.assertEqual(representation["derived_from"], source.pk)

    def test_display_owner_priority_uses_source_not_copied_owner(self):
        owned = self._raw(self.total, self.total_unit, "300")
        foreign = self._raw(
            self.total,
            self.total_unit,
            "700",
            owner=self.stranger,
            state="published",
        )
        expected, _action = create_or_update_derived_cpv(owned, owner=self.stranger)
        other, _action = create_or_update_derived_cpv(foreign, owner=self.owner)
        self.assertEqual(expected.average, 150)
        self.assertEqual(other.average, 350)
        values = list(
            Collection.visible_collectionpropertyvalues(
                [self.collection.pk], self.owner
            ).filter(property=self.specific)
        )
        self.assertEqual([value.pk for value in values], [expected.pk, other.pk])

    def test_display_publication_priority_uses_source_not_copied_status(self):
        administrator = User.objects.create_user("numeric-consumer-administrator")
        administrator.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="object_management",
                codename="administer_objects",
            )
        )
        private = self._raw(self.total, self.total_unit, "300")
        public = self._raw(
            self.total,
            self.total_unit,
            "700",
            owner=self.stranger,
            state="published",
        )
        other, _action = create_or_update_derived_cpv(
            private, owner=self.owner, publication_status="published"
        )
        expected, _action = create_or_update_derived_cpv(
            public, owner=self.owner, publication_status="private"
        )
        self.assertEqual(expected.average, 350)
        self.assertEqual(other.average, 150)
        values = list(
            Collection.visible_collectionpropertyvalues(
                [self.collection.pk], administrator
            ).filter(property=self.specific)
        )
        self.assertEqual([value.pk for value in values], [expected.pk, other.pk])

    def test_background_export_actor_is_used_for_source_selection(self):
        source = self._raw(self.total, self.total_unit, "300")
        generated, _action = create_or_update_derived_cpv(source, owner=self.stranger)
        self.assertEqual(generated.average, 150)
        serializer = CollectionFlatSerializer(context={"user": self.owner})
        selected = serializer.get_collection_property_values(self.collection)
        self.assertEqual(self._specific_ids(selected), {generated.pk})

    def test_slider_max_ignores_hidden_manual_and_private_source_copies(self):
        source = self._raw(self.total, self.total_unit, "300", state="published")
        self._assert_output(source, self.specific, self.specific_unit, "150")
        self._raw(
            self.specific,
            self.specific_unit,
            "900",
            owner=self.stranger,
            state="private",
        )
        hidden_source = self._raw(
            self.total,
            self.total_unit,
            "1000",
            owner=self.stranger,
            state="private",
        )
        hidden, _action = create_or_update_derived_cpv(
            hidden_source, publication_status="published"
        )
        self.assertEqual(hidden.average, 500)
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        with patch.object(
            CollectionFilterSet.base_filters["spec_waste_collected"],
            "property_name",
            self.specific.name,
        ):
            filters = CollectionFilterSet(
                queryset=Collection.objects.filter(pk=self.collection.pk),
                request=request,
            )
        self.assertEqual(filters.filters["spec_waste_collected"].range_max, 150)

    def test_frequency_slider_ignores_an_unreadable_frequency(self):
        public_frequency = CollectionFrequency.objects.create(
            name="public frequency",
            owner=self.owner,
            publication_status="published",
        )
        private_frequency = CollectionFrequency.objects.create(
            name="private frequency",
            owner=self.stranger,
            publication_status="private",
        )
        whole_year = CollectionSeason.objects.get(
            distribution__name="Months of the year",
            first_timestep__name="January",
            last_timestep__name="December",
        )
        CollectionCountOptions.objects.create(
            frequency=public_frequency, season=whole_year, standard=35
        )
        CollectionCountOptions.objects.create(
            frequency=private_frequency, season=whole_year, standard=70
        )
        request = RequestFactory().get("/", {"scope": "published"})
        request.user = AnonymousUser()
        filters = CollectionFilterSet(
            data=request.GET,
            queryset=Collection.objects.filter(pk=self.collection.pk),
            request=request,
        )
        self.assertEqual(
            filters.form.fields["collections_per_year"].widget.attrs["data-range_max"],
            35,
        )

    def test_frequency_range_uses_only_readable_frequency_evidence(self):
        private_frequency = CollectionFrequency.objects.create(
            owner=self.stranger, publication_status="private"
        )
        whole_year = CollectionSeason.objects.get(
            distribution__name="Months of the year",
            first_timestep__name="January",
            last_timestep__name="December",
        )
        CollectionCountOptions.objects.create(
            frequency=private_frequency, season=whole_year, standard=70
        )
        Collection.objects.filter(pk=self.collection.pk).update(
            frequency=private_frequency
        )
        collections = Collection.objects.filter(pk=self.collection.pk)
        for actor, expected_known, expected_unknown in (
            (AnonymousUser(), set(), {self.collection.pk}),
            (self.stranger, {self.collection.pk}, set()),
        ):
            with self.subTest(actor=actor):
                filter_ = CollectionsPerYearFilter()
                filter_.parent = SimpleNamespace(request=SimpleNamespace(user=actor))
                self.assertEqual(
                    set(
                        filter_.apply_range(
                            collections, slice(70, 70), False
                        ).values_list("pk", flat=True)
                    ),
                    expected_known,
                )
                self.assertEqual(
                    set(
                        filter_.apply_range(collections, slice(0, 0), True).values_list(
                            "pk", flat=True
                        )
                    ),
                    expected_unknown,
                )
