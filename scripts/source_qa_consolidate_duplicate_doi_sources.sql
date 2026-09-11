-- One-off data fix: Consolidate duplicate DOI source pairs
-- Created: 2026-09-11
-- Affected tables: bibliography_source, bibliography_sourceauthor,
--   materials_sample_sources, processes_processsource,
--   materials_componentmeasurement_sources
-- Expected outcome: Zero duplicate DOI groups remain among referenced sources.
--   Unreferenced duplicates are deleted; referenced duplicates keep the
--   better-populated record and the other is removed after reference migration.
--
-- Duplicate DOI pairs found (6 groups):
--   1. 7195/11723  DOI 10.1007/s13399-020-01243-6  (Mboowa pulping review)
--   2. 7130/9438   DOI 10.1016/j.jenvman.2016.11.058 (Fisgativa food waste)
--   3. 9475/9478   DOI 10.1016/j.scitotenv.2020.141699 (Vanden Nest P sources)
--   4. 11717/20262 DOI 10.1080/10408398.2010.499808  (Le Bourvellec polyphenols)
--   5. 15438/18848 DOI 10.3390/ani10050831           (Monllor ensiling)
--   6. 15439/18845 DOI 10.3390/microorganisms13102237 (Tuovinen microbes)

BEGIN;

-- ---------------------------------------------------------------------------
-- Pair 1: 7195 (unreferenced, has author 60) → 11723 (referenced by process 7, no authors)
-- Keep 11723, move author from 7195, delete 7195.
-- ---------------------------------------------------------------------------
INSERT INTO bibliography_sourceauthor (source_id, author_id, position)
VALUES (11723, 60, 1)
ON CONFLICT DO NOTHING;

DELETE FROM bibliography_source WHERE id = 7195;

-- ---------------------------------------------------------------------------
-- Pair 2: 7130 (unreferenced, no authors) → 9438 (referenced, has 5 authors)
-- Keep 9438, delete 7130.
-- ---------------------------------------------------------------------------
DELETE FROM bibliography_source WHERE id = 7130;

-- ---------------------------------------------------------------------------
-- Pair 3: 9475 (referenced by sample 242, no authors, title "Mestwegwijzer+")
--   vs 9478 (referenced by sample 244, no authors, embedded-author title)
--   vs 11252 (referenced by sample 243, has 6 authors, clean title)
-- 11252 is the well-formed record. Merge 9475 and 9478 into 11252:
--   - Re-point sample 242 and 244 sources to 11252
--   - Clear the wrong DOI from 9475 (it belongs to 11252, not "Mestwegwijzer+")
--   - Delete 9475 and 9478
-- ---------------------------------------------------------------------------
UPDATE materials_sample_sources SET source_id = 11252 WHERE source_id = 9475;
UPDATE materials_sample_sources SET source_id = 11252 WHERE source_id = 9478;

-- Clear the erroneously assigned DOI from 9475 before deleting
UPDATE bibliography_source SET doi = NULL WHERE id = 9475;

DELETE FROM bibliography_source WHERE id IN (9475, 9478);

-- ---------------------------------------------------------------------------
-- Pair 4: 11717 (unreferenced, no authors) → 20262 (referenced, has 2 authors)
-- Keep 20262, delete 11717.
-- ---------------------------------------------------------------------------
DELETE FROM bibliography_source WHERE id = 11717;

-- ---------------------------------------------------------------------------
-- Pair 5: 15438 (unreferenced, no authors) → 18848 (referenced, has 6 authors)
-- Keep 18848, delete 15438.
-- ---------------------------------------------------------------------------
DELETE FROM bibliography_source WHERE id = 15438;

-- ---------------------------------------------------------------------------
-- Pair 6: 15439 (unreferenced, no authors) → 18845 (referenced, has 3 authors)
-- Keep 18845, delete 15439.
-- ---------------------------------------------------------------------------
DELETE FROM bibliography_source WHERE id = 15439;

COMMIT;

-- Verification queries
-- SELECT doi, COUNT(*) AS cnt, ARRAY_AGG(id ORDER BY id) AS source_ids
--   FROM bibliography_source
--   WHERE doi IS NOT NULL AND doi != ''
--   GROUP BY doi HAVING COUNT(*) > 1
--   ORDER BY cnt DESC;
-- -- Expected: 0 rows
