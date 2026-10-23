"""Unit tests for the ReviewItemCollector review-queue service."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db.models.signals import post_save, pre_save
from django.http import QueryDict
from django.test import TestCase
from django.utils import timezone
from factory.django import mute_signals

from bibliography.models import Source
from sources.waste_collection.models import Collection
from utils.object_management.models import UserCreatedObject
from utils.object_management.review_queue import (
    ReviewItemCollector,
    ReviewItemReference,
)
from utils.properties.models import Property


class ReviewItemCollectorTests(TestCase):
    """The collector discovers moderatable models and builds the review queue."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="rq-owner")
        cls.staff = User.objects.create_user(username="rq-staff", is_staff=True)
        cls.moderator = User.objects.create_user(username="rq-moderator")
        cls.outsider = User.objects.create_user(username="rq-outsider")
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=ContentType.objects.get_for_model(Collection),
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator.user_permissions.add(permission)

        cls.now = timezone.now()
        with mute_signals(post_save, pre_save):
            cls.private_collection = Collection.objects.create(
                name="RQ Private",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.review_collection = Collection.objects.create(
                name="RQ Review Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
                submitted_at=cls.now,
            )
            cls.own_review_collection = Collection.objects.create(
                name="RQ Own Review Collection",
                owner=cls.staff,
                publication_status=UserCreatedObject.STATUS_REVIEW,
                submitted_at=cls.now,
            )
            cls.review_property = Property.objects.create(
                name="RQ Review Property",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
                submitted_at=cls.now - timedelta(hours=1),
            )
        cls.review_source = Source.objects.create(
            owner=cls.owner,
            title="RQ Review Source",
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )

    @staticmethod
    def _identities(items):
        return {(type(item), item.pk) for item in items}

    # --- available_models -------------------------------------------------

    def test_available_models_includes_only_models_with_foreign_review_items(self):
        models = ReviewItemCollector(self.staff).available_models()
        self.assertIn(Collection, models)
        self.assertIn(Property, models)

    def test_available_models_requires_moderation_permission(self):
        self.assertEqual(ReviewItemCollector(self.outsider).available_models(), [])
        moderator_models = ReviewItemCollector(self.moderator).available_models()
        self.assertIn(Collection, moderator_models)
        self.assertNotIn(Property, moderator_models)

    def test_available_models_skips_models_on_expected_query_errors(self):
        collector = ReviewItemCollector(self.staff)
        for exc in (FieldDoesNotExist("no field"), AttributeError("no attr")):
            with (
                self.subTest(exception=exc),
                patch.object(
                    ReviewItemCollector,
                    "in_review_queryset_for_model",
                    side_effect=exc,
                ),
            ):
                self.assertEqual(collector.available_models(), [])

    def test_available_models_propagates_unexpected_errors(self):
        collector = ReviewItemCollector(self.staff)
        with patch.object(
            ReviewItemCollector,
            "in_review_queryset_for_model",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                collector.available_models()

    # --- has_review_items ---------------------------------------------------

    def test_has_review_items_for_staff(self):
        self.assertTrue(ReviewItemCollector(self.staff).has_review_items())

    def test_has_review_items_scoped_by_moderation_permission(self):
        self.assertTrue(ReviewItemCollector(self.moderator).has_review_items())
        self.assertFalse(ReviewItemCollector(self.outsider).has_review_items())

    def test_has_review_items_rejects_anonymous_and_missing_users(self):
        self.assertFalse(ReviewItemCollector(AnonymousUser()).has_review_items())
        self.assertFalse(ReviewItemCollector(None).has_review_items())

    def test_has_review_items_propagates_unexpected_errors(self):
        collector = ReviewItemCollector(self.staff)
        with patch.object(
            ReviewItemCollector,
            "in_review_queryset_for_model",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                collector.has_review_items()

    # --- collect / references / hydrate -------------------------------------

    def test_collect_returns_items_across_models_without_own_items(self):
        items = ReviewItemCollector(self.staff).collect()
        identities = self._identities(items)
        self.assertIn((Collection, self.review_collection.pk), identities)
        self.assertIn((Property, self.review_property.pk), identities)
        self.assertIn((Source, self.review_source.pk), identities)
        # Own items and non-review items are excluded
        self.assertNotIn((Collection, self.own_review_collection.pk), identities)
        self.assertNotIn((Collection, self.private_collection.pk), identities)

    def test_collect_applies_search_filter_in_sql(self):
        items = ReviewItemCollector(
            self.staff, QueryDict("search=RQ+Review+Collection")
        ).collect([Collection])
        self.assertEqual(
            self._identities(items), {(Collection, self.review_collection.pk)}
        )

    def test_collect_limits_per_model_when_unfiltered(self):
        with mute_signals(post_save, pre_save):
            for index in range(25):
                Collection.objects.create(
                    name=f"RQ Bulk {index}",
                    owner=self.owner,
                    publication_status=UserCreatedObject.STATUS_REVIEW,
                    submitted_at=self.now,
                )
        collector = ReviewItemCollector(self.staff, page_size=2)
        collections = collector.collect([Collection])
        self.assertEqual(len(collections), 2 * max(10, 1))

    def test_references_are_lightweight_namedtuples(self):
        references, querysets = ReviewItemCollector(self.staff).references([Collection])
        reference = next(
            ref for ref in references if ref.pk == self.review_collection.pk
        )
        self.assertIsInstance(reference, ReviewItemReference)
        self.assertEqual(reference.model, Collection)
        self.assertEqual(reference.name, self.review_collection.name)
        self.assertIn(Collection, querysets)

    def test_hydrate_rechecks_filters_at_load_time(self):
        collector = ReviewItemCollector(self.staff)
        references, querysets = collector.references([Collection])
        target = next(ref for ref in references if ref.pk == self.review_collection.pk)
        Collection.objects.filter(pk=target.pk).update(
            publication_status=UserCreatedObject.STATUS_PUBLISHED
        )
        hydrated = collector.hydrate([target], querysets)
        self.assertEqual(hydrated, [])

    def test_references_propagates_unexpected_errors(self):
        collector = ReviewItemCollector(self.staff)
        with patch.object(
            ReviewItemCollector,
            "in_review_queryset_for_model",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                collector.references([Collection])

    # --- fallback_queryset ----------------------------------------------------

    def test_fallback_queryset_is_empty(self):
        self.assertEqual(ReviewItemCollector.fallback_queryset().count(), 0)
