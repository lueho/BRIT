-- One-off data fix: Publish all referenced sources and complete lifecycle metadata
-- Created: 2026-09-11
-- Affected tables: bibliography_source
-- Expected outcome: All 54 referenced sources are published with complete
--   lifecycle metadata (submitted_at, approved_at, approved_by, lastmodified_by).
--
-- State before this script:
--   54 referenced sources total
--   6 published (3 missing lifecycle: IDs 4, 5, 4094)
--   48 not published (private or review)
--
-- This script must be run AFTER all other source QA scripts so that:
--   - Source 9404 has corrected metadata and authors
--   - Duplicate sources have been consolidated
--   - Source 4094 type has been fixed
--   - Category C authors have been linked
--
-- Admin user: ID 1 (flexibi, is_superuser=true)

BEGIN;

-- ---------------------------------------------------------------------------
-- Step 1: Publish all referenced sources that are not yet published.
-- Sets lifecycle metadata for the review workflow: submitted → approved.
-- ---------------------------------------------------------------------------
WITH referenced AS (
  SELECT source_id FROM processes_processsource
  UNION
  SELECT source_id FROM materials_componentmeasurement_sources
  UNION
  SELECT source_id FROM materials_sample_sources
)
UPDATE bibliography_source s
SET
    publication_status = 'published',
    submitted_at = COALESCE(s.submitted_at, NOW()),
    approved_at = COALESCE(s.approved_at, NOW()),
    approved_by_id = COALESCE(s.approved_by_id, 1),
    lastmodified_by_id = COALESCE(s.lastmodified_by_id, 1)
FROM referenced r
WHERE s.id = r.source_id
  AND s.publication_status != 'published';

-- ---------------------------------------------------------------------------
-- Step 2: Backfill lifecycle metadata for published referenced sources
-- that are missing submitted_at, approved_at, approved_by, or lastmodified_by.
-- (Sources 4, 5, 4094 were published but had NULL lifecycle fields.)
-- ---------------------------------------------------------------------------
WITH referenced AS (
  SELECT source_id FROM processes_processsource
  UNION
  SELECT source_id FROM materials_componentmeasurement_sources
  UNION
  SELECT source_id FROM materials_sample_sources
)
UPDATE bibliography_source s
SET
    submitted_at = COALESCE(s.submitted_at, NOW()),
    approved_at = COALESCE(s.approved_at, NOW()),
    approved_by_id = COALESCE(s.approved_by_id, 1),
    lastmodified_by_id = COALESCE(s.lastmodified_by_id, 1)
FROM referenced r
WHERE s.id = r.source_id
  AND s.publication_status = 'published'
  AND (s.submitted_at IS NULL OR s.approved_at IS NULL OR s.approved_by_id IS NULL OR s.lastmodified_by_id IS NULL);

COMMIT;

-- Verification queries
-- WITH referenced AS (
--   SELECT source_id FROM processes_processsource
--   UNION
--   SELECT source_id FROM materials_componentmeasurement_sources
--   UNION
--   SELECT source_id FROM materials_sample_sources
-- )
-- SELECT
--   COUNT(*) AS total_referenced,
--   COUNT(*) FILTER (WHERE s.publication_status = 'published') AS published,
--   COUNT(*) FILTER (WHERE s.publication_status != 'published') AS not_published,
--   COUNT(*) FILTER (WHERE s.submitted_at IS NULL) AS missing_submitted_at,
--   COUNT(*) FILTER (WHERE s.approved_at IS NULL) AS missing_approved_at,
--   COUNT(*) FILTER (WHERE s.approved_by_id IS NULL) AS missing_approved_by,
--   COUNT(*) FILTER (WHERE s.lastmodified_by_id IS NULL) AS missing_lastmodified_by
-- FROM referenced r JOIN bibliography_source s ON s.id = r.source_id;
-- -- Expected: total_referenced=54, published=54, all missing counts = 0
