"""Tests for the per-instance publication-status tracking used by the
moderation-cache invalidation in ``utils.object_management.signals``."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from sources.waste_collection.models import Collection


class ModerationCacheSignalTests(TestCase):
    """Saving a UserCreatedObject must only clear moderator caches when a
    transition involving 'review' can actually have happened — not on every
    full save."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="signal-mod", is_staff=True)
        cls.owner = User.objects.create_user(username="signal-owner")

    def _cache_keys(self):
        return (
            f"has_pending_review_items_{self.staff.id}",
            f"is_moderator_any_model_{self.staff.id}",
        )

    def _warm_moderator_caches(self):
        for key in self._cache_keys():
            cache.set(key, True)

    def _assert_caches_warm(self):
        for key in self._cache_keys():
            self.assertTrue(cache.get(key), f"{key} was unexpectedly cleared")

    def _assert_caches_cleared(self):
        for key in self._cache_keys():
            self.assertIsNone(cache.get(key), f"{key} was not cleared")

    def _collection(self, status):
        return Collection.objects.create(
            name="Moderation cache test",
            owner=self.owner,
            publication_status=status,
        )

    def test_unchanged_save_keeps_moderator_caches(self):
        collection = self._collection(Collection.STATUS_PRIVATE)
        self._warm_moderator_caches()
        collection.name = "Changed"
        collection.save()
        self._assert_caches_warm()

    def test_transition_between_non_review_statuses_keeps_caches(self):
        collection = self._collection(Collection.STATUS_PRIVATE)
        self._warm_moderator_caches()
        collection.publication_status = Collection.STATUS_PUBLISHED
        collection.save()
        self._assert_caches_warm()

    def test_submitting_for_review_clears_moderator_caches(self):
        collection = self._collection(Collection.STATUS_PRIVATE)
        self._warm_moderator_caches()
        collection.publication_status = Collection.STATUS_REVIEW
        collection.save()
        self._assert_caches_cleared()

    def test_leaving_review_clears_moderator_caches(self):
        collection = self._collection(Collection.STATUS_REVIEW)
        collection = Collection.objects.get(pk=collection.pk)
        self._warm_moderator_caches()
        collection.publication_status = Collection.STATUS_PRIVATE
        collection.save()
        self._assert_caches_cleared()

    def test_save_after_review_transition_detects_loaded_status(self):
        """Repeated saves must still see the last persisted status."""
        collection = self._collection(Collection.STATUS_PRIVATE)
        collection.publication_status = Collection.STATUS_REVIEW
        collection.save()
        self._warm_moderator_caches()
        collection.publication_status = Collection.STATUS_DECLINED
        collection.save()
        self._assert_caches_cleared()

    def test_deferred_status_save_keeps_moderator_caches(self):
        """Django reduces update_fields to the loaded fields for deferred
        instances, so such saves cannot change publication_status."""
        collection = self._collection(Collection.STATUS_PRIVATE)
        deferred = Collection.objects.only("name").get(pk=collection.pk)
        self._warm_moderator_caches()
        deferred.name = "Changed"
        deferred.save()
        self._assert_caches_warm()

    def test_unknown_loaded_status_falls_back_to_clearing(self):
        """When the persisted status cannot be determined (no tracking info),
        keep the conservative behaviour of clearing on a full save."""
        collection = self._collection(Collection.STATUS_PRIVATE)
        reloaded = Collection.objects.get(pk=collection.pk)
        reloaded._loaded_publication_status = None
        self._warm_moderator_caches()
        reloaded.save()
        self._assert_caches_cleared()
