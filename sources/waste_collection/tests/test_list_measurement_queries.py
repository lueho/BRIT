from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.test import RequestFactory, TestCase

from materials.models import MaterialCategory
from utils.object_management.models import ObjectEditorGrant, get_default_owner
from utils.properties.models import Property, Unit

from ..filters import CollectionFilterSet, ConnectionRateFilter
from ..models import Collection, CollectionPropertyValue, WasteComponent
from ..views import CollectionPublishedListView


class CollectionMeasurementQueryTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="measurement-owner")
        cls.editor = User.objects.create_user(username="measurement-editor")
        cls.moderator = User.objects.create_user(username="measurement-moderator")
        cls.moderator.user_permissions.add(
            Permission.objects.get(codename="can_moderate_collectionpropertyvalue")
        )
        cls.connection = Property.objects.create(name="Connection rate")
        cls.specific = Property.objects.create(name="specific waste collected")
        cls.source_property = Property.objects.create(name="Measurement source")
        cls.unit = Unit.objects.create(name="Measurement query unit")

    def collection(self, name="Alpha", **kwargs):
        return Collection.objects.bulk_create(
            [
                Collection(
                    name=name,
                    owner=self.owner,
                    publication_status="published",
                    **kwargs,
                )
            ]
        )[0]

    def measurement(self, collection, average, **kwargs):
        fields = {
            "collection": collection,
            "average": average,
            "property": self.connection,
            "unit": self.unit,
            "owner": self.owner,
            "publication_status": "published",
            "year": 2023,
            **kwargs,
        }
        return CollectionPropertyValue.objects.bulk_create(
            [CollectionPropertyValue(**fields)]
        )[0]

    def request(self, data=None, user=None):
        request = RequestFactory().get(
            "/collections/", {"scope": "published", **(data or {})}
        )
        request.user = user or AnonymousUser()
        return request

    def filtered_ids(self, bounds, include_null=False, user=None):
        filter_ = ConnectionRateFilter()
        filter_.parent = type("Parent", (), {"request": self.request(user=user)})()
        return set(
            filter_.filter(
                Collection.objects.all(), (slice(*bounds), include_null)
            ).values_list("pk", flat=True)
        )

    @staticmethod
    def ranges(**ranges):
        data = {}
        for name, (minimum, maximum, include_null) in ranges.items():
            data.update(
                {
                    f"{name}_min": str(minimum),
                    f"{name}_max": str(maximum),
                    f"{name}_is_null": str(include_null).lower(),
                }
            )
        return data

    def test_measurement_visibility_for_anonymous_owner_editor_and_moderator(self):
        private = self.collection("Private measurement")
        review = self.collection("Review measurement")
        value = self.measurement(private, 75, publication_status="private")
        self.measurement(review, 75, publication_status="review")
        ObjectEditorGrant.objects.create(
            content_object=value, editor=self.editor, granted_by=self.owner
        )
        for user, expected in (
            (None, set()),
            (self.owner, {private.pk, review.pk}),
            (self.editor, {private.pk}),
            (self.moderator, {review.pk}),
        ):
            with self.subTest(user=user):
                self.assertEqual(self.filtered_ids((70, 80), user=user), expected)

    def test_generated_visibility_follows_source_not_projection_status(self):
        visible = self.collection("Visible source")
        hidden = self.collection("Hidden source")
        for collection, source_status, projection_status in (
            (visible, "published", "private"),
            (hidden, "private", "published"),
        ):
            source = self.measurement(
                collection,
                100,
                property=self.source_property,
                publication_status=source_status,
            )
            self.measurement(
                collection,
                75,
                is_derived=True,
                derived_from=source,
                publication_status=projection_status,
            )
        self.assertEqual(self.filtered_ids((70, 80)), {visible.pk})

    def test_visible_manual_precedes_derived_with_null_year_and_matching_unit(self):
        collection = self.collection()
        source = self.measurement(
            collection, 100, property=self.source_property, year=None
        )
        self.measurement(
            collection, 75, year=None, is_derived=True, derived_from=source
        )
        self.measurement(collection, 25, year=None, publication_status="private")
        self.assertEqual(self.filtered_ids((70, 80)), {collection.pk})
        self.assertEqual(self.filtered_ids((70, 80), user=self.owner), set())
        self.assertEqual(self.filtered_ids((20, 30), user=self.owner), {collection.pk})

    def test_manual_different_year_or_unit_does_not_suppress_derived(self):
        for year, unit in (
            (2022, self.unit),
            (2023, Unit.objects.create(name="Other unit")),
        ):
            collection = self.collection(f"Other key {year} {unit.pk}")
            source = self.measurement(collection, 100, property=self.source_property)
            self.measurement(collection, 75, is_derived=True, derived_from=source)
            self.measurement(collection, 25, year=year, unit=unit)
        self.assertEqual(
            self.filtered_ids((50, 50)),
            set(Collection.objects.values_list("pk", flat=True)),
        )

    def test_null_average_means_missing_or_no_visible_measurements_not_zero(self):
        missing = self.collection("Missing")
        hidden = self.collection("Hidden")
        zero = self.collection("Zero")
        self.measurement(hidden, 75, publication_status="private")
        self.measurement(zero, 0)
        self.assertEqual(self.filtered_ids((70, 80)), set())
        self.assertEqual(self.filtered_ids((70, 80), True), {missing.pk, hidden.pk})
        self.assertEqual(self.filtered_ids((0, 0)), {zero.pk})

    def test_combined_ranges_use_independent_averages_not_individual_values(self):
        collection = self.collection()
        for property_, values in (
            (self.connection, (20, 80)),
            (self.specific, (100, 300)),
        ):
            for year, average in enumerate(values, 2022):
                self.measurement(collection, average, property=property_, year=year)
        for bounds, expected in (((50, 50), {collection.pk}), ((20, 20), set())):
            data = self.ranges(
                connection_rate=(*bounds, False), spec_waste_collected=(200, 200, False)
            )
            filters = CollectionFilterSet(
                data=data, request=self.request(data), skip_min_max=True
            )
            self.assertTrue(filters.is_valid(), filters.errors)
            self.assertEqual(set(filters.qs.values_list("pk", flat=True)), expected)

    def list_response(self, data):
        with patch.object(CollectionFilterSet, "_set_filter_ranges"):
            response = CollectionPublishedListView.as_view()(self.request(data))
        self.assertEqual(response.status_code, 200)
        return response.context_data

    def test_material_joins_pagination_count_and_initials(self):
        MaterialCategory.objects.get_or_create(
            name="Biowaste component", owner=get_default_owner()
        )
        materials = [
            WasteComponent.objects.create(
                name=f"Query material {i}", publication_status="published"
            )
            for i in range(4)
        ]
        collections = [self.collection(f"Alpha {i:02}") for i in range(13)]
        for collection in collections:
            self.measurement(collection, 50)
            collection.allowed_materials.set(materials[:2])
            collection.forbidden_materials.set(materials[2:])
        self.measurement(self.collection("Zulu excluded"), 0)
        data = {
            **self.ranges(connection_rate=(50, 50, False)),
            "allowed_materials": [m.pk for m in materials[:2]],
            "forbidden_materials": [m.pk for m in materials[2:]],
        }
        first = self.list_response(data)
        self.assertTrue(first["filter"].is_valid(), first["filter"].errors)
        self.assertEqual(first["paginator"].count, 13)
        second = self.list_response({**data, "page": 2})
        self.assertEqual(
            [obj.pk for obj in first["object_list"]]
            + [obj.pk for obj in second["object_list"]],
            [obj.pk for obj in collections],
        )
        self.assertEqual(
            {item["letter"] for item in first["letter_index"] if item["enabled"]}, {"A"}
        )
        empty_letter = self.list_response({**data, "letter": "Z"})
        self.assertEqual(empty_letter["paginator"].count, 0)
        self.assertEqual(
            empty_letter["letter_index"],
            [
                dict(item, active=item["letter"] == "Z")
                for item in first["letter_index"]
            ],
        )

    def test_zero_results_have_empty_count_page_and_initials(self):
        self.measurement(self.collection(), 50)
        context = self.list_response(self.ranges(connection_rate=(90, 100, False)))
        self.assertEqual(context["paginator"].count, 0)
        self.assertEqual(list(context["object_list"]), [])
        self.assertFalse(any(item["enabled"] for item in context["letter_index"]))

    def test_invalid_numeric_range_does_not_return_unfiltered_rows(self):
        self.measurement(self.collection(), 50)
        context = self.list_response({"connection_rate_min": "invalid"})
        self.assertTrue(context["filter"].errors)
        self.assertEqual(list(context["object_list"]), [])

    def test_default_list_bypasses_pk_boundary(self):
        context = self.list_response({})
        query = context["filter"].qs.query
        self.assertFalse(query.distinct)
        self.assertIsNone(query.group_by)
        self.assertNotIn("SELECT", str(query).partition("WHERE")[2])

    def test_measurement_range_does_not_aggregate_outer_collection_rows(self):
        filters = CollectionFilterSet(
            data=self.ranges(connection_rate=(50, 75, True)), skip_min_max=True
        )
        self.assertTrue(filters.is_valid(), filters.errors)
        self.assertIsNone(filters.qs.query.group_by)
        self.assertNotIn("avg_value", filters.qs.query.annotations)

    def test_filtered_list_uses_pk_boundary_before_display_joins(self):
        context = self.list_response(self.ranges(connection_rate=(50, 75, True)))
        query = context["filter"].qs.query
        self.assertFalse(query.distinct)
        self.assertIsNone(query.group_by)
        self.assertIn("IN (SELECT", str(query))
