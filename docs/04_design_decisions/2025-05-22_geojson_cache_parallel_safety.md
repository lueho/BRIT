# MADR: Parallel-Safe GeoJSON Caching Tests in Django

## Status
Accepted

## Context
The Django test suite for BRIT includes tests for caching logic (GeoJSON endpoints for Region and NUTSRegion), which previously suffered from race conditions and false negatives when running in parallel (e.g., with `--parallel 4`). This was due to tests sharing cache keys and the use of pattern-based cache deletion in production code and signals.

## Decision
- Introduced a `@serial_test` decorator (see `utils.tests.testrunner`) to mark test classes or methods that must always run serially.
- Implemented a custom `SerialAwareTestRunner` which:
    - Runs all tests marked with `@serial_test` serially (parallel=1), after all other tests have run in parallel.
    - Handles initial data setup for all tests.
- All cache reliability for GeoJSON caching tests is now handled by marking them with `@serial_test`.
- No more patching of cache key functions or unique test-specific prefixes is required.
- Skips for cache backend feature checks remain, but all skips due to parallel race conditions have been removed.
- The approach is robust, portable, and does not require changes to Redis or Django cache settings.

## Consequences
- Caching tests are robust and parallel-safe: failures now indicate real bugs, not test environment issues.
- No test can delete another's cache key, even with pattern-based deletion in signals or management commands, because serial execution is enforced for those tests.
- The `@serial_test` pattern can be extended to any future tests that require isolation from parallelism.

## Alternatives Considered
- Patching cache key functions to add unique prefixes: rejected for brittleness and incomplete coverage.
- Using LocMemCache or per-worker Redis DBs for test isolation: rejected for portability and coverage of Redis-specific features.
- Skipping tests on missing cache keys: rejected as it can hide real cache bugs.

## Related Files
- `maps/tests/test_caching.py` (GeoJSONCachingTests, now marked with `@serial_test`)
- `utils/tests/testrunner.py` (`SerialAwareTestRunner`, `serial_test`)
- `maps/utils.py` (get_region_cache_key, get_nuts_region_cache_key)

## Date
2025-05-22

## Authors
Cascade AI + USER
