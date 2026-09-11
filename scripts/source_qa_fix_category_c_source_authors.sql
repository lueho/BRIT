-- One-off data fix: Link authors to Category C sources with embedded/incomplete author lists
-- Created: 2026-09-11
-- Affected tables: bibliography_author, bibliography_source, bibliography_sourceauthor
-- Expected outcome: Six referenced sources with embedded author names in titles
--   have their titles cleaned and proper SourceAuthor links created.
--
-- Category C sources identified (6 sources needing author research + linking):
--   9430 "Ritter (2020)"           → Annalena Ritter (author 7, exists)
--   9425 "Bastidas Jurado, C. G"    → Carla Gabriela Bastidas Jurado (author 8, exists)
--   9437 "Sortieranalyse KUKOM Steffen Walk" → Steffen Walk (author 5, exists)
--   9483 "phD Joshua Cooke (2023)..." → Joshua Cooke (new author, INRAE PhD thesis)
--   9419 "PhD Madelena De Ro"       → Madelena De Ro (new author, Ghent University)
--   11722 "Wheat straw as an alternative pulp fiber" → Peter W. Hart (new author)
--
-- Sources 9405, 9409, 9418, 9431, 9433, 9434, 9435, 9436, 9441, 9476, 9477,
-- 9480, 9481, 9482, 11713, 11723, 20260 are internal reports, standards, or
-- project names with no identifiable individual authors and are left as-is.

BEGIN;

-- ---------------------------------------------------------------------------
-- 9430: "Ritter (2020)" → Annalena Ritter (author 7, published)
-- Research: TUHH TORE person profile, ORCID 0000-0003-1314-2705
-- The title is just the author name and year — no real publication title found.
-- This is likely an internal/unpublished TUHH work. Keep the title as-is but
-- add the author link.
-- ---------------------------------------------------------------------------
INSERT INTO bibliography_sourceauthor (source_id, author_id, position)
VALUES (9430, 7, 1)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 9425: "Bastidas Jurado, C. G" → Carla Gabriela Bastidas Jurado (author 8)
-- Title is just the author name — likely an internal reference. Add author link.
-- ---------------------------------------------------------------------------
INSERT INTO bibliography_sourceauthor (source_id, author_id, position)
VALUES (9425, 8, 1)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 9437: "Sortieranalyse KUKOM Steffen Walk" → Steffen Walk (author 5)
-- Title contains author name. Clean title and add author link.
-- ---------------------------------------------------------------------------
UPDATE bibliography_source
SET title = 'Sortieranalyse KUKOM'
WHERE id = 9437;

INSERT INTO bibliography_sourceauthor (source_id, author_id, position)
VALUES (9437, 5, 1)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 9483: "phD Joshua Cooke (2023) Study and prediction..." → Joshua Cooke (new)
-- Research: INRAE PhD thesis, defended 2023-06-21 at Rennes
-- DOI: https://theses.hal.science/tel-04453521v1
-- Clean title to the actual thesis title.
-- ---------------------------------------------------------------------------
INSERT INTO bibliography_author (
    first_names, last_names, publication_status,
    institution, contact_email,
    owner_id, created_at, lastmodified_at, created_by_id, lastmodified_by_id,
    submitted_at, approved_at, approved_by_id
)
VALUES (
    'Joshua', 'Cooke', 'published',
    '', '',
    1, NOW(), NOW(), 1, 1,
    NOW(), NOW(), 1
);

UPDATE bibliography_source
SET
    title = 'Study and prediction of the impact of anaerobic digestion process parameters on the composition of digestates, and their effect on the structural stability of soils',
    citation_key = 'Cooke 2023'
WHERE id = 9483;

INSERT INTO bibliography_sourceauthor (source_id, author_id, position)
VALUES (
    9483,
    (SELECT id FROM bibliography_author WHERE first_names = 'Joshua' AND last_names = 'Cooke'),
    1
)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 9419: "PhD Madelena De Ro" → Madelena De Ro (new author)
-- Research: Ghent University MSc, linked to INRAE microbial ecology work.
-- No specific publication title found — this appears to be a project reference.
-- Clean title to remove "PhD" prefix.
-- ---------------------------------------------------------------------------
INSERT INTO bibliography_author (
    first_names, last_names, publication_status,
    institution, contact_email,
    owner_id, created_at, lastmodified_at, created_by_id, lastmodified_by_id,
    submitted_at, approved_at, approved_by_id
)
VALUES (
    'Madelena', 'De Ro', 'published',
    '', '',
    1, NOW(), NOW(), 1, 1,
    NOW(), NOW(), 1
);

UPDATE bibliography_source
SET title = 'De Ro project'
WHERE id = 9419;

INSERT INTO bibliography_sourceauthor (source_id, author_id, position)
VALUES (
    9419,
    (SELECT id FROM bibliography_author WHERE first_names = 'Madelena' AND last_names = 'De Ro'),
    1
)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 11722: "Wheat straw as an alternative pulp fiber" → Peter W. Hart (new author)
-- Research: TAPPI Journal, January 2020, DOI: 10.32964/TJ19.1.41
-- Author: Peter W. Hart (ORCID 0000-0003-0315-2424)
-- ---------------------------------------------------------------------------
INSERT INTO bibliography_author (
    first_names, last_names, publication_status,
    institution, contact_email,
    owner_id, created_at, lastmodified_at, created_by_id, lastmodified_by_id,
    submitted_at, approved_at, approved_by_id
)
VALUES (
    'Peter W.', 'Hart', 'published',
    '', '',
    1, NOW(), NOW(), 1, 1,
    NOW(), NOW(), 1
);

INSERT INTO bibliography_sourceauthor (source_id, author_id, position)
VALUES (
    11722,
    (SELECT id FROM bibliography_author WHERE first_names = 'Peter W.' AND last_names = 'Hart'),
    1
)
ON CONFLICT DO NOTHING;

COMMIT;

-- Verification queries
-- SELECT s.id, s.title, s.citation_key, COUNT(sa.id) AS author_count
--   FROM bibliography_source s
--   LEFT JOIN bibliography_sourceauthor sa ON sa.source_id = s.id
--   WHERE s.id IN (9430, 9425, 9437, 9483, 9419, 11722)
--   GROUP BY s.id, s.title, s.citation_key ORDER BY s.id;
