import importlib

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase

from utils import transaction_scope
from utils.object_management.models import get_default_owner_pk


class ScopedCacheKeyTests(TestCase):
    def test_keys_do_not_collide_across_independent_processes(self):
        """Each process (or fork) must mint its own tokens; a per-process
        counter gives every worker's first transaction the same key."""
        importlib.reload(transaction_scope)
        with transaction.atomic():
            first = transaction_scope.scoped_cache_key("probe")
        importlib.reload(transaction_scope)
        with transaction.atomic():
            second = transaction_scope.scoped_cache_key("probe")
        self.assertNotEqual(first, second)

    def test_reused_atomic_block_gets_a_fresh_scope(self):
        """``@transaction.atomic`` reuses one Atomic object per decorated
        function; a rolled-back run must not share keys with the next run."""
        block = transaction.atomic()
        with block:
            first = transaction_scope.scoped_cache_key("probe")
        with block:
            second = transaction_scope.scoped_cache_key("probe")
        self.assertNotEqual(first, second)

    def test_delete_scoped_drops_shared_key_again_after_commit(self):
        """A concurrent autocommit reader can repopulate the shared key with
        the old committed row before the writer commits."""
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                transaction_scope.delete_scoped(cache, "probe-shared")
                cache.set("probe-shared", "stale")
        self.assertIsNone(cache.get("probe-shared"))


class DefaultOwnerPkRollbackTests(TestCase):
    def test_pk_read_inside_rolled_back_block_is_not_reused(self):
        original_pk = get_default_owner_pk()
        owner = User.objects.get(pk=original_pk)
        username = owner.username

        class Rollback(Exception):
            pass

        try:
            with transaction.atomic():
                owner.username = f"displaced-{username}"
                owner.save()
                replacement = User.objects.create(username=username)
                self.assertEqual(get_default_owner_pk(), replacement.pk)
                raise Rollback
        except Rollback:
            pass

        self.assertEqual(get_default_owner_pk(), original_pk)
