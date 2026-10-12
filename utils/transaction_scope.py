"""Transaction-scoped cache keys for values read inside atomic blocks.

Values cached under a plain key while inside an atomic block would leak past
a rollback — in tests, a ``TestCase`` transaction rolls back while the cache
keeps the pre-rollback value.  Scoping keys to the current atomic stack makes
entries unobservable outside the transaction unit that wrote them; plain
autocommit code shares the unscoped key so production keeps a single entry.
"""

import uuid

from django.db import connection, transaction


def _block_token(index, block, savepoint_ids):
    # Tokens are random so that workers sharing one cache backend never mint
    # the same scope. ``@transaction.atomic`` reuses one Atomic object per
    # decorated function, so a nested block also gets a new token whenever
    # it is re-entered under a different savepoint.
    savepoint_id = savepoint_ids[index - 1] if 0 < index <= len(savepoint_ids) else None
    stamp = getattr(block, "_cache_scope_stamp", None)
    if stamp is None or stamp[1] != savepoint_id:
        stamp = (uuid.uuid4().hex, savepoint_id)
        block._cache_scope_stamp = stamp
    return stamp[0]


def current_scope():
    """Return one token per atomic block on the default connection's stack."""
    blocks = getattr(connection, "atomic_blocks", None) or ()
    savepoint_ids = getattr(connection, "savepoint_ids", None) or ()
    return tuple(
        _block_token(index, block, savepoint_ids) for index, block in enumerate(blocks)
    )


def scope_is_active(scope):
    """Return True while every block of ``scope`` is still open."""
    return current_scope()[: len(scope)] == tuple(scope)


def _key(base_key, scope):
    return ":".join((base_key, *scope)) if scope else base_key


def scoped_cache_key(base_key):
    """Return ``base_key`` namespaced to the current atomic stack.

    Outside any atomic block the shared ``base_key`` is returned.
    """
    return _key(base_key, current_scope())


def delete_scoped(cache, base_key):
    """Drop the shared entry and every scope on the current atomic stack.

    Inside a transaction the shared entry is dropped again on commit: until
    then, autocommit readers in other workers can repopulate it with the
    previously committed row.
    """
    scope = current_scope()
    cache.delete_many(
        [_key(base_key, scope[:depth]) for depth in range(len(scope) + 1)]
    )
    if scope:
        transaction.on_commit(lambda: cache.delete(base_key))
