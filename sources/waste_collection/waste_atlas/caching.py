"""Transaction-scoped cache keys for runtime-editable atlas configuration.

Values cached under a plain key while inside an atomic block would leak past
a rollback — in tests, a ``TestCase`` transaction rolls back while the cache
keeps the pre-rollback value.  Scoping keys to the innermost atomic block
makes entries unobservable outside the transaction unit that wrote them;
plain autocommit code shares the unscoped key so production keeps a single
entry.
"""

import itertools

from django.db import connection

_token_counter = itertools.count()


def _block_token(block):
    token = getattr(block, "_atlas_cache_token", None)
    if token is None:
        token = next(_token_counter)
        block._atlas_cache_token = token
    return token


def scoped_cache_key(base_key):
    """Return ``base_key`` namespaced to the innermost atomic block.

    Outside any atomic block the shared ``base_key`` is returned.  Inside one,
    a token stored on the :class:`~django.db.transaction.Atomic` object itself
    makes the key unique to that transaction unit, so entries can never be
    served after the block exits or rolls back.
    """
    atomic_blocks = getattr(connection, "atomic_blocks", None)
    if not atomic_blocks:
        return base_key
    return f"{base_key}:{_block_token(atomic_blocks[-1])}"


def delete_scoped(cache, base_key):
    """Drop the shared entry and every scope on the current atomic stack."""
    cache.delete(base_key)
    atomic_blocks = getattr(connection, "atomic_blocks", None) or ()
    for block in atomic_blocks:
        token = getattr(block, "_atlas_cache_token", None)
        if token is not None:
            cache.delete(f"{base_key}:{token}")
